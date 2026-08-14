"""The Extended Workflow server: the guardian's own small model.

The fourth process this program may hold, beside the chat model, the picture
generator and the embedding server. It exists because the guardian's worth is
its reaction time: a suggestion that arrives after the user has already fixed
the thing themselves is a suggestion nobody reads. Loading a model for every
finding costs more than keeping a small one warm.

It is deliberately NOT the chat model. The chat model is busy answering when
a finding appears — that is when the finding appeared — and asking it to write
a repair suggestion at the same moment either waits or competes. And the chat
model may be a cloud provider, while a finding carries the failed command, the
arguments it was called with and the folders this chat has released.

Which is why this module hands out an endpoint as well as a runner. A server
nobody has the address of is a server nobody asks: for its first weeks this
one was started, loaded its two gigabytes and was never sent a single request,
because the guardian asked whatever endpoint the chat happened to be on.

Started when Extended Workflow is switched on, stopped when it is switched
off. Nothing here starts by itself: a model that loads without being asked is
a gigabyte somebody did not agree to.

The numbers come from `waechter.py`, where they are derived from what the
guardian's own code can produce. They are not settings and do not appear on
any page.
"""

from __future__ import annotations

import logging

from app.config import EndpointConfig

# The /props reading is borrowed, not copied. Reading a chat template a
# second time here is exactly the kind of duplicate that drifts apart: one
# copy learns about a new capability field and the other keeps answering
# from the old one.
from app.discovery import EndpunktZustand
from app.discovery import _faehigkeiten_erkennen as faehigkeiten_erkennen
from app.modellrunner import Modellrunner
from app.providers import provider_bauen
from app.waechter import KONTEXT

log = logging.getLogger(__name__)

# Its own file, so a service restart can find and end an orphan of its own
# rather than mistaking the chat model's process for one.
PID_DATEI = "eew-server.pid"
SCHLUESSEL_VARIABLE = "EXE_EEW_SCHLUESSEL"

# The port it answers on. Its own, because sharing one with the chat model is
# exactly what having a second server is for — and 8083 rather than the 8082
# it started out as: a chat model started by hand lands on 8082 often enough
# that the default collided with real setups on the first machine it met.
#
# There is deliberately NO search for a free port. A guardian that answers on
# a different port every session is a guardian nobody can look up, and the
# refusal the runner already gives ("that port is already taken") is the
# honest answer to a clash.
PORT_VORGABE = 8083

# What the guardian model is asked to be. Small enough that it may stay
# loaded, large enough to have passed the six checkpoints — see the
# Extended-Workflow handoff for the measurements.
MODELL_VORGABE = "qwen2.5-coder-3b-instruct-q4_k_m.gguf"

# Nothing extra on the command line. The window is NOT set here: the runner
# writes `--ctx-size` itself from what it is started with, and adding a second
# one produced a command line carrying the flag twice. llama.cpp takes the
# last one and it happened to work — the kind of accident that holds until
# somebody reorders the list.
FLAGS = ()


# The id this server appears under wherever an endpoint is named. Fixed, so
# a restart on the same port replaces the entry instead of adding one.
ENDPUNKT_ID = "eew"

# How long the guardian's own server may take to answer the two questions
# asked of it before it is treated as absent. Everything here is a request
# to 127.0.0.1 against a process this program started itself; a machine that
# needs longer than this has a different problem than a missing suggestion.
ZEITGRENZE = 5.0


class NichtBereit(Exception):
    """The guardian's server cannot answer right now.

    Carries the key of the sentence to show, not the sentence itself — the
    caller decides in which language it is said.

    This exists so the failure has to be handled. The alternative that was in
    place is the reason it exists: the guardian used to be asked of whatever
    model the chat was on, so switching on a LOCAL guardian and chatting with
    a cloud provider sent every failed command, its arguments and the list of
    released folders out of the house.
    """

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


def endpunkt_bauen(port: int | None = None) -> EndpointConfig:
    """The endpoint the guardian's own server answers on.

    Built here rather than written to the configuration, for the same reason
    the chat runner's is: the entry lives exactly as long as the server it
    describes, and it must never show up in a model picker — this model
    writes repair suggestions, and a conversation sent to it would arrive at
    a server started for something else entirely.
    """
    return EndpointConfig(
        id=ENDPUNKT_ID,
        base_url=f"http://127.0.0.1:{port or PORT_VORGABE}/v1",
        provider="openai_compatible",
        parameter_dialect="llama_cpp",
        group="local",
        # The runner hands its server a fresh key at every start; requests
        # without it are turned away — the lock against web pages knocking on
        # localhost from inside the user's browser.
        api_key_env=SCHLUESSEL_VARIABLE,
    )


# What was asked of the running server already, so it is not asked again for
# every finding. Keyed by port AND model file: a restart with another file is
# another chat template, and a stale capability entry would send a thinking
# flag to a server whose template has no idea what it means.
_zustaende: dict[tuple[int, str], EndpunktZustand] = {}


async def wachzustand(runner: Modellrunner | None) -> tuple[EndpunktZustand, str | None]:
    """The guardian's endpoint, ready to be asked — or ``NichtBereit``.

    Returns the endpoint state and the name the server calls its model by.
    Both are read from the server itself: what is loaded there is the truth,
    and a name maintained anywhere else would be wrong the first time
    somebody picks another file.
    """
    lauf = runner.lauf() if runner is not None else None
    if lauf is None:
        raise NichtBereit("waechter.kein_server")

    schluessel = (lauf.port, lauf.modell)
    if (bekannt := _zustaende.get(schluessel)) is not None:
        return bekannt, bekannt.gemeldeter_name

    try:
        endpunkt = endpunkt_bauen(lauf.port)
        zustand = EndpunktZustand(endpunkt=endpunkt, provider=provider_bauen(endpunkt))
        # Asked once per loaded file. Without this the thinking switch has
        # nothing to decide on and is not sent at all — which on a model that
        # reasons spends the whole answer budget on the reasoning, in a
        # channel the panel never sees.
        zustand.faehigkeiten_erkannt = await faehigkeiten_erkennen(
            endpunkt.base_url, ZEITGRENZE, endpunkt.api_key_env
        )
        zustand.gemeldeter_name = await zustand.provider.modellname(ZEITGRENZE)
    except Exception as fehler:  # noqa: BLE001
        # Anything that goes wrong on the way to the guardian's own server
        # leaves by the one door, so the caller has exactly one case to
        # handle and can never end up with a half-built endpoint. The reason
        # goes to the log; the panel gets the same sentence either way,
        # because for the person looking at it there is no difference between
        # a server that is down and one that cannot be reached.
        log.warning("Wächterserver nicht ansprechbar", exc_info=True)
        raise NichtBereit("waechter.kein_server") from fehler
    # Only an answer is worth remembering. The process exists a moment before
    # it serves — a model file has to be read from disk first — and a silence
    # cached at that moment would be treated as the truth about this server
    # for as long as it runs.
    if zustand.faehigkeiten_erkannt is not None:
        # One at a time: a new port or a new file replaces what was there
        # rather than joining it.
        _zustaende.clear()
        _zustaende[schluessel] = zustand
    return zustand, zustand.gemeldeter_name


def runner_bauen(modellordner, programm: str | None, port: int | None = None) -> Modellrunner:
    """The guardian's runner — the same class as the others, another kind."""
    return Modellrunner(
        modellordner,
        programm,
        port=port or PORT_VORGABE,
        pid_datei=PID_DATEI,
        schluessel_variable=SCHLUESSEL_VARIABLE,
        zusatzflags=FLAGS,
        # It samples and it is handed no tools: the sampling lore of the
        # model family applies, the tool template does not matter.
        sampling_flags=True,
    )
