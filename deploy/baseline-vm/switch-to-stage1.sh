#!/usr/bin/env bash
# Run on vm-baseline-app (172.16.200.24) as `student`.
# Switches the VM from Stage 2 (Docker Compose stack) back to Stage 1
# (monolith + nginx). See documents/runbooks/final-demo-script.md for when
# this is used (pre-warm before the exam slot, per the demo storyline).
#
# REHEARSE THIS BEFORE THE REAL DEMO (sprint-plan.md R14) - do not run it for
# the first time during the actual exam slot.
set -euo pipefail

start=$SECONDS

echo "[switch-to-stage1] Stopping Stage 2 (docker compose down)..."
cd ~/deploy-docker
docker compose down

echo "[switch-to-stage1] Starting Stage 1 (monolith + nginx)..."
sudo systemctl enable --now bookstore-monolith
sudo systemctl start nginx

echo "[switch-to-stage1] Confirming monolith and nginx are active..."
if ! sudo systemctl is-active --quiet bookstore-monolith; then
  echo "[switch-to-stage1] ERROR: bookstore-monolith did not become active." >&2
  sudo systemctl status bookstore-monolith --no-pager
  exit 1
fi
if ! sudo systemctl is-active --quiet nginx; then
  echo "[switch-to-stage1] ERROR: nginx did not become active." >&2
  sudo systemctl status nginx --no-pager
  exit 1
fi

echo "[switch-to-stage1] Verifying API on port 80 (up to 30s, uvicorn/DB may still be starting up)..."
ok=0
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1/api/books >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done

if [ "$ok" = 1 ]; then
  elapsed=$((SECONDS - start))
  echo "[switch-to-stage1] OK - Stage 1 is live on port 80 (${elapsed}s total)."
else
  echo "[switch-to-stage1] ERROR: API check still failing after 30s. Diagnostics:" >&2
  echo "--- curl -v http://127.0.0.1:8000/api/books (direct to monolith, bypassing nginx) ---" >&2
  curl -v http://127.0.0.1:8000/api/books || true
  echo "--- curl -v http://127.0.0.1/api/books (through nginx) ---" >&2
  curl -v http://127.0.0.1/api/books || true
  echo "--- sudo journalctl -u bookstore-monolith -n 50 --no-pager ---" >&2
  sudo journalctl -u bookstore-monolith -n 50 --no-pager || true
  exit 1
fi
