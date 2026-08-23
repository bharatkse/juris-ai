"""
Examples used for capability classification.
"""

from src.core.enums import ActionTypeEnum

CAPABILITY_EXAMPLES: dict[
    ActionTypeEnum,
    tuple[str, ...],
] = {
    ActionTypeEnum.SEND: (
        "send the email",
        "send this email to the client",
        "send the contract to the client",
        "send the document to the client",
        "forward the document to the client",
        "forward this email",
        "email the client",
        "deliver the contract to the client",
    ),
}
