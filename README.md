# ⚖️ Juris AI

**Legal research and contract review, grounded in real sources — not model guesswork.**

Ask a question about Indian law and get an answer backed by actual statutes and case law, with citations you can check. Hand over a contract and get its risks, ambiguities, and obligations flagged in plain language. Anything that reaches outside the system — sending an email, posting to Slack — waits for your explicit approval first. Self-hosted, so your matters and documents stay on your own infrastructure.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![CI](https://github.com/bharatkse/juris-ai/actions/workflows/ci-server.yml/badge.svg)](https://github.com/bharatkse/juris-ai/actions/workflows/ci-server.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)

## Capabilities

- **Grounded legal research** — answers backed by real source documents with citations, not model guesswork (hybrid vector + keyword retrieval, reranked for relevance)
- **Contract review** — risks, ambiguities, and obligations flagged in plain language, with the relevant clause quoted alongside each finding
- **Human approval before anything leaves the system** — sending an email or posting to Slack pauses for your sign-off; it never happens automatically
- **Privacy-aware by default** — personal information, including Indian ID numbers, is automatically redacted from generated answers before you see them
- **Tamper-proof audit trail** — every request and decision is logged in a way that can't be edited or deleted afterward, independent of your chat history
- **Usage controls built in** — per-user rate limits and daily quotas out of the box
- **Live, streaming answers** — text appears as it's generated, without ever streaming content that a later safety check would redact or block
- **Ready for real cloud deployment** — Terraform and AWS SAM/CloudFormation paths, both tested against a local AWS emulator before you touch real infrastructure

## 🚀 Quick Start

```bash
git clone https://github.com/bharatkse/juris-ai.git && cd juris-ai
./setup.sh
```

First run builds the image locally (a few minutes) — this will switch to a fast image pull once the first versioned release is published. `setup.sh` generates real secrets, prompts only for your `GROQ_API_KEY` ([get one here](https://console.groq.com/keys)), and waits for a real health check before printing the URL.

- Swagger UI: http://localhost:8001/docs

## Deployment Tiers

| Tier | What | Best for |
| --- | --- | --- |
| **1 — `setup.sh`** (Quick Start above) | Auto-generates secrets, prompts only for `GROQ_API_KEY`, waits for a real health check | Just want it running |
| **2 — Manual `docker compose`** | `cp env.example .env`, fill in every value yourself, then `docker compose up -d --build` | Full control over configuration, or scripting your own install |

Developer setup (running from source, tests) or a cloud deploy (Terraform/AWS SAM)? See [`docs/server/`](docs/server/).

## Architecture

Under the hood, a multi-agent system plans, researches, and reasons before answering, with every generated response passing through a privacy and safety review before it reaches you. Full technical breakdown: [`docs/server/architecture/overview.md`](docs/server/architecture/overview.md).

## Repository Map

```text
juris-ai/
├── server/            # FastAPI backend -- source, tests, Poetry project
├── clients/           # Reserved for future first-party client apps (none yet)
├── docker/
│   ├── server/         # Backend Docker Compose stacks (dev, local AWS emulation, observability)
│   └── clients/        # Reserved for future client Docker assets (none yet)
├── docs/
│   ├── server/         # Backend architecture, setup guides, API reference
│   └── clients/        # Reserved for future client docs (none yet)
├── iac/
│   ├── terraform/      # Multi-cloud IaC (AWS built and parity-tested; GCP/Azure are stubs)
│   └── cloud/          # AWS SAM/CloudFormation templates (original deploy path)
├── legal/              # Commercial licensing terms
├── docker-compose.yml   # Release bundle: run Juris AI (builds from source until first GHCR publish)
├── setup.sh           # Release-flow installer -- see Quick Start above
├── Makefile           # Build, test, lint, migrate, deploy -- run `make help` from here
└── env.example          # Release-flow configuration template
```

## Data Processing & Privacy

Describes what the code actually does — not a legal privacy policy. If you deploy this for others, you own your own compliance obligations.

| What | Detail |
| --- | --- |
| LLM inference | **Groq** (`GROQ_API_KEY`) — chat messages + retrieved context, always on |
| Web search | **Brave Search** — only when the web-research tool runs |
| Tracing | **LangSmith** — off by default; can include conversation content if enabled |
| PII redaction | Presidio-based, on generated output only; custom `IN_PAN`/`IN_AADHAAR` recognizers |
| Local data | Legal corpus (`raw_datasets/`) is local public-domain text; local Ollama model runs on your own infra |
| Retention | No automatic deletion — conversations/events persist in Postgres until you remove them |
| Cross-conversation memory | Off by default (opt-in). When a user turns it on, short preference/profile facts they state are saved and reused in later conversations, sent to the LLM provider on every request that injects them; turning it off deletes them immediately. Unlike conversation history, saved memories DO expire automatically (sliding retention window). See [`docs/server/architecture/user-memory.md`](docs/server/architecture/user-memory.md) |

## Audit Status

| Area | Status |
| --- | --- |
| Compliance logging | Real, DB-trigger-enforced immutability on `compliance_log` — verified by e2e tests against a real Postgres instance |
| Security | `python-jose` transitive-dependency gap found and fixed; verified end-to-end (login, JWT validation, tampered-token rejection) |
| Streaming | `POST /chat/stream` works — guardrail-aware (redacted/blocked content is never streamed) — verified by e2e tests |
| Known production gaps | No real `ENVIRONMENT=production` path · `DB_SECRET_ARN` unused by the app · 6 documented Floci emulator defects + 1 CloudFormation template defect |
| Test suite | 1,219 passing (unit/e2e/smoke) · 2 known gaps tracked, not hidden · coverage via Codecov in CI |

Full detail and owners: [`docs/known-issues.md`](docs/known-issues.md).

## Contributing

- Backend: see [`server/CONTRIBUTING.md`](server/CONTRIBUTING.md).
- Clients: see [`clients/CONTRIBUTING.md`](clients/CONTRIBUTING.md).

## Community

- Found a bug or want a feature? Open a [GitHub Issue](https://github.com/bharatkse/juris-ai/issues).
- Want to contribute code? See [`server/CONTRIBUTING.md`](server/CONTRIBUTING.md) or [`clients/CONTRIBUTING.md`](clients/CONTRIBUTING.md), then open a pull request.

Nothing beyond GitHub exists yet — no Discord, Slack, or mailing list.

## License

AGPL-3.0-only — see [`LICENSE`](LICENSE). Need a proprietary/commercial license instead? See [`legal/COMMERCIAL-LICENSE.md`](legal/COMMERCIAL-LICENSE.md).
