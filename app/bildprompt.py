"""Turning a written wish into a prompt an image model understands.

People describe the picture they want in their own language, and picture
models answer far more reliably to English — and to English of a particular
kind: concrete nouns, materials, light, lens, rather than a well-formed
sentence. Both of those are work the language model already loaded on this
machine can do in one pass, so it does it here instead of leaving the user
to translate and pad by hand.

Two rules the instruction below exists to enforce:

* The scene stays the scene. Expanding a prompt is adding detail to what
  was described, never inventing a different picture — a user who asked for
  a red bicycle and got a motorcycle has been given a worse tool than none.
* Only the prompt comes back. Models like to explain what they did; an
  explanation pasted into the prompt field would be drawn as if it were part
  of the picture.

The embedding model is deliberately not an option here. Embeddings produce
vectors, not text — the call goes to the ordinary chat interface of whatever
language model is loaded, and it never touches a chat history.
"""

from __future__ import annotations

from app.providers import ChatNachricht, Generierungsanfrage, Provider

# In English in the code and not in the translation catalogue: this is not
# interface text but part of the call, and the models answer best to it in
# the language it was written in.
ANWEISUNG = (
    "You rewrite prompts for a Stable-Diffusion image model. "
    "Translate the user's prompt to English and expand it into a vivid, "
    "concrete image prompt. Stay faithful to the described scene — do not "
    "invent a different subject. Add photographic detail: materials, "
    "lighting, colour, composition, lens. Write comma-separated phrases, "
    "not sentences. Return ONLY the prompt, with no preamble, no quotes and "
    "no explanation."
)

# Long enough for a rich prompt, short enough that a model which starts
# writing an essay is cut off rather than left running. The generous half of
# that room exists for thinking models whose thinking cannot be switched
# off: their deliberation is counted here too, and a budget that only fits
# the prompt itself would be spent before the prompt is written.
MAX_TOKENS = 600

# A prompt is a prompt, not a document. What arrives longer than this is a
# mistake somewhere upstream, and sending it would cost a full context.
MAX_EINGABE = 2000


class PromptFehler(Exception):
    """The model could not be asked, or said nothing usable."""


def _saeubern(text: str) -> str:
    """Strips what models wrap around an answer they were asked not to wrap.

    Quotes around the whole thing and a trailing full stop are the two that
    survive the instruction most often, and both would be drawn.
    """
    sauber = text.strip()
    # A fenced block first, and as a block: the loop below takes one
    # character off each side, so three backticks would leave two behind and
    # they would be drawn into the picture. The opening fence may carry a
    # language word, which belongs to the fence and not to the prompt.
    if sauber.startswith("```"):
        sauber = sauber[3:]
        if "\n" in sauber:
            erste, rest = sauber.split("\n", 1)
            if not erste.strip() or erste.strip().isalpha():
                sauber = rest
        if sauber.rstrip().endswith("```"):
            sauber = sauber.rstrip()[:-3]
        sauber = sauber.strip()
    for zeichen in ('"', "'", "`"):
        if len(sauber) > 1 and sauber.startswith(zeichen) and sauber.endswith(zeichen):
            sauber = sauber[1:-1].strip()
    return sauber.rstrip(".").strip()


async def verbessern(
    provider: Provider,
    modell: str | None,
    prompt: str,
    zusatz: dict | None = None,
) -> str:
    """Asks the loaded language model for an English version of ``prompt``.

    Streams and collects rather than waiting for a whole response, because
    that is the one way every provider in the house can be asked; the caller
    gets the finished text.
    """
    eingabe = prompt.strip()
    if not eingabe:
        raise PromptFehler("empty prompt")
    if len(eingabe) > MAX_EINGABE:
        raise PromptFehler("prompt too long")

    anfrage = Generierungsanfrage(
        nachrichten=[
            ChatNachricht(role="system", content=ANWEISUNG),
            ChatNachricht(role="user", content=eingabe),
        ],
        modell=modell,
        max_tokens=MAX_TOKENS,
        # Low but not zero: a prompt writer that always returns the same six
        # adjectives stops being useful on the second try.
        temperature=0.7,
        zusatz=zusatz or {},
    )

    stuecke: list[str] = []
    strom = provider.streamen(anfrage)
    try:
        async for stueck in strom:
            if stueck.sorte == "content":
                stuecke.append(stueck.text)
            elif stueck.sorte == "error":
                raise PromptFehler(stueck.text or "model error")
    finally:
        schliessen = getattr(strom, "aclose", None)
        if schliessen is not None:
            await schliessen()

    ergebnis = _saeubern("".join(stuecke))
    if not ergebnis:
        # A model that thought until the budget ran out is the common case
        # here, and it is still nothing to put in the field.
        raise PromptFehler("model returned nothing")
    return ergebnis
