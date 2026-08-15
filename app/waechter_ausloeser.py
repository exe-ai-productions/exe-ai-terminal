"""When a step has gone wrong badly enough to be worth a second thought.

This is the cheap half of the guardian: plain code, no model, no reading
along. It looks at a tool call that has just finished and answers one
question — did this fail in a way a person would want a suggestion for?

Reading along would mean asking a model after every step whether anything
looks off. That is a second inference per tool call for a question that is
almost always answered "no", and it would make every run slower and
warmer for the sake of the rare case. A trigger costs nothing until it
fires.

The catalogue is deliberately short. Five kinds of failure carry enough
information for a useful correction to be written from them:

    befehl_gescheitert   a command came back with a non-zero exit code
    aufruf_abgelehnt     the call was refused, or the confirmation was not given
    zeit_abgelaufen      a run was still going when its time ran out
    aenderung_verfehlt   an edit found no place to apply, or too many
    datei_unlesbar       a file could not be read at all

Everything else — a search with no hits, a model that answers badly — is
not a failed step but a disappointing one, and a suggestion there would be
guessing.

The texts matched below are the tools' own English messages, not
translated ones. That is why they can be matched at all: what the user
sees in their language is built one layer further out, and matching that
would break the moment somebody switched language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BEFEHL_GESCHEITERT = "befehl_gescheitert"
AUFRUF_ABGELEHNT = "aufruf_abgelehnt"
ZEIT_ABGELAUFEN = "zeit_abgelaufen"
AENDERUNG_VERFEHLT = "aenderung_verfehlt"
DATEI_UNLESBAR = "datei_unlesbar"

# How much of a result travels on. Enough for the failure to be visible,
# short enough that a wall of build output cannot push the actual request
# out of the model's context.
# The ceilings below decide how large a finding can get, and the guardian's
# context window (`waechter.KONTEXT`) is sized from exactly that sum.
# RAISING ONE OF THEM MEANS RAISING THE WINDOW — otherwise a long finding is
# cut off in the middle on its way to the model, and the suggestion answers
# half a report. The arithmetic stands at the top of `app/waechter.py`.
ERGEBNIS_GRENZE = 800

# The same reasoning for the two things that come from OUTSIDE the tool: the
# request the user typed, and the arguments the model passed. Neither has a
# length limit of its own — a failed `edit_file` carries whatever `old_text`
# it tried, which can be a whole file. Unbounded, that would land in the
# guardian's prompt and cost minutes of prompt processing for one sentence
# of advice.
AUFTRAG_GRENZE = 600

# Per argument, and then over all of them together. Both are needed and for
# different reasons: one long value must not push out the short ones next to
# it, and twenty short ones must not add up past the window either. A single
# ceiling can only ever do one of the two.
ARGUMENT_GRENZE = 400
ARGUMENTE_GRENZE = 1200

# Names are cut too. Short by nature — but the model writes them, and
# something the model writes has no length this code knows.
SCHLUESSEL_GRENZE = 60

# Room kept free inside ARGUMENTE_GRENZE for the note that says how many
# arguments did not fit, so the total holds even when the note is added.
UEBERZAEHLIG = "…"
MARKE_RESERVE = 24

# The tool name, for the same reason: it comes out of the model's call, not
# out of our registry, and a call that named itself with a kilobyte would
# otherwise carry that kilobyte into the report.
WERKZEUG_GRENZE = 60

# Why a refused call was refused — one sentence naming a path, not a value
# the model wrote. ARGUMENT_GRENZE would fit it with room to spare, but a
# ceiling this generous is sized for what a call carries, and the window
# arithmetic in app/waechter.py counts every ceiling on the report — a
# reason this loose would spend budget the two new lines do not need.
GRUND_GRENZE = 160

_EXIT_CODE = re.compile(r"\[exit code (-?\d+)\]\s*$")
# The exit code is anchored at the END of the result: the shell tool appends
# it as the last thing it writes. Searched loosely, a successful
# `cat build.log` over a log that mentions an exit code would report itself
# as a failed step.
# The stop text cannot be end-anchored the same way — the tool writes an
# advice line AFTER it ("start it with background set to true"), so a $
# would never hold. It is anchored at the START instead, and over the whole
# first sentence: the stop text is the entire result when a run is cut off,
# while a result that merely quotes the sentence mid-text stays quiet.
_ABGELAUFEN = re.compile(r"^Stopped after \d+ seconds — the command was still running\.")
_SCHALE = "run_command"
_AENDERUNG = ("old_text was not found in", "old_text appears")
_UNLESBAR = ("is a binary file", "does not exist.", "could not be read (")


@dataclass(frozen=True)
class Befund:
    """One failed step, packed up small enough to think about.

    ``auftrag`` is the last thing the user asked for. Without it a
    suggestion could only ever repair the command; with it, the guardian
    can propose the step that was actually meant.

    ``grund`` is why a refused call was refused — the sentence the
    confirmation box itself showed, in English. ``ergebnis`` for a refusal
    only ever says a tool was "not allowed"; without the reason the
    guardian cannot tell a call refused for reaching outside the shared
    folders from one refused for any other reason, and proposes the one
    fix that is never right — asking for the permission again.
    """

    art: str
    werkzeug: str
    ergebnis: str
    auftrag: str = ""
    argumente: dict[str, Any] = field(default_factory=dict)
    grund: str = ""


def pruefen(
    *,
    name: str,
    ergebnis: str,
    fehlgeschlagen: bool = False,
    abgelehnt: bool = False,
    argumente: dict[str, Any] | None = None,
    auftrag: str = "",
    grund: str = "",
) -> Befund | None:
    """The whole catalogue, in the order the cases exclude each other.

    Returns the finding, or None when this step is not worth a thought.
    """
    text = ergebnis or ""
    art = _art(name, text, fehlgeschlagen, abgelehnt)
    if art is None:
        return None
    return Befund(
        art=art,
        werkzeug=str(name)[:WERKZEUG_GRENZE],
        ergebnis=text[:ERGEBNIS_GRENZE],
        auftrag=(auftrag or "")[:AUFTRAG_GRENZE],
        argumente=_gekuerzte_argumente(argumente),
        grund=(grund or "")[:GRUND_GRENZE],
    )


def _wert_kuerzen(wert: Any) -> Any:
    """One argument value, short enough to travel — whatever type it is.

    The first build cut only strings, and only strings. A list of two
    thousand paths, a nested object, a number with four hundred digits: all
    of those went into the guardian's prompt at full length, because none of
    them is a ``str``. What is measured here is therefore the value AS IT
    WILL BE WRITTEN, which is what the prompt costs.

    A value that fits keeps its own type — a number stays a number and reads
    as one. Only one that had to be cut becomes text, because a cut number
    is not a number any more and pretending otherwise would be a lie about
    what was passed.
    """
    text = wert if isinstance(wert, str) else str(wert)
    if len(text) <= ARGUMENT_GRENZE:
        return wert
    return text[:ARGUMENT_GRENZE] + "…"


def _gekuerzte_argumente(argumente: dict[str, Any] | None) -> dict[str, Any]:
    """Arguments, cut value by value and then bounded as a whole.

    Values are shortened one by one rather than the whole thing at once:
    which argument was passed matters for the suggestion, the last five
    hundred lines of one of them do not.

    The sum is bounded on the RENDERED dictionary, not on the values added
    up, because the rendering is what reaches the model — the braces, the
    quotes and the names between them are characters in the prompt like any
    other. Arguments that no longer fit are dropped from the back and
    counted, so the report says that something is missing rather than
    quietly showing a shorter call than the one that was made.
    """
    gekuerzt: dict[str, Any] = {}
    weggelassen = 0
    for name, wert in (argumente or {}).items():
        kandidat = dict(gekuerzt)
        kandidat[str(name)[:SCHLUESSEL_GRENZE]] = _wert_kuerzen(wert)
        if len(str(kandidat)) > ARGUMENTE_GRENZE - MARKE_RESERVE:
            weggelassen += 1
            continue
        gekuerzt = kandidat
    if weggelassen:
        gekuerzt[UEBERZAEHLIG] = f"{weggelassen} more"
    return gekuerzt


def _art(name: str, text: str, fehlgeschlagen: bool, abgelehnt: bool) -> str | None:
    # A refusal comes first: nothing ran, so nothing else can have gone
    # wrong, and the text carrying it is a translated one anyway.
    if abgelehnt:
        return AUFRUF_ABGELEHNT
    # The next two are the shell tool's own last line — and only the shell
    # tool's. Any other tool carrying those words is quoting, not failing.
    if name == _SCHALE:
        if _ABGELAUFEN.match(text.strip()):
            return ZEIT_ABGELAUFEN
        treffer = _EXIT_CODE.search(text.strip())
        if treffer and treffer.group(1) != "0":
            return BEFEHL_GESCHEITERT
    # The remaining two only count as failures when the tool said so. The
    # same sentence can appear inside a file somebody asked to read, and a
    # successful read of it is not a failed step.
    if not fehlgeschlagen:
        return None
    if any(marke in text for marke in _AENDERUNG):
        return AENDERUNG_VERFEHLT
    if any(marke in text for marke in _UNLESBAR):
        return DATEI_UNLESBAR
    return None
