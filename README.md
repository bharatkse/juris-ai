# ⚖️ Juris AI

**Legal research and contract review over real legal sources.**

Ask a question about Indian law and the system retrieves from a corpus of actual statutes to answer it, citing the retrieved sources. Share a contract's text and a contract-review agent analyzes its risks, ambiguities, and obligations. Outbound actions such as email or Slack are designed to require your explicit approval. Self-hosted, so your matters and documents stay on your own infrastructure.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![CI](https://github.com/bharatkse/juris-ai/actions/workflows/ci-server.yml/badge.svg)](https://github.com/bharatkse/juris-ai/actions/workflows/ci-server.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)

## Capabilities

- **Retrieval-backed legal research** — hybrid vector + keyword retrieval over the legal corpus, reranked for relevance, with an answer-quality gate that scores answers against the retrieved evidence
- **Contract review** — a dedicated contract agent analyzes contract text for risks, ambiguities, and obligations
- **Human-in-the-loop design for outbound actions** — calls to the email and Slack tools pause execution for a human approval decision (LangGraph interrupt/resume); only the user who made the request can approve, reject or edit it
- **PII redaction stage** — a Presidio-based output review with custom Indian ID recognizers (PAN, Aadhaar)
- **Tamper-proof audit trail** — every request and decision is logged in a way that can't be edited or deleted afterward, independent of your chat history
- **Usage controls** — per-user request rate limiting and a daily token-quota check
- **Streaming responses** — `POST /chat/stream` delivers answers over Server-Sent Events
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
| **2 — Manual configuration** | `cp server/env.example server/.env`, fill in every value yourself, then start the stacks with `./setup.sh --install` (compose files live under `docker/`) | Full control over configuration, or scripting your own install |

Developer setup (running from source, tests) or a cloud deploy (Terraform/AWS SAM)? See [`docs/server/`](docs/server/).

## Architecture

Under the hood, a multi-agent system plans, researches, and reasons before answering, with a privacy and safety review stage (harmful-content check, PII redaction) on generated responses; a response the review can't clear, including when the safety check itself can't complete, is regenerated once and otherwise replaced with a fixed refusal. Full technical breakdown: [`docs/server/architecture/overview.md`](docs/server/architecture/overview.md); per-component workflows live in `server/src/agentic/*/README.md` and `server/src/rag/README.md`.

## Repository Map

```text
juris-ai/
├── server/            # FastAPI backend -- source, tests, Poetry project
├── clients/           # Reserved for future first-party client apps (none yet)
├── docker/
│   ├── server/         # Backend app Docker Compose stack + Dockerfile
│   ├── dependencies/   # Postgres, Redis, Floci (local AWS emulator) stacks
│   ├── development/    # Ollama (local LLM), SearXNG, MCP stacks
│   ├── observability/  # OTel collector, Prometheus, Tempo, Grafana
│   └── clients/        # Reserved for future client Docker assets (none yet)
├── docs/
│   ├── server/         # Backend architecture, setup guides, API reference
│   └── clients/        # Reserved for future client docs (none yet)
├── iac/
│   ├── terraform/      # Multi-cloud IaC (AWS built and parity-tested; GCP/Azure are stubs)
│   └── cloud/          # AWS SAM/CloudFormation templates (original deploy path)
├── legal/              # Commercial licensing terms
├── sample_data/        # Sample legal acts (PDF)
├── tests/              # Repo-level tests (Claude Code hooks) -- `make test-root`
├── setup.sh           # Installer and stack lifecycle (install/reinstall/cleanup/uninstall)
└── Makefile           # Build, test, lint, migrate, deploy -- run `make help` from here
                       # Configuration template: server/env.example
```

## Data Processing & Privacy

Describes what the code actually does — not a legal privacy policy. If you deploy this for others, you own your own compliance obligations.

| What | Detail |
| --- | --- |
| LLM inference | **Groq** (`GROQ_API_KEY`) — chat messages + retrieved context, always on |
| Web search | **SearXNG** (self-hosted, `docker/development/`), which forwards queries to Google/Bing/Yahoo — only when the web-research tool runs. A Brave client exists but isn't wired in |
| Tracing | **LangSmith** — off by default; can include conversation content if enabled |
| PII redaction | Presidio-based, on generated output only; custom `IN_PAN`/`IN_AADHAAR` recognizers |
| Local data | Legal corpus is local public-domain PDFs (`sample_data/acts/`; the test/eval copy is `server/tests/datasets/rag/raw_datasets/`); local Ollama model runs on your own infra |
| Retention | No automatic deletion — conversations/events persist in Postgres until you remove them |
| Cross-conversation memory | Off by default (opt-in). When a user turns it on, short preference/profile facts they state are saved and reused in later conversations, sent to the LLM provider on every request that injects them; turning it off deletes them immediately. Unlike conversation history, saved memories DO expire automatically (sliding retention window). See [`docs/server/architecture/user-memory.md`](docs/server/architecture/user-memory.md) |

## Verification

| Area | Status |
| --- | --- |
| Compliance logging | Real, DB-trigger-enforced immutability on `compliance_log` — verified by e2e tests against a real Postgres instance |
| Streaming | `POST /chat/stream` is covered by end-to-end tests |
| Test suite | 1,388 unit tests passing (2026-09-23) · coverage via Codecov in CI |


## Contributing

- Backend: see [`server/CONTRIBUTING.md`](server/CONTRIBUTING.md).
- Clients: see [`clients/CONTRIBUTING.md`](clients/CONTRIBUTING.md).

## Community

- Found a bug or want a feature? Open a [GitHub Issue](https://github.com/bharatkse/juris-ai/issues).
- Want to contribute code? See [`server/CONTRIBUTING.md`](server/CONTRIBUTING.md) or [`clients/CONTRIBUTING.md`](clients/CONTRIBUTING.md), then open a pull request.

Nothing beyond GitHub exists yet — no Discord, Slack, or mailing list.

## License

AGPL-3.0-only — see [`LICENSE`](LICENSE). Need a proprietary/commercial license instead? See [`legal/COMMERCIAL-LICENSE.md`](legal/COMMERCIAL-LICENSE.md).
