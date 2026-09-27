from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.enums import MessageRoleEnum


def build_conversation(
    *,
    messages: list[MessageDTO] | None = None,
    metadata: dict[str, object] | None = None,
) -> ConversationDTO:
    return ConversationDTO(
        messages=tuple(
            messages
            or [
                MessageDTO(
                    role=MessageRoleEnum.USER,
                    content="Hello",
                ),
            ],
        ),
        metadata=metadata or {},
    )
