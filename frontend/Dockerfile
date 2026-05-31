# Yuno frontend — Next.js 16 (App Router). Multi-stage: build, then run the
# self-contained standalone server for a small final image.

# ---------- builder ----------
FROM node:22-alpine AS builder
WORKDIR /app

# libc6-compat: glibc shim some Node native deps expect on Alpine.
RUN apk add --no-cache libc6-compat

# Install deps first (layer cache); package-lock.json -> reproducible install.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the client bundle at build time (NEXT_PUBLIC_* is inlined by Next).
# Point the browser at the published backend port; override per host if needed.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---------- runner ----------
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Run as the built-in non-root node user.
USER node

# `output: "standalone"` ships server.js + a minimal node_modules; static assets
# are copied separately (standalone doesn't include them).
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
