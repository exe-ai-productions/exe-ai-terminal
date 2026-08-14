"""The embedding server: a second llama-server, on a port of its own.

Why a server at all, when the section search already works with one-shot
calls: a one-shot call pays for loading the model every single time. That is
right for cutting a document up — it happens once, and the seconds are spent
where somebody is watching an upload. It is wrong for a question, which
happens constantly and would carry a model load each time.

So the two ways stand side by side, and the fast one is optional:

* server running  → the question's vector comes over HTTP, in milliseconds
* server not running → the one-shot call applies, exactly as before

Nothing breaks by leaving it off. That is the whole point of the split —
this is a speed-up, not a dependency.

**Its own everything.** Port, note file, key variable. The first build gave
the embedding model to the language server's runner, and it collided on all
three: the start ran against the port the chat model was holding, the note
would have overwritten the chat server's, and the fresh key replaced the one
the running server was signing with. A second server is only a second server
if nothing about it is shared.
"""

from __future__ import annotations

import logging

import httpx

from app.modellrunner import Modellrunner

log = logging.getLogger(__name__)

# The note that finds an orphan again after a service restart. A name of its
# own, so two runners can share a folder without erasing each other's.
PID_DATEI = ".einbettungsserver.pid"

# The environment variable this server's key travels in.
SCHLUESSEL_VARIABLE = "EXE_EINBETTUNG_API_KEY"

# What makes a llama-server an embedding server.
#
# `--pooling mean` is the one that matters: without it the server answers per
# token, and there is nothing to compare a question against.
#
# The two batch sizes are the ones that make it USABLE. A server started
# without them lands on 512, and every section of a real document is bigger
# than that — the answer is then "input too large" on every single call, the
# fast path falls back every time, and it costs a round trip to find that
# out. Both numbers have to be given: with embeddings on, llama-server pulls
# the larger one down to the smaller one.
STAPEL = 2048
FLAGS = (
    "--embedding",
    "--pooling", "mean",
    "--batch-size", str(STAPEL),
    "--ubatch-size", str(STAPEL),
    # The window is NOT set here. The runner writes `--ctx-size` itself from
    # what it is started with, and a second one from this list produced a
    # command line carrying the flag twice — llama.cpp takes the last, so it
    # worked by accident until somebody reordered something. It travels as a
    # start value instead, see `starten` below.
)

# Short on purpose. If the server does not answer in this time it is not
# helping, and the one-shot path is right there.
ZEITGRENZE = 20.0


def runner_bauen(modellordner, programm: str | None, port: int) -> Modellrunner:
    """The embedding server's runner — the same class, another kind."""
    return Modellrunner(
        modellordner,
        programm,
        port=port,
        pid_datei=PID_DATEI,
        schluessel_variable=SCHLUESSEL_VARIABLE,
        zusatzflags=FLAGS,
        # No sampling lore and no --jinja: this server never samples and is
        # never handed a tool.
        sampling_flags=False,
    )


def vektoren(port: int, schluessel: str | None, texte: list[str]) -> list[list[float]] | None:
    """Vectors over HTTP, or None when this way is not available.

    None is not an error — it is the answer "ask the one-shot call". Every
    failure lands here: no server, a server still loading, a timeout, an
    answer in a shape we do not recognise. The caller has a way that always
    works and only needs to know whether the fast one worked.
    """
    if not texte:
        return []
    kopf = {"Authorization": f"Bearer {schluessel}"} if schluessel else {}
    try:
        antwort = httpx.post(
            f"http://127.0.0.1:{port}/v1/embeddings",
            json={"input": texte},
            headers=kopf,
            timeout=ZEITGRENZE,
        )
        antwort.raise_for_status()
        daten = antwort.json()["data"]
    except Exception:  # noqa: BLE001 - every failure means the same thing here
        log.debug("Einbettungsserver antwortet nicht, Einmal-Aufruf gilt", exc_info=True)
        return None
    try:
        geordnet = sorted(daten, key=lambda e: e.get("index", 0))
        vektoren = [[float(z) for z in eintrag["embedding"]] for eintrag in geordnet]
    except (KeyError, TypeError, ValueError):
        return None
    # A mismatch means the vectors and the texts no longer line up, and a
    # wrong pairing is worse than falling back.
    return vektoren if len(vektoren) == len(texte) else None
