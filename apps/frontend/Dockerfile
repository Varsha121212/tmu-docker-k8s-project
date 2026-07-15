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
