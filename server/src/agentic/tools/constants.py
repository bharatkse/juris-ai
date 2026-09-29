PDF_CONTENT_TYPE = "application/pdf"

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument." "wordprocessingml.document"

TEXT_CONTENT_TYPE = "text/plain"

MARKDOWN_CONTENT_TYPE = "text/markdown"

# Tools whose TOOL_CALL must never execute immediately -- a human must
# approve first. Both are side-effecting, externally visible sends; the
# read tools on the same services (email, slack) are separate and
# ungated. Checked by tool name at the decision -> action boundary
# (agents/runtime/execution.py tags these SEND) and enforced by
# AgentContinuationService pausing on a TOOL_CALL to one of them via
# LangGraph's interrupt() rather than executing it (continuation.py). The
# tools themselves also refuse to run without a verified approval token
# (tools/messaging/base.py, GatedMCPTool).
GATED_TOOLS: frozenset[str] = frozenset({"email_send", "slack_post"})
