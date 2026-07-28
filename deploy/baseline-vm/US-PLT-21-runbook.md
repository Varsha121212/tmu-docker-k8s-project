# US-PLT-21 Runbook: Deploy the Stage 2 Compose stack to vm-baseline-app

Target: `vm-baseline-app` (172.16.200.24) only — the Compose stack is
self-contained (its own Postgres/Redis containers, per
`deploy/docker/docker-compose.yml`), so `vm-baseline-db` is **not** touched
and simply goes unused from this point on. Stage 1 is stopped, not deleted —
it needs to come back later for the live demo.

Run each numbered step yourself; paste back the output if anything errors.

## Part A — Stop Stage 1, free port 80

```sh
sudo systemctl stop bookstore-monolith
sudo systemctl disable bookstore-monolith
sudo systemctl stop nginx
sudo ss -tlnp | grep ':80 '   # expect no output - port free
```
(`disable`, not just `stop` — a reboot shouldn't silently bring Stage 1 back
up underneath Stage 2. The venv, code, and systemd unit file are untouched;
re-enabling later for the demo is a one-line `systemctl enable --now`.)

## Part B — Install Docker Engine + Compose plugin

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world    # confirm the engine actually works
```

`student` isn't in the `docker` group by default on this VM (same finding
already logged from US-PLT-18) — every `docker`/`docker compose` command in
Parts D onward is written **without** `sudo`, so add the group membership
now rather than patching each command individually:
```sh
sudo usermod -aG docker student
```
Then start a fresh session so the new group actually applies — either log
out and back in over SSH, or run:
```sh
newgrp docker
docker ps    # should now work with no sudo and no permission error
```

Trust the non-TLS `registry-monitoring` registry (Docker refuses plain-HTTP
registries by default — same reason the k8s nodes needed a containerd
`certs.d`/`hosts.toml` trust entry in US-PLT-23, this is Docker's own
equivalent):
```sh
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "insecure-registries": ["172.16.200.23:5000"]
}
EOF
sudo systemctl restart docker
```

Port 80 is already open in `ufw` from US-PLT-20 — no new firewall rule
needed; Compose's internal service-to-service traffic stays on its own
bridge network, never touching the host firewall.

## Part C — Copy the compose stack, write a fresh `.env`

From your Windows machine:
```sh
scp deploy/docker/docker-compose.yml student@172.16.200.24:~/deploy-docker/
scp deploy/docker/postgres/init-db-roles.sh student@172.16.200.24:~/deploy-docker/postgres/
```
(**not** `docker-compose.override.yml` — that's the pgAdmin dev-only file,
explicitly flagged in Period 2 as not part of the intended network design.)

If `scp` complains the remote directory doesn't exist, create it first:
```sh
ssh student@172.16.200.24 "mkdir -p ~/deploy-docker/postgres"
```

On `vm-baseline-app`, generate fresh secrets (independent of Stage 1's —
different deployment, own security domain) and write `.env`:
```sh
cd ~/deploy-docker
for name in POSTGRES_PASSWORD IDENTITY_MIGRATOR_PASSWORD IDENTITY_APP_PASSWORD \
    CATALOG_MIGRATOR_PASSWORD CATALOG_APP_PASSWORD INVENTORY_MIGRATOR_PASSWORD \
    INVENTORY_APP_PASSWORD ORDER_MIGRATOR_PASSWORD ORDER_APP_PASSWORD; do
  echo "$name=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
done
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('INTERNAL_SERVICE_TOKEN=' + secrets.token_urlsafe(32))"
```
Paste each generated line into `.env` (`nano .env`), plus these fixed values:
```
POSTGRES_USER=postgres
POSTGRES_DB=bookstore
IMAGE_TAG=0.1.1-a08a02d
FRONTEND_IMAGE_TAG=0.0.0-1c39d25
```
(these are the current tags on `registry-monitoring` as of this deploy —
five backend services at `0.1.1-a08a02d`, frontend at `0.0.0-1c39d25`; the
compose file was fixed to use a separate `FRONTEND_IMAGE_TAG` variable
specifically because these two differ — reusing one shared tag was already
a real bug caught once before in the Kubernetes deployment.)
```sh
chmod 600 .env
```

## Part D — Pull and retag the six images

```sh
for svc in identity catalog inventory cart order; do
  docker pull 172.16.200.23:5000/bookstore/$svc:0.1.1-a08a02d
  docker tag 172.16.200.23:5000/bookstore/$svc:0.1.1-a08a02d bookstore/$svc:0.1.1-a08a02d
done
docker pull 172.16.200.23:5000/bookstore/frontend:0.0.0-1c39d25
docker tag 172.16.200.23:5000/bookstore/frontend:0.0.0-1c39d25 bookstore/frontend:0.0.0-1c39d25
docker images | grep bookstore
```
Retagging matters: `docker-compose.yml` still has a `build:` context per
service (unchanged from Period 2), but Compose only invokes a build when the
tagged image it's looking for isn't already present locally — since every
tag above now exists locally under the exact name/tag the compose file
expects, `docker compose up` (no `--build`) will use these pulled images
directly rather than rebuilding from source (which wouldn't even work here,
since `apps/services/*`/`apps/frontend` source isn't copied to this VM).

## Part E — Bring the stack up

```sh
cd ~/deploy-docker
docker compose up -d
docker compose ps
```
Expect all four `migrate-*` jobs and both `seed-*` jobs to show `Exited (0)`,
and `postgres`/`redis`/`identity`/`catalog`/`inventory`/`cart`/`order`/
`frontend` all `Up (healthy)`. If anything shows a build attempt instead of
a pull, stop and report back before continuing — it means Part D's retag
didn't match what the compose file expects.

## Part F — Verify (AC#1: full customer journey)

```sh
curl http://172.16.200.24/api/books     # expect 16 seeded books, JSON
```
Then in a browser at `http://172.16.200.24/`, walk register → browse → add
to cart → checkout → order history, same as US-PLT-20's own verification.

## Part G — Record versions (AC#2: fairness control, PMP 17.4)

```sh
docker inspect --format='{{.RepoTags}} {{index .RepoDigests 0}}' \
  bookstore/identity:0.1.1-a08a02d bookstore/catalog:0.1.1-a08a02d \
  bookstore/inventory:0.1.1-a08a02d bookstore/cart:0.1.1-a08a02d \
  bookstore/order:0.1.1-a08a02d bookstore/frontend:0.0.0-1c39d25
```
Save this output — it's the same image digests already used for Stage 3
(Kubernetes runs the identical `0.1.1-a08a02d`/`0.0.0-1c39d25` images), so
recording it here confirms Stage 1 (a different codebase entirely, the
monolith), Stage 2, and Stage 3 are all being compared on their intended,
documented versions rather than an accidental drift.

Report back once Part F's journey is confirmed and I'll mark US-PLT-21 done
and update `sprint-plan.md`/`MEMORY.md`.
