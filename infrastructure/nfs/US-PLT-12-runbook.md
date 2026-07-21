# US-PLT-12 Runbook: NFS-backed persistent storage

Prerequisite: US-PLT-09/10/11 complete — cluster `Ready`, Calico/CoreDNS
validated, metrics-server and Ingress installed.

This is the first time anything gets configured on `registry-monitoring`
(172.16.200.23) — until now it's only existed as an allocation in the VM
table. This story proves the NFS-backed PV/PVC mechanism works (mount,
write/read, and data survival across pod reschedule) using a throwaway
test workload — it does **not** deploy the real PostgreSQL/Redis storage;
those get their own purpose-built manifests in Period 4.

## Part A — NFS server on `registry-monitoring` (172.16.200.23)

1. Install the NFS server:
   ```sh
   sudo apt update
   sudo apt install -y nfs-kernel-server
   ```

2. Create the export root and this story's test subdirectory:
   ```sh
   sudo mkdir -p /srv/nfs/k8s/pv-test
   sudo chown nobody:nogroup /srv/nfs/k8s/pv-test
   sudo chmod 777 /srv/nfs/k8s/pv-test
   ```
   Wide-open permissions here are a deliberate, documented simplification
   for this lab cluster — containers write as varying non-root UIDs, and
   fine-grained NFS UID/GID mapping isn't worth the added complexity for
   a 3-PV cluster. Not something to carry into a production design.

3. Configure the export — NFSv4 only (a single port, 2049, rather than
   NFSv3's rpcbind/mountd port sprawl), restricted to the cluster subnet:
   ```sh
   echo "/srv/nfs/k8s 172.16.200.0/24(rw,sync,no_subtree_check,no_root_squash)" | sudo tee -a /etc/exports
   sudo exportfs -ra
   sudo systemctl enable --now nfs-kernel-server
   ```

4. Verify the export is live:
   ```sh
   sudo exportfs -v
   ```
   Expect a line for `/srv/nfs/k8s` listing `172.16.200.0/24`.

5. Firewall — scoped to the cluster subnet only (unlike US-PLT-11's
   Ingress port, only the three cluster nodes need to mount this, not the
   user's laptop directly). **This is the first time `ufw` gets touched
   on this VM, so it's still inactive by default — allow SSH *before*
   enabling it, in that exact order, or you will lock yourself out over
   the VPN with no way back in:**
   ```sh
   sudo ufw allow OpenSSH
   sudo ufw allow from 172.16.200.0/24 to any port 2049 proto tcp
   sudo ufw enable
   sudo ufw status verbose
   ```
   Expect `Status: active` with both the OpenSSH and `2049/tcp` rules
   listed.

## Part B — NFS client on vm-worker-1 and vm-worker-2

```sh
sudo apt update
sudo apt install -y nfs-common
```
Without this package, kubelet can't mount an NFS-backed volume at all —
it fails with "unknown filesystem type 'nfs'". `vm-master` doesn't need
this: it carries the control-plane `NoSchedule` taint (SDD §10.1, no
normal app pods there), so it will never be asked to mount a PV — nothing
in this project plans to change that, so installing it there would just
be unused state, not real consistency.

Quick sanity check from either worker (optional but cheap — confirms
network/export reachability before involving Kubernetes at all):
```sh
sudo mkdir -p /mnt/nfs-check
sudo mount -t nfs4 172.16.200.23:/srv/nfs/k8s /mnt/nfs-check
ls /mnt/nfs-check   # expect to see pv-test/
sudo umount /mnt/nfs-check
```

## Part C — PV/PVC + test workload (this is the AC evidence)

1. Copy `nfs-pv-test.yaml` to wherever you run `kubectl` from, then apply
   it:
   ```sh
   kubectl apply -f nfs-pv-test.yaml
   ```

2. Confirm binding:
   ```sh
   kubectl get pv nfs-pv-test
   kubectl get pvc nfs-pvc-test
   ```
   Expect both `STATUS` columns to read `Bound`.

3. Wait for the test pod, then write and read through the mount — **this
   is the AC #1 evidence**:
   ```sh
   kubectl get pods -l app=nfs-test-writer -w   # Ctrl+C once Running
   ```
   ```sh
   POD=$(kubectl get pods -l app=nfs-test-writer -o jsonpath='{.items[0].metadata.name}')
   kubectl exec $POD -- sh -c 'echo "us-plt-12-$(date -u +%Y%m%dT%H%M%SZ)" > /data/testfile.txt'
   kubectl exec $POD -- cat /data/testfile.txt
   ```
   Paste back the written/read value.

4. Delete the pod (not the Deployment) so the ReplicaSet reschedules it —
   this is the literal "pod is deleted and rescheduled... restarts" from
   AC #2:
   ```sh
   kubectl get pod $POD -o jsonpath='{.spec.nodeName}'; echo   # note which node it was on
   kubectl delete pod $POD
   kubectl get pods -l app=nfs-test-writer -w   # wait for a NEW pod name, Running; Ctrl+C
   ```

5. Read the same file from the **new** pod — **this is the AC #2
   evidence**:
   ```sh
   NEWPOD=$(kubectl get pods -l app=nfs-test-writer -o jsonpath='{.items[0].metadata.name}')
   kubectl exec $NEWPOD -- cat /data/testfile.txt
   kubectl get pod $NEWPOD -o jsonpath='{.spec.nodeName}'; echo
   ```
   The content must match what was written in step 3. Worth noting (not
   required) whether the new pod landed on the *other* worker node — if
   so, that's extra confirmation this is genuinely network-backed
   storage, not incidentally-preserved node-local state.

## Cleanup

Because the PV uses `persistentVolumeReclaimPolicy: Retain` (a deliberate
choice, not an oversight — implements this project's R05 mitigation of
"document reclaim policy," so an accidental PVC deletion elsewhere can
never silently wipe real data), deleting the Kubernetes objects does
**not** delete the underlying file on `registry-monitoring`. Both steps
are required:

```sh
# wherever kubectl is pointed
kubectl delete -f nfs-pv-test.yaml
kubectl get pv,pvc,pods -l app=nfs-test-writer   # confirm all gone
```
```sh
# on registry-monitoring (172.16.200.23)
sudo rm -f /srv/nfs/k8s/pv-test/testfile.txt
ls /srv/nfs/k8s/pv-test   # confirm empty
```
