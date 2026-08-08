"""How a model is named across the whole program.

One endpoint used to be one model. That worked as long as every entry in the
configuration pointed at a local server with exactly one model loaded — and
it broke the moment a cloud provider was added: OpenAI is one address with a
whole catalogue behind it, and choosing "the" model of that address has no
sensible answer.

So an endpoint is now the **provider**, and the model is named alongside it:

    openai:gpt-5.5          the provider `openai`, the model `gpt-5.5`
    anthropic:claude-opus-5 the provider `anthropic`, that model
    mana                    a provider that names no model of its own

The bare form stays valid on purpose. Chats and agents have the old ids
stored, and a local server that has exactly one model loaded has nothing to
add to its name anyway — it would be a colon and a repetition.

The separator is a colon because endpoint ids never contain one (they are
short handles like `mana` or `openai`), while model names regularly contain
dots, slashes and hyphens. Splitting at the FIRST colon therefore keeps model
names with colons intact.
"""

from __future__ import annotations

TRENNER = ":"


def bauen(endpunkt_id: str, modell: str | None) -> str:
    """The public id of one model at one provider."""
    if not modell:
        return endpunkt_id
    return f"{endpunkt_id}{TRENNER}{modell}"


def zerlegen(kennung: str) -> tuple[str, str | None]:
    """Splits a public id back into provider and model.

    Without a separator the whole string is the provider and there is no
    model — which is exactly what the old, still valid ids look like.
    """
    endpunkt_id, trenner, modell = kennung.partition(TRENNER)
    if not trenner:
        return kennung, None
    return endpunkt_id, modell or None
