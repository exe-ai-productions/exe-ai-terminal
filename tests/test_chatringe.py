"""The status dot of a chat row: which state wins when several are true.

A chat can be several things at once — a run is going on AND the last one
left an unseen error AND a confirmation is standing. The row has one dot,
so the order of precedence IS the feature; get it wrong and the list
quietly reports the least urgent of the three.

The decision lives in its own import-free module for exactly this reason:
it can be executed here as it is, without the interface around it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
FRONTEND = WURZEL / "frontend"
MODUL = FRONTEND / "src" / "lib" / "ringfarbe.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="kein Node auf diesem Rechner"
)


def _farben(faelle: list[dict]) -> list[str]:
    treiber = FRONTEND / "ringfarbe.pruefung.mjs"
    treiber.write_text(
        textwrap.dedent(
            """
            import { ringAus } from %r
            const faelle = %s
            console.log(JSON.stringify(faelle.map((f) => ringAus(f))))
            """
        )
        % ("./" + str(MODUL.relative_to(FRONTEND)), json.dumps(faelle)),
        encoding="utf-8",
    )
    try:
        lauf = subprocess.run(
            ["node", treiber.name], cwd=FRONTEND, capture_output=True, text=True, timeout=60
        )
    finally:
        treiber.unlink(missing_ok=True)
    assert lauf.returncode == 0, (lauf.stdout + lauf.stderr)[-2000:]
    return json.loads(lauf.stdout.strip().splitlines()[-1])


def test_jede_lage_fuer_sich_traegt_ihre_farbe():
    farben = _farben(
        [
            {},
            {"fertig": True},
            {"fehler": True},
            {"laeuft": True},
            {"fragt": True},
        ]
    )
    assert farben == ["leer", "gruen", "rot", "blau", "gelb"]


def test_eine_offene_frage_schlaegt_alles_andere():
    """A question stops the run — reporting "running" there would be a lie."""
    farben = _farben(
        [
            {"fragt": True, "laeuft": True, "fehler": True, "fertig": True},
            {"laeuft": True, "fehler": True, "fertig": True},
            {"fehler": True, "fertig": True},
        ]
    )
    assert farben == ["gelb", "blau", "rot"]
