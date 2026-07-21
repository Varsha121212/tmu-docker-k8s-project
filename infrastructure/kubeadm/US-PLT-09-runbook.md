# US-PLT-09 Runbook: kubeadm cluster bootstrap

Target: three Ubuntu 24.04 LTS VMs, all 2 vCPU / 4 GB RAM / 50 GB disk, on the
same VPN-only private subnet already used for `vm-baseline-app`/`vm-baseline-db`
(US-PLT-20) — same WireGuard VPN, same SSH key auth, same `student@<ip>` login.

| Node | IP | Role |
|---|---|---|
| `vm-master` | 172.16.200.20 | Control plane only — `kube-apiserver`, `scheduler`, `controller-manager`, `etcd`. No application pods (control-plane taint stays in place). |
| `vm-worker-1` | 172.16.200.21 | Worker |
| `vm-worker-2` | 172.16.200.22 | Worker |

Run each numbered step yourself over SSH; paste back the output if anything
errors. This runbook only gets the cluster to `Ready` (kubeadm AC #1) with a
documented recovery path if a join fails (AC #2). Deeper CNI/DNS validation
(cross-node pod ping, Service-name resolution) is a separate story,
US-PLT-10 — not covered here. metrics-server and Ingress are US-PLT-11 —
also not covered here.

## Before you start — known gotchas

- **Duplicate `product_uuid`/MAC on cloned VMs.** If these three were
  provisioned from one template/snapshot, kubelet registration can collide
  silently. Phase 0.4 checks this before anything else is installed.
- **containerd's default config has `SystemdCgroup = false`.** This is the
  single most common "kubelet won't start / node stuck NotReady forever"
  cause on a fresh install. Phase 1 explicitly flips it — don't skip the
  `sed` step.
- **Outbound internet from a VPN-only subnet isn't guaranteed.**
  `kubeadm init` pulls images from `registry.k8s.io`, apt needs
  `pkgs.k8s.io`, Calico needs GitHub. Phase 0.8 checks this before you're
  mid-`kubeadm init` and it's harder to diagnose.
- **`swapoff -a` alone doesn't survive a reboot.** Phase 0.5 also edits
  `/etc/fstab`.
- **kubeadm/kubelet/kubectl must be the identical exact version on all
  three nodes** — not just the same minor version, the same
  version+deb-revision string. Phase 2 picks the version once on
  `vm-master` and has you reuse that literal string on both workers rather
  than re-querying "latest" independently on each node.
- **The join token expires after 24 hours.** If there's a gap between
  Phase 3 and Phase 4, see Phase 7.A.

## Phase 0 — Preflight (run on all three: vm-master, vm-worker-1, vm-worker-2)

1. Baseline checks:
   ```sh
   lsb_release -a               # expect Ubuntu 24.04
   free -h                      # expect ~4 GB
   df -h /                      # expect ~50 GB
   timedatectl                  # confirm NTP-synced; if not: sudo timedatectl set-ntp true
   ```

2. Set a unique hostname matching this node's role (run the matching line
   on each node, not all three):
   ```sh
   sudo hostnamectl set-hostname vm-master        # on vm-master
   sudo hostnamectl set-hostname vm-worker-1       # on vm-worker-1
   sudo hostnamectl set-hostname vm-worker-2       # on vm-worker-2
   ```
   Verify: `hostnamectl`

3. Static `/etc/hosts` entries — this subnet has no internal DNS, so append
   the same three lines on **all three** nodes:
   ```sh
   sudo tee -a /etc/hosts <<'EOF'
   172.16.200.20 vm-master
   172.16.200.21 vm-worker-1
   172.16.200.22 vm-worker-2
   EOF
   ```

4. Duplicate MAC/`product_uuid` check (cloned-VM gotcha) — run on all
   three, then compare the three outputs and confirm they all differ:
   ```sh
   sudo cat /sys/class/dmi/id/product_uuid
   ip link show | grep ether
   ```
   If any two nodes match, stop here — see Phase 7.E before continuing.

5. Disable swap, persistently:
   ```sh
   sudo swapoff -a
   sudo sed -i '/\sswap\s/s/^/#/' /etc/fstab
   free -h          # expect Swap: 0
   swapon --show    # expect empty output
   ```

6. Kernel modules for container networking:
   ```sh
   cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
   overlay
   br_netfilter
   EOF
   sudo modprobe overlay
   sudo modprobe br_netfilter
   lsmod | grep -E 'overlay|br_netfilter'   # expect both listed
   ```

7. sysctl for bridged traffic + IP forwarding:
   ```sh
   cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
   net.bridge.bridge-nf-call-iptables  = 1
   net.bridge.bridge-nf-call-ip6tables = 1
   net.ipv4.ip_forward                 = 1
   EOF
   sudo sysctl --system
   sysctl net.ipv4.ip_forward net.bridge.bridge-nf-call-iptables net.bridge.bridge-nf-call-ip6tables
   ```

8. Outbound connectivity check (catches an internet-access problem now,
   not mid-`kubeadm init`):
   ```sh
   curl -I https://registry.k8s.io
   curl -I https://pkgs.k8s.io
   curl -I https://github.com
   ```

9. Firewall — trust the whole VPN-gated subnet rather than enumerating
   kubeadm's control-plane/worker ports plus Calico's BGP(179)/IP-in-IP
   (protocol 4) individually; a wrong per-port rule here is itself a
   common cause of join failures, and this subnet is already gated by
   WireGuard + SSH keys:
   ```sh
   sudo ufw allow OpenSSH
   sudo ufw allow from 172.16.200.0/24
   sudo ufw enable
   sudo ufw status verbose
   ```
   *(Reference only, not applied — if this is ever hardened later: control
   plane inbound TCP 6443, 2379-2380, 10250, 10259, 10257; worker inbound
   TCP 10250 and 30000-32767; Calico TCP 179 and IP-in-IP protocol 4
   between all nodes.)*

## Phase 1 — containerd (all three nodes)

1. Install containerd from Docker's apt repo:
   ```sh
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list
   sudo apt-get update
   sudo apt-get install -y containerd.io
   ```

2. Generate the default config and fix the cgroup-driver gotcha:
   ```sh
   sudo mkdir -p /etc/containerd
   containerd config default | sudo tee /etc/containerd/config.toml
   sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
   sudo systemctl restart containerd
   sudo systemctl enable containerd
   ```

3. Verify:
   ```sh
   grep SystemdCgroup /etc/containerd/config.toml   # expect "true"
   systemctl status containerd --no-pager           # expect active (running)
   sudo ctr version
   ```

## Phase 2 — kubeadm / kubelet / kubectl (all three nodes)

1. **On `vm-master` only** — determine the current stable minor version
   once:
   ```sh
   K8S_FULL=$(curl -L -s https://dl.k8s.io/release/stable.txt)
   K8S_MINOR=$(echo "$K8S_FULL" | grep -oE '^v[0-9]+\.[0-9]+')
   echo "Full: $K8S_FULL   Repo channel: $K8S_MINOR"
   ```
   Write down `$K8S_MINOR` (e.g. `v1.32`) — reuse this **exact literal
   value** on both workers below. Don't re-run `stable.txt` independently
   on each node; "current stable" can drift between when you set up
   `vm-master` and when you get to the workers, and that drift is exactly
   how nodes end up on mismatched versions.

2. **On all three nodes**, substituting the value you recorded for
   `<K8S_MINOR>`:
   ```sh
   sudo apt-get install -y apt-transport-https ca-certificates curl gpg
   sudo mkdir -p /etc/apt/keyrings
   curl -fsSL https://pkgs.k8s.io/core:/stable:/<K8S_MINOR>/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
   echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/<K8S_MINOR>/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
   sudo apt-get update
   apt-cache madison kubeadm | head        # note the exact version string, e.g. 1.32.1-1.1
   ```

3. Install and pin the **identical exact version string** on all three
   nodes (use the string you noted above, don't let apt pick independently
   per node):
   ```sh
   KUBE_VERSION=<exact string from apt-cache madison, e.g. 1.32.1-1.1>
   sudo apt-get install -y kubelet=$KUBE_VERSION kubeadm=$KUBE_VERSION kubectl=$KUBE_VERSION
   sudo apt-mark hold kubelet kubeadm kubectl
   ```

4. Verify on each node, compare output across all three — they must match
   exactly:
   ```sh
   kubeadm version
   kubelet --version
   kubectl version --client
   ```

## Phase 3 — `kubeadm init` (vm-master only)

1. Pre-pull images first — turns a mid-init registry/DNS failure into an
   earlier, cheaper, more diagnosable one:
   ```sh
   sudo kubeadm config images pull
   ```

2. Initialize the control plane:
   ```sh
   sudo kubeadm init \
     --apiserver-advertise-address=172.16.200.20 \
     --pod-network-cidr=192.168.0.0/16 \
     --node-name=vm-master \
     | tee ~/kubeadm-init.log
   ```
   `--pod-network-cidr=192.168.0.0/16` must match Calico's default pool
   applied in Phase 5 — these two values have to agree, and a mismatch
   can't be hot-patched afterward (see Phase 7.D).

3. Extract and save the join command — copy the full 3-line block
   somewhere durable, the token expires in 24h:
   ```sh
   grep -A2 "kubeadm join" ~/kubeadm-init.log
   ```

4. Set up `kubectl` access on `vm-master`:
   ```sh
   mkdir -p $HOME/.kube
   sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
   sudo chown $(id -u):$(id -g) $HOME/.kube/config
   ```

5. Verify (NotReady is expected here — no CNI yet):
   ```sh
   kubectl get nodes -o wide          # vm-master, STATUS NotReady — expected
   kubectl get pods -n kube-system    # coredns Pending, everything else Running
   kubectl describe node vm-master | grep -A2 Taints   # expect node-role.kubernetes.io/control-plane:NoSchedule
   ```

6. **Optional** — use `kubectl` from your Windows laptop instead of SSH'd
   into `vm-master` every time, same pattern as the US-PLT-20 pgAdmin
   tunnel:
   ```sh
   scp student@172.16.200.20:~/.kube/config ./vm-master-kubeconfig
   ```
   Then in PowerShell: `$env:KUBECONFIG = ".\vm-master-kubeconfig"` before
   running `kubectl` locally.

## Phase 4 — `kubeadm join` (vm-worker-1, then vm-worker-2)

1. On each worker, run your saved join command (add `--node-name` for
   clarity even though it's normally auto-detected):
   ```sh
   sudo kubeadm join 172.16.200.20:6443 --token <token> \
     --discovery-token-ca-cert-hash sha256:<hash> \
     --node-name=vm-worker-1
   ```
   (Use `--node-name=vm-worker-2` on the second worker.)

2. Verify locally on the worker:
   ```sh
   systemctl status kubelet --no-pager   # expect active (running)
   ```

3. Verify from `vm-master` (still NotReady — expected, pre-CNI):
   ```sh
   kubectl get nodes -o wide
   ```

Repeat both steps on the second worker before moving to Phase 5.

## Phase 5 — Install Calico (vm-master only)

Using the plain manifest (not the Tigera operator) — fewer moving parts for
a fixed 2-worker lab cluster where the pod CIDR never changes.

1. Find the latest Calico release tag:
   ```sh
   curl -s https://api.github.com/repos/projectcalico/calico/releases/latest | grep '"tag_name"'
   ```

2. Download and sanity-check the manifest before applying:
   ```sh
   CALICO_TAG=<tag from above, e.g. v3.29.1>
   curl -O https://raw.githubusercontent.com/projectcalico/calico/$CALICO_TAG/manifests/calico.yaml
   grep -n "192.168.0.0/16" calico.yaml   # confirm it matches Phase 3's --pod-network-cidr
   ```

3. Apply and wait for everything to come up:
   ```sh
   kubectl apply -f calico.yaml
   kubectl get pods -n kube-system -w     # wait for calico-node-*, calico-kube-controllers-*, coredns-* all Running/Ready; Ctrl+C once stable
   ```

## Phase 6 — Final verification (this is the AC #1 evidence)

```sh
kubectl get nodes -o wide                          # expect all 3 Ready
kubectl get pods -n kube-system -o wide             # expect all Running
kubectl describe node vm-master | grep -A2 Taints   # control-plane taint still present — no app pods schedule here
```

Paste back the `kubectl get nodes -o wide` output once all three show
`Ready` — that's the acceptance evidence for this story.

**Explicitly not checked here** (belongs to US-PLT-10 instead): cross-node
pod-to-pod ping, Service-name DNS resolution via CoreDNS.

## Phase 7 — Recovery / retry (this is the AC #2 evidence)

Every path below is a documented step — if you hit a join failure, follow
the matching case rather than improvising.

**A. Discovery token expired, or you lost the join command**
```sh
# on vm-master
kubeadm token create --print-join-command
```
Use the freshly printed command on the affected worker; nothing else
changes.

**B. A node needs a clean retry (join half-failed, or you're re-running init)**
```sh
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo iptables -F && sudo iptables -t nat -F && sudo iptables -t mangle -F && sudo iptables -X
sudo systemctl restart containerd kubelet
```
Then re-run the appropriate step: `kubeadm join` (worker, using a fresh
token from A) or `kubeadm init` (master, see D).

**C. A node is stuck NotReady after joining, past Phase 5**
```sh
kubectl get pods -n kube-system -o wide | grep <node-name>
kubectl describe pod -n kube-system <calico-node-pod-on-that-node>
kubectl logs -n kube-system <calico-node-pod-on-that-node>
```
Check these two documented causes, in order:
1. Phase 0.6/0.7 (kernel modules/sysctl) wasn't actually applied on that
   node — re-run those exact commands, then
   `sudo systemctl restart containerd kubelet`.
2. Pod CIDR mismatch between `kubeadm init` and the applied Calico
   manifest — this can't be hot-patched; go to D.

**D. Full control-plane redo (wrong CIDR/advertise-address, or an
unrecoverable init failure)**
```sh
# vm-master
sudo kubeadm reset -f
sudo rm -rf /etc/kubernetes /var/lib/etcd
```
Re-run Phase 3 from `kubeadm config images pull` onward, capture a **new**
join command, then apply Phase 7.B and rejoin **both** workers with the new
command — the old join credentials are tied to the previous control
plane's CA and will not work against the reinitialized one.

**E. Duplicate `product_uuid`/MAC found in Phase 0.4**
Not fixable via kubeadm — this is a VM-provisioning issue. Documented fix:
regenerate a unique machine-id on the affected node, then re-verify:
```sh
sudo rm /etc/machine-id
sudo systemd-machine-id-setup
sudo cat /sys/class/dmi/id/product_uuid
```
If the `product_uuid` itself (not just `machine-id`) is duplicated, that's
a hypervisor-level VM template issue — request a NIC MAC/UUID regeneration
from whoever controls the VM template before continuing.
