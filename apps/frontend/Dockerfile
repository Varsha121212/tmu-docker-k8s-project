# syntax=docker/dockerfile:1
FROM node:22-alpine AS builder
WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# nginx-unprivileged: runs as a non-root user (uid 101) listening on 8080 by
# default, instead of patching the standard nginx image to drop root (SDD 9.1
# / 12: non-root runtime user, minimal image).
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Trivy CVE-2026-31789 (libssl3/libcrypto3, fixed in Alpine's 3.3.7-r0):
# the base image layer predates that patch - pull current packages at
# build time rather than waiting for a new base image tag. apk needs to
# write /etc/apk and /lib/apk/db, which the image's own uid-101 user (set
# by nginx-unprivileged's base layers, before this stage even starts)
# can't do - switch to root only for this step, then back to 101
# immediately so every later instruction, and the running container,
# keeps the same non-root guarantee as before.
USER root
RUN apk update && apk upgrade --no-cache
USER 101

ARG APP_VERSION=0.1.0
ARG GIT_REVISION=unknown
LABEL org.opencontainers.image.title="bookstore-frontend" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_REVISION}" \
      org.opencontainers.image.source="https://github.com/tmu-cn8001/bookstore"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:8080/ || exit 1
