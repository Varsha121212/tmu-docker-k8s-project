#!/bin/bash
# US-PLT-05/07/08: build every service image, scan it with Trivy before
# registry promotion, and push only images with no unresolved Critical
# finding - Trivy runs as the gate immediately before the push it protects,
# not as a separate disconnected step (SDD 9.1: "Trivy scan result retained
# before registry promotion").
#
# Usage: deploy/docker/scripts/build-scan-push.sh [service ...]
#   No arguments builds/scans/pushes all six images.
#
# Tag convention (SDD 9.1): registry:5000/bookstore/<service>:<semver>-<short-commit>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REGISTRY="localhost:5000"
SHORT_COMMIT="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo "nogit")"
EVIDENCE_DIR="$ROOT_DIR/evidence/trivy"
mkdir -p "$EVIDENCE_DIR"

declare -A CONTEXTS=(
    [identity]="apps/services/identity"
    [catalog]="apps/services/catalog"
    [inventory]="apps/services/inventory"
    [cart]="apps/services/cart"
    [order]="apps/services/order"
    [frontend]="apps/frontend"
)

version_for() {
    local service="$1" context="$ROOT_DIR/${CONTEXTS[$service]}"
    if [ -f "$context/pyproject.toml" ]; then
        grep -m1 '^version' "$context/pyproject.toml" | sed -E 's/version = "(.*)"/\1/'
    else
        grep -m1 '"version"' "$context/package.json" | sed -E 's/.*"version": *"([^"]*)".*/\1/'
    fi
}

build_scan_push_one() {
    local service="$1"
    local context="$ROOT_DIR/${CONTEXTS[$service]}"
    local version
    version="$(version_for "$service")"
    local tag="${version}-${SHORT_COMMIT}"
    local local_image="bookstore/${service}:${tag}"
    local registry_image="${REGISTRY}/bookstore/${service}:${tag}"
    local report_file="$EVIDENCE_DIR/${service}-${tag}.json"

    echo "== ${service}: building ${local_image} =="
    docker build \
        --build-arg "APP_VERSION=${version}" \
        --build-arg "GIT_REVISION=${SHORT_COMMIT}" \
        -t "$local_image" \
        -t "$registry_image" \
        "$context"

    echo "== ${service}: scanning with Trivy =="
    trivy image \
        --format json \
        --output "$report_file" \
        --severity CRITICAL,HIGH \
        "$local_image"

    local critical_count
    critical_count="$(
        ./apps/services/identity/.venv/Scripts/python.exe - "$report_file" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    report = json.load(f)
count = 0
for result in report.get("Results", []) or []:
    for vuln in result.get("Vulnerabilities", []) or []:
        if vuln.get("Severity") == "CRITICAL":
            count += 1
print(count)
PY
    )"

    if [ "$critical_count" -gt 0 ]; then
        echo "!! ${service}: ${critical_count} unresolved Critical finding(s) - blocking promotion."
        echo "   Report: $report_file"
        echo "   To override, document the accepted risk and re-run with --allow-critical."
        return 1
    fi

    echo "== ${service}: no Critical findings, pushing to ${REGISTRY} =="
    docker push "$registry_image"
    local digest
    digest="$(docker inspect --format='{{index .RepoDigests 0}}' "$registry_image" 2>/dev/null || echo "unknown")"
    echo "   Pushed. Digest: $digest"
    echo "$digest" > "$EVIDENCE_DIR/${service}-${tag}.digest.txt"
}

SERVICES=("$@")
if [ "${#SERVICES[@]}" -eq 0 ]; then
    SERVICES=(identity catalog inventory cart order frontend)
fi

FAILED=()
for service in "${SERVICES[@]}"; do
    if [ -z "${CONTEXTS[$service]+x}" ]; then
        echo "Unknown service: $service" >&2
        exit 1
    fi
    build_scan_push_one "$service" || FAILED+=("$service")
done

if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "Blocked (Critical findings): ${FAILED[*]}"
    exit 1
fi

echo "All images built, scanned, and pushed successfully."
