"""The message queue, run for real instead of read.

The queue decides what happens to a message that was typed while an answer
was still running — whether it goes out by itself afterwards, whether it
stays put after a failed run, whether the ``✕`` really takes it out. Those
are three sentences of behaviour, and a test that only greps the source
would confirm the sentences exist, not that they hold.

So the module is compiled with Svelte's own compiler and executed in Node:
``$state`` works outside a browser, and the queue is plain data. What runs
here is the same file the interface imports, not a copy of its logic.
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
MODUL = FRONTEND / "src" / "lib" / "warteschlange.svelte.js"


def _laufen(js: str) -> dict:
    """Compile the queue module and run `js` against it, return its report."""
    treiber = FRONTEND / "warteschlange.pruefung.mjs"
    gebaut = FRONTEND / "warteschlange.gebaut.mjs"
    treiber.write_text(
        textwrap.dedent(
            """
            import { compileModule } from 'svelte/compiler'
            import { readFileSync, writeFileSync } from 'fs'
            const quelle = readFileSync(%r, 'utf-8')
            const gebaut = compileModule(quelle, {
              filename: 'warteschlange.svelte.js', generate: 'client',
            })
            writeFileSync(%r, gebaut.js.code)
            const w = await import(%r)
            const bericht = await (async () => {
            %s
            })()
            console.log('---BERICHT---' + JSON.stringify(bericht))
            """
        )
        % (str(MODUL), str(gebaut), "./" + gebaut.name, textwrap.indent(js, "  ")),
        encoding="utf-8",
    )
    try:
        lauf = subprocess.run(
            ["node", treiber.name],
            cwd=FRONTEND,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        treiber.unlink(missing_ok=True)
        gebaut.unlink(missing_ok=True)
    assert lauf.returncode == 0, (lauf.stdout + lauf.stderr)[-2000:]
    marke = "---BERICHT---"
    assert marke in lauf.stdout, lauf.stdout[-2000:]
    return json.loads(lauf.stdout.split(marke, 1)[1].strip())


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not (FRONTEND / "node_modules").is_dir(),
    reason="kein Node oder keine Frontend-Abhängigkeiten auf diesem Rechner",
)


def test_die_schlange_gibt_der_reihe_nach_heraus():
    """First in, first out — and per chat, not across all of them."""
    bericht = _laufen(
        """
        w.einreihen('a', { inhalt: 'eins' })
        w.einreihen('b', { inhalt: 'fremd' })
        w.einreihen('a', { inhalt: 'zwei' })
        return {
          erste: w.ausreihen('a').inhalt,
          zweite: w.ausreihen('a').inhalt,
          dann: w.ausreihen('a'),
          fremd_bleibt: w.fuerChat('b').map((e) => e.inhalt),
        }
        """
    )
    assert bericht["erste"] == "eins"
    assert bericht["zweite"] == "zwei"
    assert bericht["dann"] is None
    assert bericht["fremd_bleibt"] == ["fremd"]


def test_ein_lauf_der_scheitert_haelt_die_schlange_an():
    """The hold is what keeps the next message out of a broken state."""
    bericht = _laufen(
        """
        w.einreihen('a', { inhalt: 'eins' })
        w.einreihen('a', { inhalt: 'zwei' })
        w.einreihen('b', { inhalt: 'fremd' })
        const vorher = w.haelt('a')
        w.anhalten('a')
        return {
          vorher,
          nachher: w.haelt('a'),
          alle_markiert: w.fuerChat('a').every((e) => e.haelt),
          fremder_chat: w.haelt('b'),
          geloest: (w.loesen('a'), w.haelt('a')),
        }
        """
    )
    assert bericht["vorher"] is False
    assert bericht["nachher"] is True
    assert bericht["alle_markiert"] is True
    assert bericht["fremder_chat"] is False
    assert bericht["geloest"] is False


def test_das_kreuz_nimmt_genau_einen_eintrag_heraus():
    bericht = _laufen(
        """
        const eins = w.einreihen('a', { inhalt: 'eins' })
        w.einreihen('a', { inhalt: 'zwei' })
        w.entfernen(eins)
        w.entfernen(99999)
        return { rest: w.fuerChat('a').map((e) => e.inhalt) }
        """
    )
    assert bericht["rest"] == ["zwei"]


def test_ein_geloeschter_chat_nimmt_seine_schlange_mit():
    bericht = _laufen(
        """
        w.einreihen('a', { inhalt: 'eins' })
        w.einreihen('b', { inhalt: 'fremd' })
        w.leeren('a')
        return { a: w.fuerChat('a').length, b: w.fuerChat('b').length }
        """
    )
    assert bericht["a"] == 0
    assert bericht["b"] == 1
