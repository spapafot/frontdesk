from app.core.config import settings
from app.services.chat_service import get_client

_SUMMARY_SYSTEM = (
    "You summarize a customer support conversation for an internal admin log. "
    "Write 1-2 short, plain-text sentences describing what the customer wanted and "
    "the outcome. No markdown, no preamble, just the summary."
)


def _transcript(messages: list[dict]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            speaker = "Customer" if role == "user" else "Agent"
            lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


async def summarize_conversation(messages: list[dict]) -> str:
    """Generate a short plain-text summary of a conversation via DeepSeek."""
    transcript = _transcript(messages)
    if not transcript:
        return ""

    client = get_client()
    response = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": transcript},
        ],
        extra_body={
            "thinking": {"type": "enabled" if settings.deepseek_thinking else "disabled"}
        },
    )
    return (response.choices[0].message.content or "").strip()
