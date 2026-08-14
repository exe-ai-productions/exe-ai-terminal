"""Cutting the chat list into days.

Three things can go wrong here and none of them is visible in a
screenshot taken on a quiet afternoon: the day boundary is computed in UTC
instead of on the user's wall clock, the incoming order gets shuffled while
grouping, or "Yesterday" quietly swallows the day before it.

The grouping is an import-free function of a list and a moment, so it runs
here as it is — including the moment, which is why the boundaries can be
aimed at at all.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
FRONTEND = WURZEL / "frontend"
MODUL = FRONTEND / "src" / "lib" / "chatgruppen.js"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="kein Node auf diesem Rechner"
)


def _laufen(js: str) -> dict:
    treiber = FRONTEND / "chatgruppen.pruefung.mjs"
    treiber.write_text(
        textwrap.dedent(
            """
            import { chatgruppen, gruppenDatum } from %r
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
            ["node", treiber.name],
            cwd=FRONTEND,
            capture_output=True,
            text=True,
            timeout=60,
            # A fixed zone, because the day boundary is exactly what is being
            # measured — on a machine set to UTC the local-time test would
            # pass for the wrong reason.
            env={**os.environ, "TZ": "Europe/Berlin"},
        )
    finally:
        treiber.unlink(missing_ok=True)
    assert lauf.returncode == 0, (lauf.stdout + lauf.stderr)[-2000:]
    return json.loads(lauf.stdout.strip().splitlines()[-1])


def test_heute_gestern_und_die_tage_davor_stehen_getrennt():
    bericht = _laufen(
        """
        const jetzt = new Date('2026-08-13T10:00:00+02:00').getTime()
        const chats = [
          { id: 'a', pinned: true, updated_at: '2026-06-01T09:00:00+02:00' },
          { id: 'b', updated_at: '2026-08-13T09:00:00+02:00' },
          { id: 'c', updated_at: '2026-08-13T08:00:00+02:00' },
          { id: 'd', updated_at: '2026-08-12T23:30:00+02:00' },
          { id: 'e', updated_at: '2026-08-07T12:00:00+02:00' },
        ]
        return chatgruppen(chats, jetzt).map((g) => ({
          schluessel: g.schluessel,
          datiert: Boolean(g.datum),
          ids: g.chats.map((c) => c.id),
        }))
        """
    )
    assert bericht == [
        {"schluessel": "chat.angeheftet", "datiert": False, "ids": ["a"]},
        {"schluessel": "chat.heute", "datiert": False, "ids": ["b", "c"]},
        {"schluessel": "chat.gestern", "datiert": False, "ids": ["d"]},
        {"schluessel": None, "datiert": True, "ids": ["e"]},
    ]


def test_die_grenze_liegt_auf_der_ortszeit_nicht_auf_utc():
    """22:30 local is already the next day in UTC — it must still read as today."""
    bericht = _laufen(
        """
        const jetzt = new Date('2026-08-13T23:00:00+02:00').getTime()
        const chats = [{ id: 'spaet', updated_at: '2026-08-13T22:30:00+02:00' }]
        return chatgruppen(chats, jetzt).map((g) => g.schluessel)
        """
    )
    assert bericht == ["chat.heute"]


def test_die_reihenfolge_der_liste_bleibt_wie_sie_kam():
    bericht = _laufen(
        """
        const jetzt = new Date('2026-08-13T10:00:00+02:00').getTime()
        const chats = [
          { id: '1', updated_at: '2026-08-13T09:00:00+02:00' },
          { id: '2', updated_at: '2026-08-11T09:00:00+02:00' },
          { id: '3', updated_at: '2026-08-11T08:00:00+02:00' },
          { id: '4', updated_at: '2026-08-05T09:00:00+02:00' },
        ]
        return chatgruppen(chats, jetzt).flatMap((g) => g.chats.map((c) => c.id))
        """
    )
    assert bericht == ["1", "2", "3", "4"]


def test_ein_chat_ohne_brauchbares_datum_reisst_keine_gruppe_auf():
    bericht = _laufen(
        """
        const jetzt = new Date('2026-08-13T10:00:00+02:00').getTime()
        const chats = [
          { id: 'gut', updated_at: '2026-08-13T09:00:00+02:00' },
          { id: 'kaputt', updated_at: 'unfug' },
        ]
        return chatgruppen(chats, jetzt).map((g) => ({
          schluessel: g.schluessel, ids: g.chats.map((c) => c.id),
        }))
        """
    )
    assert bericht == [{"schluessel": "chat.heute", "ids": ["gut", "kaputt"]}]


def test_um_mitternacht_entsteht_keine_zweite_heute_gruppe():
    """The clock in the sidebar ticks once a minute.

    For up to a minute after midnight it still says yesterday, so a chat
    stamped after midnight is dated LATER than "today". Filing that under a
    group of its own would leave two groups carrying the heading "Today" —
    and two groups with one key is an error Svelte raises rather than
    survives.
    """
    bericht = _laufen(
        """
        // The clock still stands a minute before midnight.
        const jetzt = new Date('2026-08-13T23:59:30+02:00').getTime()
        const chats = [
          { id: 'nachher', updated_at: '2026-08-14T00:00:10+02:00' },
          { id: 'nachmittag', updated_at: '2026-08-13T15:00:00+02:00' },
          { id: 'gestern', updated_at: '2026-08-12T15:00:00+02:00' },
        ]
        const gruppen = chatgruppen(chats, jetzt)
        return {
          schluessel: gruppen.map((g) => g.schluessel),
          ids: gruppen.map((g) => g.chats.map((c) => c.id)),
        }
        """
    )
    assert bericht["schluessel"] == ["chat.heute", "chat.gestern"]
    assert bericht["ids"] == [["nachher", "nachmittag"], ["gestern"]]
    # And no heading appears twice, whatever the grouping decided.
    assert len(bericht["schluessel"]) == len(set(bericht["schluessel"]))


def test_das_datum_traegt_die_ordnung_der_jeweiligen_sprache():
    """English puts the month first, German the day — Intl decides, not us."""
    bericht = _laufen(
        """
        const jetzt = new Date('2026-08-13T10:00:00+02:00').getTime()
        const tag = new Date(2026, 6, 7)
        const alt = new Date(2025, 6, 7)
        return {
          en: gruppenDatum(tag, 'en', jetzt),
          de: gruppenDatum(tag, 'de', jetzt),
          en_alt: gruppenDatum(alt, 'en', jetzt),
          de_alt: gruppenDatum(alt, 'de', jetzt),
        }
        """
    )
    assert bericht["en"] == "July 7"
    assert bericht["de"] == "7. Juli"
    # Beyond the current year the year comes along, or the heading is a riddle.
    assert "2025" in bericht["en_alt"] and "2025" in bericht["de_alt"]
