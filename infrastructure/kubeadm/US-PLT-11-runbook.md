# US-PLT-11 Runbook: metrics-server and NGINX Ingress installation

Prerequisite: US-PLT-09/US-PLT-10 complete — cluster `Ready`, Calico and
CoreDNS validated. Run this from wherever `kubectl` is pointed at the
cluster.

**Known sequencing gap, by design — read before you start:** AC #2 says
"the Ingress Controller is installed **and the frontend is deployed**...
the frontend loads via the Ingress path." The real frontend doesn't exist
yet — it's deployed in US-PLT-13 (Period 4). Part B below proves the
Ingress *mechanism* end-to-end with a throwaway placeholder page instead
of the real frontend. That's real, valid evidence the routing works; the
literal AC (with the actual frontend) gets its final confirmation once
US-PLT-13 lands.

## Part A — metrics-server (this is the AC #1 evidence)

1. Apply the official manifest:
   ```sh
   kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
   ```

2. Patch in `--kubelet-insecure-tls` — on a kubeadm cluster, kubelet's
   serving certificates aren't in metrics-server's default trusted CA
   pool, so it can't scrape without this flag (a universal kubeadm
   gotcha, not specific to this cluster):
   ```sh
   kubectl patch deployment metrics-server -n kube-system --type='json' \
     -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
   ```

3. Wait for it to come up:
   ```sh
   kubectl rollout status deployment/metrics-server -n kube-system
   ```

4. Give it ~60 seconds for the first scrape cycle — an immediate `kubectl
   top` right after startup can legitimately return "metrics not
   available yet"; that's not a failure, just wait and retry:
   ```sh
   sleep 60
   kubectl top nodes
   kubectl top pods -A
   ```
   Paste back both outputs — real per-pod CPU/memory numbers here are the
   AC #1 acceptance evidence. No throwaway pods needed; `kube-system`'s
   already-running pods (CoreDNS, Calico, etc.) are enough.

## Part B — NGINX Ingress Controller (installs Ingress, proves the mechanism for AC #2)

1. Find the latest `ingress-nginx` release tag:
   ```sh
   curl -s https://api.github.com/repos/kubernetes/ingress-nginx/releases/latest | grep '"tag_name"'
   ```

2. Download and apply the official bare-metal manifest (NodePort
   exposure — the standard approach for a kubeadm cluster with no cloud
   load balancer):
   ```sh
   INGRESS_TAG=<tag from above, e.g. controller-v1.13.0>
   curl -O https://raw.githubusercontent.com/kubernetes/ingress-nginx/$INGRESS_TAG/deploy/static/provider/baremetal/deploy.yaml
   kubectl apply -f deploy.yaml
   kubectl get pods -n ingress-nginx -w    # wait for controller pod Running/Ready; Ctrl+C once stable
   ```

3. Pin the NodePort to a fixed, memorable value instead of leaving it
   randomly assigned (a random port would silently change on any future
   redeploy and break a bookmarked demo URL). HTTPS is intentionally left
   unpinned/unopened — this project doesn't do TLS on the Kubernetes
   Ingress (SDD §20 names this a known lab-environment limitation, same
   as Stage 1's plain-HTTP precedent):
   ```sh
   kubectl patch svc ingress-nginx-controller -n ingress-nginx --type='json' \
     -p='[{"op":"replace","path":"/spec/ports/0/nodePort","value":30080}]'
   kubectl get svc ingress-nginx-controller -n ingress-nginx   # confirm 80:30080/TCP
   ```

4. Firewall — **this is a new rule, not covered by US-PLT-09's earlier
   ufw setup.** US-PLT-09 Phase 0.9 only opened the cluster subnet
   (`172.16.200.0/24`) to itself; your laptop's own WireGuard client IP
   isn't necessarily inside that range — the same reason US-PLT-20 opened
   port 80 on `vm-baseline-app` unrestricted rather than scoped to a
   subnet. NodePort Services are reachable via **any** node's IP by
   default, so open it on all three nodes:
   ```sh
   # on vm-master, vm-worker-1, and vm-worker-2
   sudo ufw allow 30080/tcp
   sudo ufw status verbose   # confirm the rule is listed
   ```

5. Deploy the placeholder test page:
   ```sh
   kubectl apply -f ingress-test.yaml
   kubectl get pods -w   # wait for ingress-test-backend-* Running; Ctrl+C once stable
   ```

6. From an actual browser on your laptop (over the VPN, not `curl` from a
   node — this needs to prove real external browser access), open:
   ```
   http://<any-node-ip>:30080/ingress-test
   ```
   e.g. `http://172.16.200.21:30080/ingress-test`. Expect the default
   `nginx:alpine` welcome page. That's the AC #2 mechanism evidence —
   external HTTP over the VPN reached the Ingress Controller, which
   routed it to the right Service and pod.

7. Clean up the placeholder — it was only there to prove the path works,
   not to stay:
   ```sh
   kubectl delete -f ingress-test.yaml
   kubectl get pods   # confirm ingress-test-backend-* is gone
   ```
   Leave the Ingress Controller itself (`ingress-nginx` namespace)
   running — unlike the placeholder, it's real platform infrastructure
   Period 4's application deployment depends on.

## What's still open after this runbook

AC #2's literal wording — "the frontend is deployed... loads via the
Ingress path" — isn't fully closed by this story alone, because the real
frontend doesn't exist until US-PLT-13 (Period 4). This runbook proves
the Ingress mechanism itself is sound; final confirmation with the actual
frontend happens once US-PLT-13 adds a real Ingress rule for it and it's
loaded the same way (`http://<node-ip>:30080/`) from a VPN browser.
