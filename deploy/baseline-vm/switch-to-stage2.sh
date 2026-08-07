#!/usr/bin/env bash
# Run on vm-baseline-app (172.16.200.24) as `student`.
# Switches the VM from Stage 1 (monolith + nginx) to Stage 2 (Docker Compose
# stack), live, in front of examiners. See documents/runbooks/final-demo-script.md
# for when this is used in the running order.
#
# REHEARSE THIS BEFORE THE REAL DEMO (sprint-plan.md R14) - do not run it for
# the first time during the actual exam slot.
set -euo pipefail

start=$SECONDS

echo "[switch-to-stage2] Stopping Stage 1 (monolith + nginx)..."
sudo systemctl stop bookstore-monolith
sudo systemctl disable bookstore-monolith
sudo systemctl stop nginx

echo "[switch-to-stage2] Confirming port 80 is free..."
for i in $(seq 1 10); do
  if ! sudo ss -tlnp | grep -q ':80 '; then
    break
  fi
  sleep 1
done
if sudo ss -tlnp | grep -q ':80 '; then
  echo "[switch-to-stage2] ERROR: port 80 still in use, aborting." >&2
  sudo ss -tlnp | grep ':80 '
  exit 1
fi

echo "[switch-to-stage2] Starting Stage 2 (docker compose up -d)..."
cd ~/deploy-docker
docker compose up -d

echo "[switch-to-stage2] Waiting for frontend healthcheck (up to 60s)..."
# Compose project name is "bookstore" (docker-compose.yml top-level `name:`),
# so the container is bookstore-frontend-1, not the directory-derived default.
status="starting"
for i in $(seq 1 30); do
  status=$(docker inspect -f '{{.State.Health.Status}}' bookstore-frontend-1 2>/dev/null || echo "starting")
  if [ "$status" = "healthy" ]; then
    echo "[switch-to-stage2] frontend healthy."
    break
  fi
  sleep 2
done
if [ "$status" != "healthy" ]; then
  echo "[switch-to-stage2] WARNING: frontend still '$status' after 60s - continuing to the API check anyway, but this is worth investigating (see diagnostics below if it fails)." >&2
fi

echo "[switch-to-stage2] Verifying API on port 80..."
if curl -sf http://127.0.0.1/api/books >/dev/null; then
  elapsed=$((SECONDS - start))
  echo "[switch-to-stage2] OK - Stage 2 is live on port 80 (${elapsed}s total)."
else
  echo "[switch-to-stage2] ERROR: API check failed. Diagnostics:" >&2
  echo "--- docker compose ps ---" >&2
  docker compose ps || true
  echo "--- docker compose logs --tail=50 frontend ---" >&2
  docker compose logs --tail=50 frontend || true
  echo "--- docker compose logs --tail=50 catalog ---" >&2
  docker compose logs --tail=50 catalog || true
  exit 1
fi
