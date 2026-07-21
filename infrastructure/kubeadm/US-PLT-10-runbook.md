# US-PLT-10 Runbook: Calico CNI and CoreDNS validation

Prerequisite: US-PLT-09 complete — `kubectl get nodes -o wide` shows
`vm-master`/`vm-worker-1`/`vm-worker-2` all `Ready`.

This validates that Calico actually routes pod traffic across nodes and
that CoreDNS actually resolves Service names to the correct ClusterIP —
not just that the Calico/CoreDNS pods report `Running` (US-PLT-09 already
confirmed that). Run this from wherever you have `kubectl` pointed at the
cluster (`vm-master` directly, or your laptop using the kubeconfig copied
out in US-PLT-09 Phase 3 step 6).

Uses `infrastructure/kubeadm/network-test-pods.yaml` — four throwaway
diagnostic objects (two pinned pods, one backend Deployment, one Service),
all in the `default` namespace, deleted at the end. Nothing here persists
or is part of the real application (that's US-PLT-13, Period 4).

## Phase 1 — Deploy the test objects

1. Copy `network-test-pods.yaml` to wherever you're running `kubectl` from
   (e.g. `scp infrastructure/kubeadm/network-test-pods.yaml
   student@172.16.200.20:~/` if running from `vm-master`), then apply it:
   ```sh
   kubectl apply -f network-test-pods.yaml
   ```

2. Wait for everything to come up:
   ```sh
   kubectl get pods -o wide -w
   ```
   Wait until `net-test-1`, `net-test-2`, and the `dns-test-backend-*` pod
   all show `Running`, then Ctrl+C.

3. Confirm the two test pods actually landed on the nodes you asked for —
   don't assume `nodeName` pinning worked, check it:
   ```sh
   kubectl get pods -o wide
   ```
   Expect `net-test-1`'s `NODE` column to read `vm-worker-1` and
   `net-test-2`'s to read `vm-worker-2`.

## Phase 2 — Cross-node ping (this is the AC #1 evidence)

1. Get each test pod's IP:
   ```sh
   kubectl get pod net-test-1 -o jsonpath='{.status.podIP}'; echo
   kubectl get pod net-test-2 -o jsonpath='{.status.podIP}'; echo
   ```

2. Ping worker-2's pod from worker-1's pod:
   ```sh
   kubectl exec net-test-1 -- ping -c 4 <net-test-2's IP from above>
   ```
   Expect `4 packets transmitted, 4 packets received, 0% packet loss`.

3. And the reverse direction, for a fuller confirmation of Calico's
   cross-node routing than the AC strictly requires:
   ```sh
   kubectl exec net-test-2 -- ping -c 4 <net-test-1's IP from above>
   ```
   Paste back both `ping` outputs — that's the AC #1 acceptance evidence.

## Phase 3 — Service-name DNS resolution (this is the AC #2 evidence)

1. Resolve the test Service's name from inside a pod:
   ```sh
   kubectl exec net-test-1 -- nslookup dns-test-svc
   ```

2. Independently read the Service's actual ClusterIP:
   ```sh
   kubectl get svc dns-test-svc -o jsonpath='{.spec.clusterIP}'; echo
   ```

3. Compare the two — the IP `nslookup` returned in step 1 must match the
   `clusterIP` from step 2 exactly. Paste back both outputs; that match is
   the AC #2 acceptance evidence, not just "nslookup returned something."

## Phase 4 — Cleanup

```sh
kubectl delete -f network-test-pods.yaml
kubectl get pods -o wide   # confirm net-test-1/net-test-2/dns-test-backend-* are gone
```
These were diagnostic-only; nothing from this story should still be
running afterward.

## Troubleshooting

**A pod is stuck `Pending`:**
```sh
kubectl describe pod <pod-name>
```
Check the `Events` section — most likely cause on a 2-worker lab cluster is
a resource-capacity conflict with something already running on that node.

**Ping fails outright (100% packet loss or "Destination Host
Unreachable"):** this points back at Calico itself, not this story's test
objects — check `calico-node` health on both workers involved:
```sh
kubectl get pods -n kube-system -o wide | grep calico-node
kubectl logs -n kube-system <calico-node-pod-on-the-affected-worker>
```
If a `calico-node` pod isn't `Running`, that's a regression from US-PLT-09,
not a new failure mode — the same diagnosis approach from that runbook's
Phase 7.C applies.

**`nslookup` fails or times out:**
```sh
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system <a-coredns-pod>
kubectl get ep kube-dns -n kube-system
```
If `kube-dns`'s Endpoints list is empty, CoreDNS itself isn't healthy —
check the CoreDNS pod logs above for the actual cause before re-testing.
