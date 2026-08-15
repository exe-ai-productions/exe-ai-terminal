"""The guardian: one suggestion for a step that failed.

The trigger catalogue (``app/waechter_ausloeser.py``) decides in plain code
THAT something went wrong. This is what happens next: the finding is packed
up, the model that is already loaded is asked once, and what comes back is
offered in the panel — a corrected instruction, one click away from being
sent.

Three decisions are built in and worth reading before changing anything:

* **Its own server, never the chat's model.** The question goes to the small
  model on 127.0.0.1 that Extended Workflow starts (``app/eewserver.py``) and
  nowhere else. A finding carries the failed command, its arguments and the
  folders this chat has released — switching on a LOCAL guardian and then
  seeing all of that leave the machine because the chat happened to be on a
  cloud provider is the one outcome this feature must not have. When that
  server is not up there is no suggestion, and it is said so; there is no
  quiet second choice.
* **After the run, not during it.** A local server has one slot. Asking it
  something while it is still streaming the answer would put the guardian's
  question in a queue in front of the user's own answer. The finding
  appears the moment it happens; the suggestion catches up seconds later.
* **It offers, it never acts.** Everything here ends in a panel entry. What
  gets sent, gets sent by a hand.

The findings live in memory only. They belong to a run that just happened;
after a restart there is nothing left to correct, and a stored suggestion
would be advice about a situation that no longer exists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Any

from app import denkschalter
from app.providers import ChatNachricht, Generierungsanfrage
from app.waechter_ausloeser import (
    ARGUMENTE_GRENZE,
    AUFTRAG_GRENZE,
    BEFEHL_GESCHEITERT,
    ERGEBNIS_GRENZE,
    GRUND_GRENZE,
    WERKZEUG_GRENZE,
    Befund,
)

log = logging.getLogger(__name__)

# What the model is asked. English and fixed in the code: this is not an
# interface text but an instruction to a machine, and it has to read the
# same whatever language the window is set to.
# The last sentence about the shell says the same thing as the tools block in
# app/grundprompt.py — deliberately, and it has to stay that way: this prompt
# repairs what that one failed to prevent, and two prompts that disagree about
# the machinery teach the model twice and correctly once.
# WHOEVER CHANGES ONE READS THE OTHER.
ANWEISUNG = (
    "A step the assistant took has failed. Everything needed to fix it is in "
    "the report below. Write the ONE instruction the user should send next so "
    "the assistant gets it right. Name the concrete command, path or text from "
    "the report. Never repeat the call that just failed. No 'check' or 'make "
    "sure'. One sentence, imperative, no greeting, no explanation, no quotes. "
    "Each command runs in its own shell; activation does not carry over."
)

# At most this many suggestions per request from the user. The guardian is
# meant to catch the one step that went wrong, not to comment on a run that
# is falling apart — after two, a person needs to look, not a third
# suggestion.
JE_AUFTRAG = 2

# A suggestion is one sentence. This ceiling is what keeps a model that
# starts explaining itself from filling the panel with an essay.
VORSCHLAG_GRENZE = 400

# How many folders travel, as characters of the joined list. The released
# folders have no ceiling of their own — a chat may hold a dozen of them and
# a path may be any length — and without one they are the single unbounded
# thing in an otherwise measured request. Whole entries are dropped rather
# than a path being cut in half: half a path is a folder that does not exist,
# and naming one is worse than naming none.
ORDNER_GRENZE = 400

# Room for the answer. Twice what `VORSCHLAG_GRENZE` allows through, and no
# more: the generous 700 of the first build was reserve for a model that
# thinks before it speaks, and thinking is off. Reserve that is never used
# still has to be held free in the context window.
ANTWORT_GRENZE = 200

# --- How the window is sized ----------------------------------------------
#
# Everything the request can carry is bounded, and the window is the sum of
# those bounds. The parts, in characters:
#
#     ANWEISUNG (the system message)                       431
#     the labels around the fields, plus newlines          100
#     tool name          WERKZEUG_GRENZE                    60
#     the user's request AUFTRAG_GRENZE                    600
#     the arguments      ARGUMENTE_GRENZE                 1200
#     the result         ERGEBNIS_GRENZE                    800
#     the refusal reason GRUND_GRENZE                       160
#     released folders   ORDNER_GRENZE                      400
#     the .venv marker   len(UMGEBUNGSMARKE)                 34
#                                                    ---------
#                                                         3785
#
# This sum is a conservative envelope, not a reachable finding: the refusal
# reason rides a refused call, the .venv marker rides a failed command, and
# the 60-char tool name rides a tool that is not the shell — no single
# finding carries all three. Summing them anyway is deliberate: the window
# must hold whichever combination shows up, and the cheapest way to be sure
# is to hold the sum of all of them.
#
# NOT in the sum, and worth saying because it is the usual reason a window
# this size is too small: no conversation history, and no tool descriptions.
# This request is two messages and is handed no tools at all.
#
# Characters become tokens at the ratio below. Byte-level BPE gives about
# four characters per token on English prose, about three on paths and JSON,
# and about two on dense log output and non-ASCII text — so two is taken as
# the floor for the mixture a finding actually carries, not the average, and
# it is the number the rest of this code computes with (ZEICHEN_JE_TOKEN).
#
#     3785 / 2 = 1893 tokens of report
#         + 64 tokens for what the chat template wraps around two messages
#         + 200 tokens of answer (ANTWORT_GRENZE)
#         = 2157 tokens
#
# That is the honest worst case, and it would fit a 2560 window with room.
# The window is held at 4096 for one reason worth stating plainly rather than
# dressing up: the two-per-character ratio is a floor, not a guarantee, and a
# report that is a wall of non-ASCII text can cost more. Even in the paranoid
# case where every character became a token of its own, 3785 + 64 + 200 =
# 4049 still fits 4096 — which no smaller round window does. The cost is the
# extra key-value cache on a three-billion-parameter model, a rounding error
# against the model file itself, and the guardian's reason to exist is that
# it answers before the user has fixed the thing by hand.
#
# ^ RAISING ANY OF THE NINE LIMITS ABOVE MEANS REDOING THIS SUM. The test
#   `test_der_groesste_moegliche_prompt_passt_ins_fenster` assembles the
#   largest request this code can build and does the arithmetic again, so a
#   limit raised without a window raised fails the suite rather than the run.
ZEICHEN_JE_TOKEN = 2.0
VORLAGE_TOKENS = 64
KONTEXT = 4096

# One correct instruction is wanted, not an idea. Measured identical from
# 0.0 to 0.2 and worse from 0.4 up.
TEMPERATUR = 0.1


@dataclass
class Eintrag:
    """One finding in the panel: what went wrong, and what to do about it."""

    id: int
    chat_id: str
    befund: Befund
    # None while the model is still thinking — the panel shows the finding
    # immediately and fills the suggestion in when it arrives.
    vorschlag: str | None = None
    # Why there is no suggestion, when the reason is not the model's answer
    # but the guardian's own server. The KEY of a sentence, never the
    # sentence: the window is the only place that knows which language the
    # person in front of it reads.
    hinweis: str | None = None

    def als_daten(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "art": self.befund.art,
            "werkzeug": self.befund.werkzeug,
            "ergebnis": self.befund.ergebnis,
            "vorschlag": self.vorschlag,
            "hinweis": self.hinweis,
        }


@dataclass
class Wache:
    """The guardian's memory for one chat."""

    eintraege: list[Eintrag] = field(default_factory=list)
    # Counted per request from the user, not per chat: a long conversation
    # should not use up its allowance on the first afternoon.
    im_auftrag: int = 0


class Waechter:
    def __init__(self) -> None:
        self._wachen: dict[str, Wache] = {}
        self._zaehler = count(1)

    # Reading and writing use different doors on purpose. A GET for a chat
    # id that does not exist must not leave a `Wache` behind — the route is
    # reachable with any id, and a loop over made-up ones would otherwise
    # grow this dict without bound.
    _LEER = Wache()

    def _lesen(self, chat_id: str) -> Wache:
        return self._wachen.get(chat_id) or self._LEER

    def _wache(self, chat_id: str) -> Wache:
        return self._wachen.setdefault(chat_id, Wache())

    def neuer_auftrag(self, chat_id: str) -> None:
        """A new request from the user: the allowance starts over."""
        self._wache(chat_id).im_auftrag = 0

    def darf_noch(self, chat_id: str) -> bool:
        return self._lesen(chat_id).im_auftrag < JE_AUFTRAG

    def aufnehmen(self, chat_id: str, befund: Befund) -> Eintrag | None:
        """File a finding, or None when this request has had its two."""
        wache = self._wache(chat_id)
        if wache.im_auftrag >= JE_AUFTRAG:
            return None
        wache.im_auftrag += 1
        eintrag = Eintrag(id=next(self._zaehler), chat_id=chat_id, befund=befund)
        wache.eintraege.append(eintrag)
        return eintrag

    def offene(self, chat_id: str) -> list[Eintrag]:
        """Findings still waiting for a suggestion."""
        return [e for e in self._lesen(chat_id).eintraege if e.vorschlag is None]

    def liste(self, chat_id: str) -> list[Eintrag]:
        return list(self._lesen(chat_id).eintraege)

    def verwerfen(self, chat_id: str, eintrag_id: int) -> bool:
        wache = self._wachen.get(chat_id)
        if wache is None:
            return False
        vorher = len(wache.eintraege)
        wache.eintraege = [e for e in wache.eintraege if e.id != eintrag_id]
        return len(wache.eintraege) != vorher

    def vergessen(self, chat_id: str) -> None:
        """A deleted chat takes its findings with it."""
        self._wachen.pop(chat_id, None)


wache = Waechter()


def ordnerzeile(ordner: list[str] | None) -> str:
    """The released folders, as many as fit, whole ones only."""
    teile: list[str] = []
    uebrig = ORDNER_GRENZE
    for eintrag in ordner or []:
        pfad = str(eintrag)
        # The two characters are the ", " this entry costs in the join.
        bedarf = len(pfad) + (2 if teile else 0)
        if bedarf > uebrig:
            break
        uebrig -= bedarf
        teile.append(pfad)
    return ", ".join(teile)


# The fact that turns a wrong suggestion into a right one. Without it, a
# `python3 -m pytest` that fails with "No module named pytest" reads to the
# model like a missing global package, and it proposes `pip install` — while
# the environment that already has pytest sits one folder deep. Naming the
# interpreter directly (`.venv/bin/python3 -m pytest`) is the fix, and the
# tool starts every command in its own shell, so `source .venv/bin/activate`
# does not carry over — which the model can only know if the venv is named.
UMGEBUNGSMARKE = "The working folder contains .venv/"


def umgebungszeile(ordner: list[str] | None) -> str:
    """One line if a released folder holds a `.venv`, empty otherwise.

    Scans every released folder, not only the ones that fit on the folder
    line: the marker is a single fact about the environment, and it is worth
    naming even when the folder itself was dropped from the list for length.
    """
    for eintrag in ordner or []:
        try:
            if (Path(eintrag) / ".venv").is_dir():
                return UMGEBUNGSMARKE
        except OSError:
            # A path that cannot be looked at is simply not a venv here.
            continue
    return ""


def frage_bauen(
    befund: Befund, ordner: list[str] | None = None, zustand=None
) -> Generierungsanfrage:
    """The one request that goes to the model.

    Deliberately without the conversation's history: the guardian is asked
    about a single failed step, and a history would invite it to answer the
    conversation instead of the failure. Everything it needs is in the
    finding.

    `ordner` are the folders this chat has released. They belong in the
    report for a plain reason: a call refused for reaching outside them can
    only be repaired by naming a path INSIDE them, and a model that is never
    told which those are cannot name one. Asking anyway is not a test of the
    model, it is a gap in our question.

    `zustand` is the endpoint this goes to, and it is here for the thinking
    switch alone — see below. Without one nothing is asked of the template,
    which is the same answer the switch gives for an endpoint that reveals
    nothing about itself.
    """
    teile = [f"Tool: {befund.werkzeug}"]
    if befund.auftrag:
        teile.append(f"The user had asked: {befund.auftrag}")
    if befund.argumente:
        teile.append(f"Called with: {befund.argumente}")
    teile.append(f"It came back with: {befund.ergebnis}")
    # Why a refused call was refused. `ergebnis` for a refusal only says a
    # tool was "not allowed"; the reason is what tells apart a path outside
    # the shared folders — repairable by naming one inside — from a refusal
    # nothing can be done about, so the model stops proposing the one fix
    # that is never right, asking for the permission again.
    if befund.grund:
        teile.append("Refused because: " + befund.grund)
    if zeile := ordnerzeile(ordner):
        teile.append("Released folders: " + zeile)
    # Only a command that FAILED can be the "No module named X" this marker
    # answers. On a refused write or an unreadable file it is noise, and a
    # small model reads noise as instruction — told about a .venv beside a
    # refused path, it proposed writing the note INTO the .venv. So the fact
    # rides only the finding it can actually repair.
    if befund.art == BEFEHL_GESCHEITERT and (marke := umgebungszeile(ordner)):
        teile.append(marke)
    return Generierungsanfrage(
        nachrichten=[
            ChatNachricht(role="system", content=ANWEISUNG),
            ChatNachricht(role="user", content="\n".join(teile)),
        ],
        max_tokens=ANTWORT_GRENZE,
        # Sober: one instruction, not an idea.
        temperature=TEMPERATUR,
        # No thinking pass. What is asked for here is a single line, and a
        # model that reasons its way to it spends the whole budget on the
        # reasoning — which arrives in a different channel than the answer,
        # so the panel would show nothing at all.
        #
        # Asked FOR this endpoint rather than stated. The flag only means
        # anything where the chat template knows it; sent to a template that
        # does not, it lands in the rendered prompt as text, which is worse
        # than not asking. That decision has one home and this is a caller
        # of it, not a second copy.
        zusatz=denkschalter.zusatz(False, zustand) if zustand is not None else {},
    )


def fenster_bedarf(anfrage: Generierungsanfrage) -> int:
    """How much of the window a built request needs, in tokens.

    The one formula behind the sizing block at the top of this file: what is
    written plus what the template wraps around it plus what the answer is
    allowed to cost. Kept as code so the sum can be recomputed on a request
    that was really assembled, instead of being retyped in a comment and in
    a test until the three disagree.
    """
    zeichen = sum(len(nachricht.content or "") for nachricht in anfrage.nachrichten)
    tokens = int(zeichen / ZEICHEN_JE_TOKEN) + VORLAGE_TOKENS
    return tokens + (anfrage.max_tokens or 0)


def vorschlag_saeubern(text: str) -> str:
    """What the model returns, reduced to the one instruction.

    Models like to wrap an answer in a sentence of their own or in code
    fences. The panel shows this text as something to send, so anything
    that is not the instruction has to come off — a stray "Sure, try:" would
    be sent along with it.
    """
    sauber = (text or "").strip()
    if sauber.startswith("```"):
        zeilen = [z for z in sauber.splitlines() if not z.strip().startswith("```")]
        sauber = "\n".join(zeilen).strip()
    return sauber[:VORSCHLAG_GRENZE].strip()


async def vorschlag_holen(
    zustand, modellname: str | None, befund: Befund, ordner: list[str] | None = None
) -> str:
    """Ask the guardian's own server once. "" when nothing usable comes back.

    `zustand` is the endpoint state of that server — the provider to talk to
    and the capabilities to ask about. It is NOT the chat's endpoint, and the
    caller is the place that guarantees it: whoever resolves the wrong one
    here sends a failed command and the released folders wherever the chat
    happens to point.

    Errors are swallowed on purpose. The guardian is an extra; a failed
    suggestion must never turn into a second error message on top of the
    one the user already has. A server that is not there at all is the other
    case and does not come through here — it is reported.
    """
    anfrage = frage_bauen(befund, ordner, zustand)
    if modellname:
        anfrage.modell = modellname
    stuecke: list[str] = []
    quelle = None
    try:
        quelle = zustand.provider.streamen(anfrage)
        async for stueck in quelle:
            if stueck.sorte == "content":
                stuecke.append(stueck.text)
    except Exception:  # noqa: BLE001
        log.warning("Wächter: kein Vorschlag zu %s", befund.art, exc_info=True)
        return ""
    finally:
        if quelle is not None:
            try:
                await quelle.aclose()
            except Exception:  # noqa: BLE001
                pass
    return vorschlag_saeubern("".join(stuecke))
