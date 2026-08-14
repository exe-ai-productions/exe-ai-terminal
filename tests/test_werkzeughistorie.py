"""The chat's small history: every tool call, in the order it happened.

The bug this replaces was quiet and complete: a conversation spent reading
and writing files reported "no command has run yet". The module was looking
at shell runs only, and everything else the program can do was invisible in
the place built to show what it had done.

The ordering is the part worth testing hardest. Runs and calls come from two
sources with no shared clock — the messages carry the order, the runs are
threaded into it — and a mistake there does not look like an error, it looks
like a history of things that happened in the wrong sequence.
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
MODUL = FRONTEND / "src" / "lib" / "werkzeughistorie.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="kein Node auf diesem Rechner"
)


def _laufen(js: str):
    treiber = FRONTEND / "werkzeughistorie.pruefung.mjs"
    treiber.write_text(
        textwrap.dedent(
            """
            import { historie, kurzargument, leer } from %r
            const bericht = (() => {
            %s
            })()
            console.log(JSON.stringify(bericht))
            """
        )
        % ("./" + str(MODUL.relative_to(FRONTEND)), textwrap.indent(js, "  ")),
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


def test_jeder_aufruf_bekommt_eine_zeile_egal_woher():
    """Built in, memory, or a server — the module used to see only one."""
    bericht = _laufen(
        """
        const nachrichten = [
          { werkzeuge: [
            { name: 'read_file', argumente: { path: 'app/main.py' } },
            { name: 'memory_save', server: 'memory', argumente: { text: 'etwas' } },
          ] },
          { stats: { werkzeuge: [
            { name: 'web_search', server: 'suche', argumente: { query: 'Wetter morgen' } },
          ] } },
        ]
        return historie(nachrichten, []).map((e) => [e.art, e.name, e.kurz])
        """
    )
    assert bericht == [
        ["aufruf", "read_file", "app/main.py"],
        ["aufruf", "memory_save", "etwas"],
        ["aufruf", "web_search", "Wetter morgen"],
    ]


def test_ein_shell_befehl_erscheint_als_lauf_und_nicht_doppelt():
    bericht = _laufen(
        """
        const nachrichten = [{ werkzeuge: [
          { name: 'read_file', argumente: { path: 'a.py' } },
          { name: 'run_command', argumente: { command: 'ls -F' } },
        ] }]
        const laeufe = [{ lauf: 1, befehl: 'ls -F', zustand: 'fertig' }]
        const eintraege = historie(nachrichten, laeufe)
        return {
          arten: eintraege.map((e) => e.art),
          namen: eintraege.map((e) => e.name ?? e.lauf.befehl),
        }
        """
    )
    assert bericht["arten"] == ["aufruf", "lauf"]
    assert bericht["namen"] == ["read_file", "ls -F"]


def test_die_reihenfolge_kommt_aus_dem_gespraech():
    """A run is threaded in where its call stands, not appended at the end."""
    bericht = _laufen(
        """
        const nachrichten = [
          { werkzeuge: [{ name: 'run_command', argumente: { command: 'erst' } }] },
          { werkzeuge: [{ name: 'read_file', argumente: { path: 'dann.py' } }] },
          { werkzeuge: [{ name: 'run_command', argumente: { command: 'zuletzt' } }] },
        ]
        const laeufe = [
          { lauf: 1, befehl: 'erst', zustand: 'fertig' },
          { lauf: 2, befehl: 'zuletzt', zustand: 'fertig' },
        ]
        return historie(nachrichten, laeufe).map((e) =>
          e.art === 'lauf' ? e.lauf.befehl : e.name,
        )
        """
    )
    assert bericht == ["erst", "read_file", "zuletzt"]


def test_ein_lauf_ohne_aufruf_geht_nicht_verloren():
    """The CLI module starts runs too — they happened, so they are shown."""
    bericht = _laufen(
        """
        const laeufe = [{ lauf: 7, befehl: 'aus der CLI', zustand: 'fertig' }]
        return historie([], laeufe).map((e) => [e.art, e.lauf.befehl])
        """
    )
    assert bericht == [["lauf", "aus der CLI"]]


def test_ein_shell_aufruf_ohne_lauf_faellt_auf_die_zeile_zurueck():
    """After a service restart the call is still in the chat, its output is not."""
    bericht = _laufen(
        """
        const nachrichten = [{ werkzeuge: [
          { name: 'run_command', argumente: { command: 'von gestern' } },
        ] }]
        return historie(nachrichten, []).map((e) => [e.art, e.name, e.kurz])
        """
    )
    assert bericht == [["aufruf", "run_command", "von gestern"]]


def test_die_leere_meldung_gilt_nur_wenn_wirklich_nichts_da_ist():
    bericht = _laufen(
        """
        return {
          nichts: leer([], []),
          nur_aufruf: leer([{ werkzeuge: [{ name: 'read_file', argumente: {} }] }], []),
          nur_lauf: leer([], [{ lauf: 1, befehl: 'x', zustand: 'fertig' }]),
        }
        """
    )
    assert bericht["nichts"] is True
    assert bericht["nur_aufruf"] is False
    assert bericht["nur_lauf"] is False


def test_das_kurzargument_sagt_worum_es_ging():
    bericht = _laufen(
        """
        return {
          pfad: kurzargument({ path: 'app/main.py' }),
          zahl: kurzargument({ zeilen: 42 }),
          lang: kurzargument({ text: 'x'.repeat(200) }).length,
          leer: kurzargument({}),
          keins: kurzargument(null),
          umbruch: kurzargument({ text: 'zwei\\n  zeilen' }),
        }
        """
    )
    assert bericht["pfad"] == "app/main.py"
    assert bericht["zahl"] == "42"
    # Long enough to recognise, short enough not to wrap.
    assert bericht["lang"] == 61
    assert bericht["leer"] == ""
    assert bericht["keins"] == ""
    assert bericht["umbruch"] == "zwei zeilen"


def test_der_ausgang_wird_mitgefuehrt():
    bericht = _laufen(
        """
        const nachrichten = [{ werkzeuge: [
          { name: 'read_file', argumente: {}, fehlgeschlagen: true },
          { name: 'write_file', argumente: {} },
        ] }]
        return historie(nachrichten, []).map((e) => e.fehlgeschlagen)
        """
    )
    assert bericht == [True, False]


# --- Two kinds of run in one list -----------------------------------------
#
# The merge brought drawing jobs into the same run list without telling the
# pairing about them. `shift()` then handed the next run to whichever shell
# call asked first, and a picture ended up filed under a command.


def test_ein_bildlauf_wird_keinem_shell_befehl_untergeschoben():
    """The regression.

    The picture was drawn first, so it stands first in the run list. The
    shell call must still get ITS run — not the picture — and the picture
    must still appear.
    """
    bericht = _laufen(
        """
        const nachrichten = [{ werkzeuge: [
          { name: 'run_command', argumente: { command: 'ls -F' } },
        ] }]
        const laeufe = [
          { lauf: 1, art: 'bild', befehl: 'ein Fuchs im Schnee', zustand: 'fertig' },
          { lauf: 2, art: 'befehl', befehl: 'ls -F', zustand: 'fertig' },
        ]
        return historie(nachrichten, laeufe).map((e) => [e.lauf.art, e.lauf.befehl])
        """
    )
    assert bericht == [
        ["befehl", "ls -F"],
        ["bild", "ein Fuchs im Schnee"],
    ]


def test_ein_lauf_ohne_art_gilt_weiter_als_befehl():
    """Runs stored before the kind existed must not become orphans."""
    bericht = _laufen(
        """
        const nachrichten = [{ werkzeuge: [
          { name: 'run_command', argumente: { command: 'ls' } },
        ] }]
        const laeufe = [{ lauf: 1, befehl: 'ls', zustand: 'fertig' }]
        const eintraege = historie(nachrichten, laeufe)
        return { anzahl: eintraege.length, befehl: eintraege[0].lauf.befehl }
        """
    )
    assert bericht == {"anzahl": 1, "befehl": "ls"}


def test_ein_bild_ohne_befehl_daneben_steht_trotzdem_da():
    bericht = _laufen(
        """
        const laeufe = [{ lauf: 1, art: 'bild', befehl: 'ein Hafen', zustand: 'fertig' }]
        return historie([], laeufe).map((e) => [e.art, e.lauf.art])
        """
    )
    assert bericht == [["lauf", "bild"]]
