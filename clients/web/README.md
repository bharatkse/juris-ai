# Juris AI Web

Next.js 15 App Router (TypeScript, npm) for marketing, authentication,
conversations, streaming chat, attachments, citations, HITL approvals, quota
UX, and profile settings.

## Requirements

- Node.js 20.9 or newer (below 23)
- FastAPI on `http://localhost:8001` by default (`/api/v1`)

## Setup

```bash
# from repo root
make web-install
make web-dev
```

Or:

```bash
cd clients/web
cp .env.example .env.local
npm ci
npm run dev
```

Open [http://127.0.0.1:3100](http://127.0.0.1:3100). Port 3100 avoids Grafana on 3000.

## Environment

| Variable | Where | Default | Notes |
|---|---|---|---|
| `BACKEND_API_URL` | server only | `http://127.0.0.1:8001/api/v1` | FastAPI base. Never prefix with `NEXT_PUBLIC_`. In Docker: `http://api:8000/api/v1`. |
| `NEXT_PUBLIC_CHAT_STREAMING` | browser | `true` | Set `false` to use synchronous `POST /chat`. |
| `NEXT_PUBLIC_FEATURE_CONVERSATION_RENAME` | browser | `false` | No PATCH conversation route on FastAPI. |
| `PLAYWRIGHT_BASE_URL` | tests | `http://127.0.0.1:3100` | Optional. |
| `PLAYWRIGHT_DESIGN_BASE_URL` | design capture | `http://127.0.0.1:3107` | Dedicated Next port for reference PNGs. |
| `WEB_PORT` | Compose | `3100` | Host port mapping. |
| `NEXT_PUBLIC_DEFAULT_THEME` | browser (build-time) | `light` | `light` or `dark` only. Inlined by Next; pass as a Docker **build arg**. |

Copy `.env.example` to `.env.local` for local Next.js. Access/refresh tokens stay in `httpOnly` cookies; browser JS never sees them.

## Scripts

```bash
npm run dev             # Next.js on :3100
npm run lint            # ESLint, max-warnings=0
npm run format          # Prettier
npm run typecheck       # tsc --noEmit
npm test                # Vitest (`tests/config/vitest.config.ts`)
npm run build           # production bundle (standalone)
npm run e2e             # Playwright (`tests/e2e/playwright.config.ts`)
npm run design:capture  # visual refs (`tests/design/playwright.config.ts`)
```

From the repo root: `make web-ci` (OpenAPI types check + lint + typecheck + test + build).
`make web-api-types` regenerates `src/types/openapi.d.ts` from `openapi/openapi.json`.
`make web-e2e` and `make web-design-capture` run Playwright from the moved configs.

## API integration

The browser never talks to FastAPI hosts or ports. It calls same-origin `/api/auth/*` and `/api/backend/*`. `src/lib/api/client.ts` unwraps `ApiResponse`, times out, retries **GET/HEAD** on network/502/503/504, and normalizes `ApiError`. Feature modules live in `src/features/<name>/api.ts` with TanStack Query hooks.

There is no `GET /auth/me`. `/api/auth/me` decodes JWT `sub` and loads `GET /users/{id}`. Messages are `GET /conversations/{id}/messages` (not `/events`).

Feature flags (`src/config/features.ts`): conversation rename, usage dashboard, and document library stay off until the backend exposes those routes. Copy lives in `src/constants/copy.ts`.

Audit vs FastAPI: [`docs/clients/web/api-audit.md`](../../docs/clients/web/api-audit.md).

## Docker

Server stack must be up on `juris_ai_network` first.

```bash
make web-docker-build
make web-up          # production image, background
make web-logs
curl -sf http://127.0.0.1:3100/api/health
make web-down

make web-up-dev      # bind-mount + next dev
```

The image is built from [`docker/clients/web/Dockerfile`](../../docker/clients/web/Dockerfile)
with Compose context `clients/web` and `dockerfile` pointed at that file
from the context (`../../docker/clients/web/Dockerfile`). Ignore patterns
live next to the Dockerfile as `Dockerfile.dockerignore` (BuildKit), not
at the Next.js root, so the package root stays a Next app.

## Structure

```
clients/web/
├── public/
├── src/
├── tests/
│   ├── e2e/                 # Playwright e2e + playwright.config.ts
│   ├── design/              # visual capture spec, PNGs, playwright.config.ts
│   └── config/              # vitest.config.ts
├── .env.example
├── .eslintrc.json .prettierrc.json .prettierignore
├── next.config.mjs next-env.d.ts postcss.config.mjs
├── tailwind.config.ts tsconfig.json
├── package.json package-lock.json
├── README.md
└── .gitignore

docker/clients/
├── docker-compose.yml
└── web/
    ├── Dockerfile
    └── Dockerfile.dockerignore

docs/clients/web/design/     # Figma plugin, tokens, screen manifest
```

Unit tests stay colocated as `src/**/*.test.ts` (Vitest `include`). There is
no dump under `tests/unit/` because moving them would split each module from
its tests.

### Why these files stay at the package root

| File | Why it stays |
|---|---|
| `package.json`, `package-lock.json` | npm / Next package root |
| `next.config.mjs`, `next-env.d.ts` | Next.js loads them from cwd |
| `tsconfig.json` | `tsc` and Next default path |
| `postcss.config.mjs`, `tailwind.config.ts` | PostCSS/Tailwind resolution from app root |
| `.eslintrc.json`, `.prettierrc.json`, `.prettierignore` | ESLint 8 / Prettier look here; not merged into `package.json` (readability) |
| `.env.example` | documents env next to `.env.local` |
| `public/`, `src/` | Next App Router conventions |
| `README.md` | package docs |

`.next/`, `node_modules/`, and `*.tsbuildinfo` are gitignored. Incremental
TypeScript writes to `.next/cache/tsconfig.tsbuildinfo`.

- Browser calls same-origin `/api/auth/*` and `/api/backend/*` via `apiFetch` / `apiStream`.
- `app/api/backend/[...path]` attaches the Bearer token, retries once after refresh on 401, and blocks proxying `/auth/*`.
- Assistant Markdown is sanitized (`rehype-sanitize`).

## Theming

Modes: **light** and **dark** only (default **light**). `next-themes` sets `class` on `<html>` (`attribute="class"`, `enableSystem={false}`, `disableTransitionOnChange`, storage key `juris-theme`). A blocking script in `src/features/theme/theme-script.tsx` applies the stored value before paint. Stored `system` or unknown values migrate to the env default.

The light page canvas is **pure white** (`--background: 0 0% 100%` / `#FFFFFF`). Semantic tokens live in `src/config/theme.ts` and `src/styles/theme.css`. Tailwind maps them in `tailwind.config.ts` (`darkMode: "class"`). Components use `bg-background`, `bg-hover`, `bg-sidebar` — not hex or `bg-white`. Token table: [`docs/clients/web/design/runtime-tokens.md`](../../docs/clients/web/design/runtime-tokens.md).

### Change the default

Set `NEXT_PUBLIC_DEFAULT_THEME=light|dark` at **build** time (`.env.local` or Compose `build.args`). Other values fail env validation. Runtime `environment:` on the container does not rewrite an already-built bundle.

Primary and accent are tokens only; do not edit components to rebrand.

## Layout

- **Shell** (`src/components/layout/app-shell.tsx`): `h-dvh`, slim header, left sidebar ~260px.
- **Sidebar** (`conversation-sidebar.tsx`): New chat, search, Chats / Memory / Settings, Recents by day, account + theme at the bottom. Collapses to an icon rail on desktop; overlay drawer below 768px.
- **Chat** (`features/chat/components/`): `max-w-chat` column; assistant prose without a bubble; user bubble `max-w-[80%]`; composer rounded ~24px with circular Send / Stop.
- **Panel** (`side-panel.tsx`): resizable right rail on desktop, full-screen sheet on mobile (citations / sources).
- **Pages** (Settings, Memory): `max-w-5xl` content.
