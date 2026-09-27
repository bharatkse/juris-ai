# Juris AI Web

Phases 1–4 of the Juris AI frontend: a Next.js 15 App Router application with
marketing, secure authentication, conversation management, streaming chat,
document attachments, source-led answers, approval controls, quota UX, and
editable profile settings.

## Requirements

- Node.js 20.9 or newer
- The FastAPI service on `http://localhost:8001` by default

## Setup

```bash
cd clients/web
cp .env.example .env.local
npm install
npm run dev
```

Open [http://127.0.0.1:3100](http://127.0.0.1:3100). The app uses port
3100 so it does not collide with Grafana on 3000.

`BACKEND_API_URL` is server-only and defaults to
`http://localhost:8001/api/v1`. Do not rename it with a `NEXT_PUBLIC_` prefix.
Chat uses committed SSE completion events by default. Set
`NEXT_PUBLIC_CHAT_STREAMING=false` to deliberately use the synchronous
`/chat` fallback.

## Commands

```bash
npm run dev        # local development
npm run lint       # ESLint
npm run typecheck  # TypeScript
npm test           # Vitest unit tests
npm run build      # production build
npm run e2e        # mocked Playwright smoke tests
```

## Architecture

- `app/api/auth/*` owns login, registration, logout, and current-user session
  handling.
- FastAPI access and refresh tokens are stored only in `httpOnly`, `SameSite`
  cookies. Auth responses sent to browser JavaScript never contain raw tokens.
- `app/api/backend/[...path]` is the authenticated same-origin proxy for
  feature APIs. It preserves JSON or multipart bodies, retries once after a
  successful refresh on `401`, and blocks direct proxying of auth endpoints.
- `middleware.ts` protects `/app/*` and preserves the requested destination in
  `next`.
- TanStack Query owns server state; Zod and React Hook Form own form
  validation; reusable UI primitives live in `src/components/ui`.
- Conversation and chat API functions live in `src/lib/api`; resource hooks
  and cache keys live with their features under `src/features`.
- Chat uses `/chat/stream` lifecycle events and only treats the post-commit
  `complete` event as canonical. A Stop action aborts in-flight streams without
  discarding the composer draft. Assistant Markdown is sanitized before
  rendering. Uploads are limited to five PDF, DOCX, TXT, MD, or HTML files of
  20 MB each.
- Histories with 80 or more messages use dynamically measured virtualization;
  shorter threads retain the simpler complete DOM for accessibility.
- Citation detail stays in a conversation-scoped TanStack cache after a chat
  response; after a full reload, citations appear only when event metadata
  actually contains them.
- HITL actions expose approve/reject controls with expiry handling and resume
  events. Rate-limit and token-quota errors remain distinct in the composer.
- Playwright smoke tests mock the BFF boundary and do not require FastAPI.
