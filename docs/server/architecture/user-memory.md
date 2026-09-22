# User Memory

Durable, per-user facts that persist **across conversations**: working preferences and professional-profile details the user has stated about themselves (for example "prefers concise answers", "practises before the Delhi High Court").

This is **not** the conversation's rolling summary. That summary lives on one `Conversation` row and is only ever read back into that same conversation. User memory is a separate table (`user_memories`) keyed by user.

Phase 1 is deliberately narrow: user-level preference/profile memory only. There is no matter or client scoping, because no matters model exists yet.

---

## Pre-ship checklist / known issues

Do not enable memory for real users until each of these is resolved. Development is not blocked on them.

| # | Item | Status | Where |
| :-: | ---- | ------ | ----- |
| 1 | **Retention window is a placeholder.** 120 days from last use, not a legal determination. Needs the confirmed period for the product's jurisdiction and matter types. | **Needs legal input** | `USER_MEMORY_RETENTION_DAYS` in `core/constants.py` (the only place it is defined) |
| 2 | **Consent copy.** The API describes what turning memory on/off does in plain terms, but the actual consent notice (DPDP Act 2023: purpose, what is stored, how to withdraw) has not been written. | **Needs legal input** | UI / product copy; API text in `api/schemas/memory.py` is functional description only |
| 3 | **`USER_MEMORY_MIN_SIMILARITY = 0.5` is uncalibrated.** BGE-style embeddings score even unrelated short texts well above zero, so this value is a guess. It has not been tuned against real extracted memories. Too low injects irrelevant memory into prompts; too high means memory silently never applies. | **Tune before production** | `core/constants.py` |
| 4 | **`USER_MEMORY_MIN_EXTRACTION_CONFIDENCE = 0.6` is uncalibrated.** Model-stated confidence is not a measured probability. | Tune before production | `core/constants.py` |
| 5 | **No extraction-precision eval.** Nothing measures how often extraction saves something it should not, or misses something it should. `MEMORY_EXTRACTION_MODEL` defaults to the cheaper summarization model without validation. | Deferred to Phase 2 | `config/llm.py` |
| 6 | **The PII guard's missed-name / statute-misclassification problem.** Measured on real sentences: a bare person name ("Advocate Sharma") was **not** detected, meaning a client or counterparty name can be extracted and stored; statute names ("Indian Contract Act 1872") are wrongly flagged as organizations and rejected (over-blocking, not a leak). Identifier patterns (Aadhaar, PAN, IFSC, account numbers, email/UPI) are hard-blocked by regex and are reliable. The extraction prompt (which forbids names) and the user's ability to view and delete every memory are the only other controls on the missed-name path. | **Must fix before extraction runs against real conversations** -- a missed name is a real leak in this domain, not a cosmetic gap. Recall improvement (a better NER model/config, not a rewrite of this guard's structure) is its own piece of work, out of scope for the wiring done in this session. | `application/services/memory_content_guard.py` (two `xfail` tests pin both behaviours) |
| 7 | **Expired memories are only purged when their owner triggers it** (listing memories, or an extraction pass). Until then they are hidden from retrieval and the list but still stored. There is no scheduled job. | Deferred to Phase 2 | `UserMemoryService.purge_expired` |
| 8 | **No account-deletion path exists in the codebase.** The `user_memories` foreign key cascades, but `conversations.user_id` has **no** `ON DELETE CASCADE` at the database level, so a hard user delete is blocked while conversations exist. Any future deletion path must remove conversations first. Deactivating an account (`is_active = false`) does not delete memories. | Gap, not built | schema / product decision |
| 9 | **Memory content reaches third parties.** Saved facts are sent to the LLM provider on every request that injects them. If LangSmith tracing is enabled, prompt content (including the `<user_memory>` block) can flow into traces. Not changed in this work. | Review before enabling tracing | `adapters/observability/langsmith.py` |
| 10 | **Existing rolling-summary behaviour (unchanged):** a summary is injected as a history message, so `fit_to_budget` drops it first under token pressure. Noted because user memory deliberately avoids this pattern. | Pre-existing, not changed | `application/services/chat.py` |

---

## Behaviour that is deliberate

- **Opt-in, default off.** `users.memory_enabled` defaults to false. Nothing is extracted or injected until the user turns it on. Only messages sent **after** consent was granted are ever read.
- **Withdrawing consent hard-deletes everything**, in the same transaction as the flag change. It cannot be undone.
- **The per-conversation "don't remember this" switch suppresses both writing and injection**, forward-only. While it is on for a conversation: nothing said from then on is saved, AND `UserMemoryService.retrieve_for_prompt` returns nothing for that conversation even if the user has other memories that would otherwise match -- same check (`is_enabled_for_conversation`), same short-circuit pattern as the account-level consent check above, not a separate code path. It does **not** delete facts already saved from earlier messages, in that conversation or any other. To remove those, delete them from the memory list, or turn memory off entirely. Turning the switch back off moves the extraction watermark to now, so nothing said while it was on is ever read later.
- **Only the user's own messages are ever sent to the extraction model.** Never assistant output, tool output, retrieved documents or web content, so none of those can write to a user's persistent memory.
- **The compliance log records identifiers, counts and a content hash only.** It is insert-only and retained indefinitely by default, so memory text written there could never be erased. `ComplianceLogService.record_memory_operation` has no parameter that could carry text.
- **Tenant isolation is structural.** Every `UserMemoryRepository` method requires a keyword-only `user_id`, all queries start from one scoped statement, and a test fails if a method without `user_id` is ever added.

## Database privileges

The migration issues no `GRANT`. The restricted runtime role gets access to new tables from the per-database `ALTER DEFAULT PRIVILEGES` set up by the role bootstrap (`docker/dependencies/init/postgres/_create_app_role.lib`, run by `01-create-app-role.sh` on a new volume or `scripts/bash/setup_app_role.sh` on an existing one). A database created outside that bootstrap gives the app role no access to **any** table; run `setup_app_role.sh` there rather than changing a migration.

## Deferred to Phase 2

- Matters model and matter-scoped memory (the `scope_type` CHECK constraint currently allows only `user`).
- Consolidation and scheduled expiry job.
- Extraction-precision evaluation (see items 3-6 above).
