# User Memory

Durable, per-user facts that persist **across conversations**: working preferences and professional-profile details the user has stated about themselves (for example "prefers concise answers", "practises before the Delhi High Court").

This is **not** the conversation's rolling summary. That summary lives on one `Conversation` row and is only ever read back into that same conversation. User memory is a separate table (`user_memories`) keyed by user.

Phase 1 is deliberately narrow: user-level preference/profile memory only. There is no matter or client scoping, because no matters model exists yet.

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

## Scope

Matter-scoped memory is out of scope for Phase 1: the `scope_type` CHECK constraint allows only `user`.

---

Known architecture and security gaps are tracked privately by the maintainers.
