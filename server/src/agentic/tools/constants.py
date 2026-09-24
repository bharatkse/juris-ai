PDF_CONTENT_TYPE = "application/pdf"

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument." "wordprocessingml.document"

TEXT_CONTENT_TYPE = "text/plain"

MARKDOWN_CONTENT_TYPE = "text/markdown"

# Tools whose TOOL_CALL must never execute immediately -- a human must
# approve first. Both are side-effecting, externally-visible sends
# (Slack post, email send); read operations on the same tools stay
# ungated (see GatedMCPTool). Checked by tool name at the decision ->
# action boundary (agents/runtime/execution.py) and enforced by
# AgentContinuationService pausing on a real TOOL_CALL to one of these
# via LangGraph's interrupt() rather than executing it -- see
# continuation.py's TOOL_CALL branch.
GATED_TOOLS: frozenset[str] = frozenset({"email", "slack"})
