#!/usr/bin/env bash
# Run from your laptop (Git Bash), over the VPN, with the same SSH key
# access to all three hosts already used by every other cross-VM script in
# this project.
#
# Resets every book's inventory.stock.available_qty to a flat quantity on
# whichever stage(s) you name, so leftover state from testing/order
# placement doesn't show a false "out of stock" error during the demo.
# Uses restock-inventory.sql (same file) against all three stages - they
# run the identical inventory schema (ADR-007).
#
# Usage:
#   ./restock-all-stages.sh all             # restock all three, qty=999
#   ./restock-all-stages.sh stage1          # just Stage 1
#   ./restock-all-stages.sh stage2 stage3   # any subset
#   QTY=200 ./restock-all-stages.sh all     # override the flat quantity
#
# Assumes: POSTGRES_USER=postgres / POSTGRES_DB=bookstore on Stage 2/3
# (the convention already used throughout deploy/docker/.env and
# deploy/kubernetes/02-secrets.yaml) - adjust the -U/-d flags below first
# if your actual .env/Secret used different values.
set -euo pipefail

QTY="${QTY:-999}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="$SCRIPT_DIR/restock-inventory.sql"

restock_stage1() {
  echo "[restock] Stage 1 (vm-baseline-db, native Postgres)..."
  # /tmp, not ~ - /home/student defaults to 750, which the `postgres` OS
  # user can't traverse into (the identical class of bug already found and
  # fixed for nginx/www-data in US-PLT-20 - see MEMORY.md), so `sudo -u
  # postgres psql -f ~/...` fails with "Permission denied" no matter what
  # the file's own mode is.
  scp "$SQL_FILE" student@172.16.200.25:/tmp/restock-inventory.sql
  ssh student@172.16.200.25 \
    "sudo -u postgres psql -d bookstore -v qty=$QTY -f /tmp/restock-inventory.sql && rm -f /tmp/restock-inventory.sql"
}

restock_stage2() {
  echo "[restock] Stage 2 (vm-baseline-app, Docker Compose)..."
  scp "$SQL_FILE" student@172.16.200.24:/tmp/restock-inventory.sql
  ssh student@172.16.200.24 "
    docker cp /tmp/restock-inventory.sql bookstore-postgres-1:/tmp/restock-inventory.sql
    docker exec bookstore-postgres-1 psql -U postgres -d bookstore -v qty=$QTY -f /tmp/restock-inventory.sql
    docker exec bookstore-postgres-1 rm -f /tmp/restock-inventory.sql
    rm -f /tmp/restock-inventory.sql
  "
}

restock_stage3() {
  echo "[restock] Stage 3 (Kubernetes, via vm-master)..."
  scp "$SQL_FILE" student@172.16.200.20:/tmp/restock-inventory.sql
  ssh student@172.16.200.20 "
    kubectl cp /tmp/restock-inventory.sql bookstore/postgres-0:/tmp/restock-inventory.sql
    kubectl exec -n bookstore postgres-0 -- psql -U postgres -d bookstore -v qty=$QTY -f /tmp/restock-inventory.sql
    kubectl exec -n bookstore postgres-0 -- rm -f /tmp/restock-inventory.sql
    rm -f /tmp/restock-inventory.sql
  "
}

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 {all|stage1|stage2|stage3} [stage2 stage3 ...]" >&2
  exit 1
fi

for arg in "$@"; do
  case "$arg" in
    all)    restock_stage1; restock_stage2; restock_stage3 ;;
    stage1) restock_stage1 ;;
    stage2) restock_stage2 ;;
    stage3) restock_stage3 ;;
    *) echo "Unknown target: $arg (expected all|stage1|stage2|stage3)" >&2; exit 1 ;;
  esac
done

echo "[restock] Done. QTY=$QTY applied to requested stage(s)."
