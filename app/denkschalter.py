"""Asking a model to think, or not to.

Models that reason before they answer expose that as a chat-template flag,
and the flag only means anything where the template knows it. Sent blindly
it does not switch anything off — it lands in the rendered prompt as text,
which is worse than not asking.

So the decision lives here, once: the endpoint's own capability entry wins,
and where it says nothing the discovery's native detection decides. Two
callers need it and used to carry a copy each — the chat, where the user
flips the switch, and the picture-prompt rewrite, where thinking is always
unwanted because nobody reads it and it eats the token budget before the
prompt is written.
"""

from __future__ import annotations


def zusatz(thinking: bool | None, zustand) -> dict:
    """The extra request fields for the thinking switch, or nothing.

    ``None`` means the caller has no opinion — then nothing is sent and the
    model does whatever it does by default.
    """
    if thinking is None:
        return {}
    faehig = zustand.endpunkt.capabilities.thinking
    if faehig is None:
        faehig = bool(getattr(zustand, "thinking_erkannt", False))
    if not faehig:
        return {}
    return {"chat_template_kwargs": {"enable_thinking": thinking}}
