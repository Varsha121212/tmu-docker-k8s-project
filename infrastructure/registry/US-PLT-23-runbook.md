# US-PLT-23 Runbook: Deploy private Docker registry to registry-monitoring VM

Prerequisite: cluster `Ready` (US-PLT-09/10/11/12), all six `bookstore/*`
images already built and Trivy-scanned locally (Period 2, US-PLT-07/08).

`registry-monitoring` (172.16.200.23) so far only runs the NFS server from
US-PLT-12. This is the first time Docker gets installed there. This story
closes a gap `deploy/docker/scripts/start-registry.sh` deliberately left
open: its own header comment calls the `localhost:5000` registry "not the
eventual dedicated registry VM (that's a later, separate deployment step
once this is proven working locally)" — that later step is this runbook.

**Real finding, not just a hand-off gap:** the images already sitting in
`evidence/trivy/` are all tagged `0.1.0-385a7e9` / `0.0.0-385a7e9` — from
commit `385a7e9`. Current `main` is three commits ahead
(`ed29083`, `a706c3b`... check `git log --oneline -5` for the real current
list), and the most recent of those, "fixed few bugs in frontend...",
changed `apps/frontend` source (the `crypto.randomUUID` fallback and cart
badge fixes from US-PLT-20). **Reusing the `385a7e9`-tagged frontend image
as-is would silently ship a frontend build that predates those fixes.**
Part B below rebuilds fresh at current `HEAD` rather than retagging stale
images, so what lands in Kubernetes actually matches what's on `main`.

`build-scan-push.sh` has been changed (one line) to read its registry
target from a `REGISTRY` env var, defaulting to `localhost:5000` as
before — this lets the exact same build+scan+push logic (and its Trivy
Critical-severity gate) target the new VM registry without duplicating
that logic in this runbook.

## Part A — registry container on `registry-monitoring` (172.16.200.23)

1. Install Docker Engine (same apt-repo pattern US-PLT-09 already used for
   `containerd.io` on the cluster nodes, reused here for the full Docker
   package):
   ```sh
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl gnupg
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   sudo chmod a+r /etc/apt/keyrings/docker.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io
   sudo systemctl enable --now docker
   ```
   Note: this installs a second, independent `containerd` on this VM,
   unrelated to the cluster's own `containerd` on `vm-master`/
   `vm-worker-1`/`vm-worker-2` — this VM isn't a cluster node, so there's
   no conflict.

2. Run the registry, bind-mounted (not a named volume) so the data is
   visible/backup-able the same way the NFS export already is:
   ```sh
   sudo mkdir -p /srv/registry/data
   sudo docker run -d \
     --name bookstore-registry \
     -p 5000:5000 \
     --restart unless-stopped \
     -v /srv/registry/data:/var/lib/registry \
     registry:2
   ```
   `--restart unless-stopped` plus `systemctl enable --now docker` from
   step 1 together mean both the daemon and the container come back after
   a VM reboot — the same two guarantees Docker Desktop gives you for
   free on the laptop, made explicit here since this VM has no such
   behaviour by default.

3. Firewall. Unlike US-PLT-12's NFS port (only the three cluster nodes
   ever needed to reach it), this port also needs to accept a push from
   your own laptop, so confirm your WireGuard client's actual VPN IP
   falls inside `172.16.200.0/24` before scoping to it — if it doesn't,
   open the port unrestricted instead, same reasoning already applied to
   US-PLT-11's NodePort 30080. **This VM already has `ufw` active from
   US-PLT-12** (unlike a fresh VM), so just add the new rule:
   ```sh
   sudo ufw allow from 172.16.200.0/24 to any port 5000 proto tcp
   sudo ufw status verbose
   ```

4. Verify:
   ```sh
   curl http://172.16.200.23:5000/v2/_catalog
   ```
   Expect `{"repositories":[]}`.

## Part B — rebuild and push all six images to the new registry (from the dev laptop)

1. Docker Desktop refuses to push to a plain-HTTP, non-localhost registry
   by default — add an insecure-registry entry: Docker Desktop → Settings
   → Docker Engine, merge this into the JSON, then **Apply & Restart**:
   ```json
   {
     "insecure-registries": ["172.16.200.23:5000"]
   }
   ```

2. Confirm you're on the commit you intend to ship, then rebuild, rescan,
   and push all six images fresh — targeting the new registry via the
   `REGISTRY` env var, not the default `localhost:5000`:
   ```sh
   git log --oneline -5
   REGISTRY=172.16.200.23:5000 ./deploy/docker/scripts/build-scan-push.sh
   ```
   This reuses the exact same Trivy Critical-severity gate as Period 2 —
   if any image has an unresolved Critical finding, the push is blocked
   and the script exits non-zero, same as it always has.

3. Note the exact tags printed by the script (`<version>-<shortcommit>` —
   should now match your current `HEAD`'s short commit, not `385a7e9`).
   You'll need these tags again in US-PLT-13's runbook.

4. Verify:
   ```sh
   curl http://172.16.200.23:5000/v2/_catalog
   curl http://172.16.200.23:5000/v2/bookstore/identity/tags/list
   ```
   Expect all six `bookstore/<service>` repositories listed, and the tag
   from step 3 present.

## Part C — containerd trust on vm-master, vm-worker-1, vm-worker-2

Run on **all three nodes**, including `vm-master` — it will never
actually pull an app image (control-plane taint), but keeping the config
uniform is cheap and avoids a future untaint silently missing this step.
This is `containerd`'s own trust mechanism, not Docker's
`insecure-registries` (that's Docker-daemon-specific and doesn't apply —
these nodes run bare `containerd`, confirmed in US-PLT-09).

1. Check the current `config_path` setting. **Do not assume the plugin
   name or quote style from US-PLT-09's `SystemdCgroup` edit still
   applies** — this cluster runs `containerd v2.2.6` (confirmed live via
   `containerd --version`, not assumed), whose CRI plugin was restructured
   from the older `io.containerd.grpc.v1.cri` naming to
   `io.containerd.cri.v1.images`/`io.containerd.cri.v1.runtime`, and its
   generated config uses single-quoted TOML strings, not double-quoted:
   ```sh
   containerd --version
   grep -n '^\[plugins' /etc/containerd/config.toml
   grep -n 'config_path' /etc/containerd/config.toml
   ```
   Expect **two** `config_path = ''` matches — one under
   `[plugins.'io.containerd.cri.v1.images'.registry]` (this is the one to
   change), one under `[plugins.'io.containerd.transfer.v1.local']` (an
   unrelated image-transfer setting — leave it alone). Confirm which line
   number belongs to which section with `sed -n '<N-10>,<N+2>p'
   /etc/containerd/config.toml` around each match before changing
   anything — don't rely on line-number assumptions from another node or
   another containerd version.

2. Point only the registry one at the certs directory. A plain
   find-replace would hit both matches (identical text), so this scopes
   the substitution to the address range starting at the registry
   section's header line, using single quotes to match this file's actual
   style:
   ```sh
   sudo sed -i "/\[plugins\.'io\.containerd\.cri\.v1\.images'\.registry\]/,/config_path = ''/ s|config_path = ''|config_path = '/etc/containerd/certs.d'|" /etc/containerd/config.toml
   grep -n 'config_path' /etc/containerd/config.toml
   ```
   **Don't verify with `grep -A1 "<section header>"` here** — the two
   sections in this file don't have the same shape (the registry section
   is a 1-line block, so `-A1` happens to reach its `config_path`; the
   `transfer.v1.local` section has several other keys before its own
   `config_path`, so `-A1` on that header only shows an unrelated line and
   silently looks fine either way, proving nothing — this is exactly what
   happened during this story's first real run, and the mistake is worth
   avoiding a second time). The plain `grep -n 'config_path'` above is the
   only check that actually inspects both lines directly. Expect exactly
   two matches: one now reading `= '/etc/containerd/certs.d'` (the
   registry one you just changed), the other still `= ''`
   (`transfer.v1.local`, untouched, confirming the range-scoped sed above
   didn't overreach).

3. Create the per-registry trust file. **This directory name contains a
   colon and must never be created on the Windows laptop or committed to
   git** — NTFS forbids `:` in filenames, and this isn't a git-tracked
   path anyway; type this directly over SSH on each Linux node:
   ```sh
   sudo mkdir -p "/etc/containerd/certs.d/172.16.200.23:5000"
   cat <<'EOF' | sudo tee "/etc/containerd/certs.d/172.16.200.23:5000/hosts.toml"
   server = "http://172.16.200.23:5000"

   [host."http://172.16.200.23:5000"]
     capabilities = ["pull", "resolve"]
     skip_verify = true
   EOF
   ```

4. Restart containerd on **this node** (run on each of the three nodes as
   you work through them) and confirm it came back healthy locally:
   ```sh
   sudo systemctl restart containerd
   sudo systemctl status containerd --no-pager   # expect "active (running)", no errors in the boot log
   ```
   Then, **from `vm-master`** specifically (kubectl only has a working
   kubeconfig there — `kubeadm init` copies `admin.conf` to `vm-master`'s
   `~/.kube/config` only, `kubeadm join` doesn't do the same for workers,
   so running `kubectl` directly on `vm-worker-1`/`vm-worker-2` fails with
   a `localhost:8080: connection refused` error that looks alarming but
   is just a missing kubeconfig, not a sign anything is actually broken —
   confirmed hitting this for real during this story's first run),
   confirm the cluster-wide view is still healthy:
   ```sh
   kubectl get nodes    # confirm still all Ready
   ```

## Part D — verification (this is the AC evidence)

1. Direct pull test on a worker (proves the trust config itself works,
   independent of the scheduler). `crictl` is a separate tool
   (`cri-tools` package) — not installed by any prior step, containerd
   and the kubeadm/kubelet/kubectl packages don't bring it in. Install it
   from the same Kubernetes apt repo US-PLT-09 already configured on this
   node (no new package source needed), and point it at containerd's
   socket explicitly so it doesn't warn about an undiscovered runtime
   endpoint:
   ```sh
   # on vm-worker-1
   sudo apt-get update
   sudo apt-get install -y cri-tools
   cat <<'EOF' | sudo tee /etc/crictl.yaml
   runtime-endpoint: unix:///run/containerd/containerd.sock
   EOF
   ```
   Set the tag once as a variable rather than typing it inline —
   `<tag from Part B>` used directly and unquoted on a command line would
   hit the same bash-redirection bug already found in US-PLT-24's Part E
   (`<` and `>` are live shell operators, not inert placeholder markup):
   ```sh
   export IMAGE_TAG=0.1.0-XXXXXXX   # replace XXXXXXX with the short commit from Part B step 3
   sudo crictl pull 172.16.200.23:5000/bookstore/identity:"$IMAGE_TAG"
   sudo crictl images | grep identity
   ```
   Expect `Image is up to date for sha256:...` (or a fresh pull if it
   wasn't cached) — this is the actual evidence the trust config works,
   not just that the command ran.

2. Scheduler-driven pull test — a throwaway Pod with
   `imagePullPolicy: Always` to force a real pull rather than relying on
   step 1's cache. The manifest is `infrastructure/registry/
   registry-pull-test.yaml` (same pattern as `ingress-test.yaml`/
   `nfs-pv-test.yaml` from earlier stories — a real file in the repo, not
   just YAML text in this runbook). Copy it to wherever you run `kubectl`
   from (`vm-master`, per this story's kubectl-location question), fill
   in the real tag from Part B in place of `<tag from Part B>`, then:
   ```sh
   kubectl apply -f registry-pull-test.yaml
   kubectl get pod registry-pull-test -w   # Ctrl+C once Running
   kubectl describe pod registry-pull-test | grep -i pull   # confirm "Successfully pulled image"
   ```
   **Don't use `grep -A<N> Events` here** — the number of lines between
   the `Events:` header and the actual `Pulling`/`Pulled` lines varies
   (header row + separator already consume 2 lines before any real event
   text starts), so guessing a fixed window can silently cut off the one
   line that's the actual evidence, while still looking like a
   successful, complete check (this happened for real during this
   story's first run — `-A3` only ever reached the `Scheduled` line, and
   the pod was deleted before it could be re-checked). Searching for the
   evidence text directly (`grep -i pull`) doesn't depend on how many
   other events happen to come first.

3. Clean up — throwaway, same pattern as `ingress-test.yaml`/
   `nfs-pv-test.yaml`, not a permanent file:
   ```sh
   kubectl delete pod registry-pull-test
   ```

## What's still open after this runbook

Only the six `bookstore/*` images are covered by the trust config above.
`postgres:16-alpine` and `redis:7-alpine` (US-PLT-24) are public Docker
Hub images and need no registry or containerd changes at all — don't add
unnecessary trust config for images that don't need it.
