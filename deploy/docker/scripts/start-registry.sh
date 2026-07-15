#!/bin/bash
# US-PLT-07: local private Docker registry for image push/pull round-trip
# testing (build -> push -> remove local copy -> pull -> run). Bound to
# localhost:5000 only - not the eventual dedicated registry VM (that's a
# later, separate deployment step once this is proven working locally).
set -euo pipefail

if docker ps --format '{{.Names}}' | grep -qx bookstore-registry; then
    echo "bookstore-registry is already running."
    exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -qx bookstore-registry; then
    docker start bookstore-registry
else
    docker run -d \
        --name bookstore-registry \
        -p 5000:5000 \
        --restart unless-stopped \
        -v bookstore-registry-data:/var/lib/registry \
        registry:2
fi

echo "Registry listening at localhost:5000."
