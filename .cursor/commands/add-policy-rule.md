# Add an RBAC policy rule

Rule: $ARGUMENTS

Two layers exist. Do not mix them.

## A. User + agent-action RBAC (`application/authorization/`)

1. If a new `ActionTypeEnum` is required, add it in `core/enums.py`.
2. `rbac/policy.py` `RBACPolicy.default()` — `agent_id → tool_name → frozenset[ActionTypeEnum]`.
3. **Both** paths must honor it:
   - `RBACService.check_intent()` — user role permissions from `DatabaseRolePermissionProvider`. If request-time should see this capability, add `CAPABILITY_EXAMPLES` (today only `SEND` is classified; otherwise `check_intent` never sees it).
   - `RBACService.check_action()` — user permission **and** `agent_action_allowed`.
4. Role seeds: `wiring/factories/roles.py` (`member` / `reader`). Create-if-missing — existing DB rows are not rewritten.
5. Tests: `tests/unit/application/authorization/rbac/test_resolver.py` and `test_execute_gate.py`; e2e `test_user_roles.py` if a role changes.

## B. Agent tool allow-list (`agentic/policy/`)

`AgentPolicyGuard.check_tool()` + `wiring/factories/agent_policies.py`. This is not RBAC. Gated sends still need `GATED_TOOLS` + `ApprovalLifecyclePolicy` (`SEND`).

## C. Approval

`ApprovalLifecyclePolicy._APPROVAL_REQUIRED_ACTIONS` is `SEND` only. Changing that is a product/security change; `ApprovalRecordVerifier` must still match payload.

Output a diff plan covering A–C as applicable, then implement if the user asked to apply.
