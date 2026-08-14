"""Does a picture still fit beside the language model that is loaded?

On a machine with one shared memory pool — which every Apple Silicon Mac
is — starting the image generator while a language model holds its weights
is not a question of taste. Either both fit, or the machine starts swapping
and a picture that would have taken thirty seconds takes ten minutes with
the fans up.

So the honest answer comes BEFORE the run, not as a crash during it. The
sum is deliberately crude: what the model server is holding right now, plus
the size of the image model file, plus a hand's width for everything the
run needs beyond its weights. A precise prediction is not possible here and
would only make the refusal look more authoritative than it is.

The reserve is what keeps this from being a lie in the other direction: a
check that fills the machine to the last byte says yes and then hangs.

**All of them, not one of them.** This program may hold several model
servers at once — the chat model, the embedding server, the guardian's own
small model — and each one is a real gigabyte of a shared pool. Asking only
the first of them turns the check into a lie in the dangerous direction: on
a 16 GB machine it adds four and six and two and a half, finds twelve and a
half, and says yes to a run that needs sixteen. So the sum is collected
rather than named, and that is what keeps a fifth server from being
forgotten the day it is added.
"""

from __future__ import annotations

# What the run needs on top of the model file: working memory for the
# denoising steps and the decoder, plus room for the rest of the system.
# Held as one number rather than a formula per resolution — the difference
# between 512 and 1024 pixels is small against the weights.
ZUSCHLAG_GB = 2.5


def _dinge(zustand) -> list:
    """Everything the application is holding, whatever it is called.

    Starlette keeps its state in an inner dictionary; a plain object keeps
    it in its own. Both are read here so a test can hand in something
    simple instead of building an application.
    """
    innen = getattr(zustand, "_state", None)
    if isinstance(innen, dict):
        return list(innen.values())
    try:
        return list(vars(zustand).values())
    except TypeError:
        return []


def gehaltene_gb(zustand) -> float:
    """What every running model server is holding right now, added up.

    Collected by asking, not by listing names. A list of runners would be
    right on the day it is written and wrong on the day the next server is
    added — and being wrong here means a machine brought to its knees rather
    than a sentence. Anything that can answer "how much am I holding" is
    counted; anything idle answers nothing and adds nothing.
    """
    summe = 0.0
    for ding in _dinge(zustand):
        frage = getattr(ding, "belegt_gb", None)
        if not callable(frage):
            continue
        try:
            belegt = frage()
        except Exception:  # noqa: BLE001 - a runner that cannot answer holds nothing knowable
            continue
        if isinstance(belegt, (int, float)):
            summe += float(belegt)
    return summe


def passt(gesamt_gb: float | None, belegt_gb: float, modell_gb: float) -> bool:
    """Whether an image model of this size still has room.

    Without a readable machine total the answer is yes: refusing on a
    number nobody could read would block the feature on every machine whose
    memory cannot be queried, which is the wrong side to err on for
    something the user asked for explicitly.
    """
    if not gesamt_gb:
        return True
    return belegt_gb + modell_gb + ZUSCHLAG_GB <= gesamt_gb


def fehlend_gb(gesamt_gb: float | None, belegt_gb: float, modell_gb: float) -> float:
    """How much is missing, for a message that says something useful."""
    if not gesamt_gb:
        return 0.0
    fehlt = belegt_gb + modell_gb + ZUSCHLAG_GB - gesamt_gb
    return round(max(0.0, fehlt), 1)
