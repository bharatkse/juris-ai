# syntax=docker/dockerfile:1.7

# Pinned Node 20 (engines: >=20.9 <23) to match local/dev.
ARG NODE_IMAGE=node:20.19.4-alpine3.21

# ---------------------------------------------------------------------------
# deps — install from the lockfile only
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS deps
WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------------
# build — Next.js standalone output
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG BACKEND_API_URL=http://api:8000/api/v1
ARG NEXT_PUBLIC_CHAT_STREAMING=true
ARG NEXT_PUBLIC_DEFAULT_THEME=light
ARG NEXT_PUBLIC_FEATURE_MEMORY_BACKEND=http
ARG NEXT_PUBLIC_FEATURE_PROJECTS_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_PINS_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_DOCUMENTS_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_PREFERENCES_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_NOTIFICATIONS_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_INTEGRATIONS_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_API_KEYS_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_CONVERSATION_TITLES_BACKEND=local
ARG NEXT_PUBLIC_FEATURE_ADMIN=false
ARG NEXT_PUBLIC_FEATURE_PERMISSIONS=false
ENV BACKEND_API_URL=${BACKEND_API_URL} \
    NEXT_PUBLIC_CHAT_STREAMING=${NEXT_PUBLIC_CHAT_STREAMING} \
    NEXT_PUBLIC_DEFAULT_THEME=${NEXT_PUBLIC_DEFAULT_THEME} \
    NEXT_PUBLIC_FEATURE_MEMORY_BACKEND=${NEXT_PUBLIC_FEATURE_MEMORY_BACKEND} \
    NEXT_PUBLIC_FEATURE_PROJECTS_BACKEND=${NEXT_PUBLIC_FEATURE_PROJECTS_BACKEND} \
    NEXT_PUBLIC_FEATURE_PINS_BACKEND=${NEXT_PUBLIC_FEATURE_PINS_BACKEND} \
    NEXT_PUBLIC_FEATURE_DOCUMENTS_BACKEND=${NEXT_PUBLIC_FEATURE_DOCUMENTS_BACKEND} \
    NEXT_PUBLIC_FEATURE_PREFERENCES_BACKEND=${NEXT_PUBLIC_FEATURE_PREFERENCES_BACKEND} \
    NEXT_PUBLIC_FEATURE_NOTIFICATIONS_BACKEND=${NEXT_PUBLIC_FEATURE_NOTIFICATIONS_BACKEND} \
    NEXT_PUBLIC_FEATURE_INTEGRATIONS_BACKEND=${NEXT_PUBLIC_FEATURE_INTEGRATIONS_BACKEND} \
    NEXT_PUBLIC_FEATURE_API_KEYS_BACKEND=${NEXT_PUBLIC_FEATURE_API_KEYS_BACKEND} \
    NEXT_PUBLIC_FEATURE_CONVERSATION_TITLES_BACKEND=${NEXT_PUBLIC_FEATURE_CONVERSATION_TITLES_BACKEND} \
    NEXT_PUBLIC_FEATURE_ADMIN=${NEXT_PUBLIC_FEATURE_ADMIN} \
    NEXT_PUBLIC_FEATURE_PERMISSIONS=${NEXT_PUBLIC_FEATURE_PERMISSIONS} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build

# ---------------------------------------------------------------------------
# runtime — copy standalone server, non-root
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3100 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 --ingroup nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3100/api/health').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
