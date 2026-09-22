# Known issues

A current backlog of confirmed, open gaps between design and implementation —
for phase planning, not a changelog. Add an entry here instead of leaving a
finding only in a PR thread or a chat. When something is verified fixed,
remove its entry rather than marking it resolved — git history is the
changelog.

Last full audit: 2026-09-22 (every entry below was re-verified against
current code/docs on that date, not carried forward on trust).

---

## Memory feature — pre-production blockers

None of these block development; all block enabling memory for real users.
Full detail and the authoritative status table:
[`docs/server/architecture/user-memory.md`](server/architecture/user-memory.md)
(pre-ship checklist) — not duplicated in full here, only summarized for the
backlog view.

- **PII guard has recall gaps — the one marked "must fix," not just "tune."**
  A bare person name ("Advocate Sharma") is not reliably detected by the
  extraction content guard, so a client or counterparty name can be saved to
  a user's persistent memory; statute names are also wrongly flagged as
  organizations (over-blocking, not a leak). Identifier patterns (Aadhaar,
  PAN, IFSC, account numbers, email/UPI) are regex-hard-blocked and reliable
  — this is specifically a named-entity-recognition recall problem. Owner:
  `application/services/memory_content_guard.py` (two `xfail` tests pin both
  behaviors). **Size: medium-large** (a better NER model/config, not a
  rewrite of the guard's structure).
- **Retention window (`USER_MEMORY_RETENTION_DAYS = 120`) is a placeholder,
  not a legal determination.** Needs the confirmed period for the product's
  jurisdiction and matter types. Owner: `core/constants.py`. **Size: small**
  (a constant change once the number is known) but blocked on legal input,
  not engineering.
- **DPDP Act 2023 consent copy has not been written.** The API describes
  what turning memory on/off does in functional terms
  (`api/schemas/memory.py`) but not the actual legal consent notice (purpose,
  what is stored, how to withdraw). **Size: small** (product/legal copy, not
  code) but blocked on legal input.
- **`USER_MEMORY_MIN_SIMILARITY = 0.5` and `USER_MEMORY_MIN_EXTRACTION_CONFIDENCE
  = 0.6` are both uncalibrated guesses**, not tuned against real extracted
  memories or measured model probabilities. Too-low similarity injects
  irrelevant memory into prompts; too-high means memory silently never
  applies. Owner: `core/constants.py`. **Size: medium** (needs a real
  extraction-precision eval harness first — see next item).
- **No extraction-precision evaluation exists.** Nothing measures how often
  extraction saves something it shouldn't, or misses something it should.
  Deferred to Phase 2. **Size: medium.**
- **No account-deletion path exists, and `conversations.user_id` has no
  cascade.** `user_memories`'s FK is `ondelete="CASCADE"`
  (`adapters/persistence/sqlalchemy/models/user_memory.py`), but
  `conversations.user_id` is a bare `ForeignKey("users.id")` with no
  `ondelete` at all (`adapters/persistence/sqlalchemy/models/conversation.py`)
  — confirmed directly in both model files. A hard user delete is blocked
  while conversations exist; deactivating an account (`is_active = false`)
  does not delete memories either. This predates the memory feature but the
  feature makes it more visible (withdrawing memory consent *does*
  hard-delete memories in the same transaction — deleting the account itself
  does not). **Size: medium** (schema change + a real deletion path is a
  product decision, not just a migration).
- **No global kill-switch for the memory feature.** Verified: no
  `config/memory.py` exists, and the only "enabled" gating anywhere in
  `application/services/user_memory*.py` is the per-user `user.memory_enabled`
  flag — there is no environment-level flag to disable extraction/injection
  across an entire deployment regardless of per-user settings (e.g. for an
  incident response). **Size: small** (one settings flag + a check at the two
  write/read call sites).
- **Expired memories are only purged when their owner triggers it**
  (listing memories, or an extraction pass) — hidden from retrieval once
  expired, but not actually deleted until then. No scheduled job. Deferred to
  Phase 2. **Size: small** (a cron/scheduled task calling the existing
  `UserMemoryService.purge_expired`).
- **Memory content reaches third parties.** Saved facts are sent to the LLM
  provider on every request that injects them; if LangSmith tracing is
  enabled, prompt content (including the `<user_memory>` block) can flow into
  traces. Owner: `adapters/observability/langsmith.py`. **Size: small**
  (review + possibly a redaction/exclusion rule before enabling tracing in an
  environment where this matters).

---

## Architecture gaps (agentic / RAG)

Summarized here for the backlog view; full technical detail lives in each
package's own README, not duplicated below.

- **`Tool.execute() -> str` boundary loses structured per-result data** (title,
  per-chunk score, document id) for every `Tool`, capping citation/source
  quality across the whole agentic pipeline. Fixing it needs a change to the
  `Tool.execute()` contract itself, not a patch to one caller. Detail:
  `src/agentic/README.md` → Known gaps. Owner: `agentic/tools/base.py` +
  `agentic/tools/retrieval.py`. **Size: large** (contract change across every
  concrete `Tool`).
- **Tool-permission enforcement has one remaining bypass.** Agents hold a
  `RetrieverTool` instance directly (`agents/base.py._retrieve_context()`)
  rather than resolving it through the Tool Registry, with no policy check —
  still dead code (nothing calls it) as of this writing, but higher-risk than
  it looks now that real enforcement exists everywhere else it's reachable.
  Detail: `src/agentic/README.md` → Known gaps. Owner: `agentic/agents/base.py`.
  **Size: small** (delete the dead path, or route it through the registry if
  it's ever needed).
- **`AgentResponseDTO.usage` is never populated — real token usage never
  reaches `usage_records`.** `AgentResponseMapper.map()`
  (`agentic/execution/aggregation/mapper.py`) never sets `usage=`, even
  though the data already exists on `LLMResponseDTO.usage`. Verified still
  true (`usage` does not appear in `mapper.py` at all). Consequence: the
  daily token quota (`RATE_LIMIT_DAILY_TOKEN_QUOTA`) has never actually been
  fed by a real request, non-streaming or streaming. **Size: medium**
  (threading one field through `AgentState`/`AgentResponseMapper.map()` — the
  data exists one hop earlier already).
- **`CollaborationBus`/`DELEGATE` is unverified.** Real code path, zero real
  exercise — no test or production path drives an actual end-to-end
  delegation, and `DELEGATE` is currently unreachable in production anyway
  (`AgentPolicyGuard.check_delegation()` always denies). Detail:
  `src/agentic/README.md` → Known gaps. **Size: n/a** (needs a decision on
  whether to build this out or remove it, not a fix).
- **Citation-quality thresholds are uncalibratable from the current
  dataset.** `_evaluate_citations` (`agentic/evaluation/answer.py`) is exact
  set-membership (0.0 or 1.0 per case), so there's no continuous distribution
  to sweep a threshold over, unlike groundedness/relevance/correctness.
  **Size: medium** (needs a richer citation-quality dataset, not a code fix).
- **`rag/evaluation/models/quality_gate.py` is not wired into CI.** The gate
  exists and functions (used by `ragas_offline.py`), but nothing under
  `.github/workflows/` calls it. **Size: small.**
- **Ingestion never writes `url` into chunk metadata.** Not currently
  actionable — no web-sourced ingestion path exists yet, so there's nothing
  to populate it with. Flagged so a future web-sourced `DocumentSource`
  doesn't ship with the same silent gap. Owner: `rag/ingestion/`. **Size:
  n/a until a web ingestion path is built.**
- **Inline legislative amendment-marker brackets are an unhandled
  text-matching artifact class** (e.g. `"1[electronic\nsignature]"`
  mid-sentence in the IT Act corpus). See
  `rag/evaluation/metrics/text_matching.py`'s module docstring. **Size:
  small-medium** (corpus-specific normalization, deliberately not
  generalized yet — fix golden-dataset entries as they're hit, per that
  docstring's own guidance).

---

## Test infrastructure

### `make test-e2e`/`make test-smoke` run pytest directly on the host, and inherit the same compose-internal-hostname problem the alembic targets used to have — broader, not yet fixed

Verified still current: both targets still run
`$(IN_SERVER) $(PYTEST) tests/e2e ...` / `tests/smoke ...` directly
(`Makefile`), reading `server/.env`'s compose-internal hostnames. Unlike the
alembic fix, this needs more than one hostname resolved for the host
process: at minimum `DB_HOST` (Postgres), `REDIS_HOST` (Redis), and for
tests exercising the local model or tracing paths, `LLM_LOCAL_BASE_URL`
(Ollama) and the OTEL exporter endpoint.

The `docker compose exec api ...` pattern used for `alembic-*` is **not**
viable here: `tests/` is not bind-mounted into the `api` container (only
`src/` is), so mounting `tests/` plus the dev dependency group into what's
otherwise an app-serving container is a bigger, separate design change.

Working pattern today (used throughout this session's own test validation):
host-resolvable overrides passed only to the pytest invocation —
`DB_HOST=localhost`, `REDIS_HOST=localhost`,
`LLM_LOCAL_BASE_URL=http://localhost:11434`,
`OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` — without touching
`server/.env`'s own values (the `api` container still needs those).
Whoever picks this up: wire that override set into `test-e2e`/`test-smoke`
as Makefile variables with `localhost` defaults, applied only to those two
targets. Owner: `Makefile`. **Size: small-medium.**

---

## Tooling / environment setup

### `server/env.example` has drifted from what `setup.sh` and the compose files read

Verified still current against the live file:

1. **`JURIS_AI_VERSION` is unused** (line 24) — defined, comment claims it
   pins the released image, but no compose file, script, or code reads it;
   the API is built from the Dockerfile.
2. **Self-referencing header comment** (line 2) — says "Developing on the
   backend from source instead? Use `server/env.example`", but that *is*
   `server/env.example`.
3. **`DB_HOST`, `DB_NAME`, `DB_PORT`, `DB_USER`, `APP_DB_USER` are all still
   `CHANGE_ME`** with no generator or default — `setup.sh` only generates
   `SECRET_KEY`, `JWT_SECRET_KEY`, `DB_PASSWORD`, `APP_DB_PASSWORD`, and only
   rewrites `DB_HOST` when empty or `localhost`. A fresh `./setup.sh` install
   would leave `DB_HOST=CHANGE_ME` and fail to connect.

Owner: `setup.sh` and `server/env.example`. **Size: small.**

### Floci (local AWS emulator) has confirmed defects affecting Terraform/SAM deploys

Not a bug in this repo's own code — recorded so `make iac-apply`/
`make iac-destroy` users know what to expect. Two observed defects (more
exist but aren't written up here):

- **`UPDATE_ROLLBACK_FAILED` on an in-place `sam deploy` parameter update.**
  A `sam deploy` that only changes an unrelated template parameter can
  trigger Floci's CloudFormation engine to attempt an in-place replacement of
  `DBSecret` even though nothing about that resource changed, leaving the
  stack in `UPDATE_ROLLBACK_FAILED`. Workaround: `aws cloudformation
  delete-stack` / `sam delete --stack-name <name>`, then redeploy fresh.
- **`aws_api_gateway_integration`'s `timeout_milliseconds` is accepted on
  create, always read back as `0`, and rejects `PATCH` updates outright.**
  No known workaround; always destroy/recreate rather than incrementally
  `terraform apply` against an existing Floci-deployed api-gateway stack.

**Size: n/a** — not fixable in this repo; consider reporting upstream to
`floci-io/floci` if these keep recurring.

---

## Code quality

### `mypy` reports 114 errors on `server/src`, and nothing blocks on them

Freshly verified 2026-09-22 (`rm -rf .mypy_cache && poetry run mypy src/`,
so the count is a clean run, not a warm-cache artifact — the count has
previously been observed to vary slightly between warm-cache runs, worth
knowing if a future recheck looks off by a couple):

- **Result:** `Found 114 errors in 62 files (checked 434 source files)`.
- **By package:** adapters 28, agentic 25, application 19, api 17, rag 9,
  core 7, wiring 6, config 2, `main.py` 1.
- **By code:** `arg-type` 28, `attr-defined` 16, `no-any-return` 11,
  `import-untyped` 11 (ragas and scikit-learn ship no stubs), `override` 9,
  `redundant-cast` 5, `valid-type` 4, `union-attr` 4, `call-arg` 4, and 22
  spread across smaller codes.
- **Why nobody notices:** no workflow under `.github/` runs mypy — the only
  automatic check is the pre-commit mypy hook, configured for the
  `pre-push` stage. `pyproject.toml` also carries an unused override
  (`fitz.*`) that mypy warns about on every run.
- **Worth a look first:** `src/main.py:116` (`"Redis[bytes]" has no
  attribute "aclose"`) may be a real runtime mismatch at shutdown, not only
  a typing complaint. Not investigated.

Owner: nobody yet — not triaged. **Size: medium** to get a baseline wired
into CI; **large** to actually drive the count toward zero. Suggested order:
add stubs/overrides for the 11 untyped imports, fix the cheap groups
(`redundant-cast`, `override`), then wire mypy into CI with a baseline so
the count can only go down from here.

---

## Documentation gaps

### `application/`, `api/`, `adapters/`, `core/`, `wiring/` have zero module-level documentation

Verified: no README.md or CLAUDE.md anywhere under these five directories —
`adapters/` alone (96 files: DB, LLM/MCP/search/storage clients, security,
observability) is the largest undocumented surface in the repo. The only
description of any of them is `claude.md`'s one-row-per-layer table (and
that file is gitignored, so it isn't available outside this machine either).
`agentic/` has its own package-level docs (`README.md`, `CLAUDE.md`,
`tools/README.md`) plus one submodule README so far
(`agentic/execution/README.md`) — the remaining `agentic/` submodules
(`planning/`, `orchestration/`, `agents/`, `policy/`, `guardrails/`,
`registry/`, `decisions/`, `evaluation/`) and a RAG doc split
(ingestion/retrieval/evaluation) are drafted as a proposal, not yet built.
**Size: large** (five whole layers with no onboarding doc at all); the
`agentic/`/`rag/` completion is separately scoped and already proposed.
