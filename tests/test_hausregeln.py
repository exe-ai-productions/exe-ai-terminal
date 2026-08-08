"""House rules the code has to keep, enforced instead of remembered.

A rule that lives only in a document gets read once and forgotten; one that
fails the suite stays kept.

  1. Comments, docstrings and commit messages are ENGLISH. German is the
     language between people, not in the source.
  2. No person's name in a comment. The reasoning stays, the origin goes —
     decisions belong in the log, not in a source file.
  3. No interface text hardcoded in a component. Whatever is not in the
     catalogue can never be translated, and nobody notices until they open
     the window in the other language.

Rule 2 is counted: a counter that only ever reads zero keeps it that way.
"""

from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DURCHSUCHT = ("app", "tests", "frontend/src")
ENDUNGEN = (".py", ".js", ".svelte")

# How many name references a comment may carry: none. The counter stays at
# zero; never raise it.
NAMEN_OBERGRENZE = 0

# Words that occur in German and not in English. Two of them in one comment
# is the signal — a single one can be an English word that happens to look
# German ("the loop must never die").
DEUTSCHE_WOERTER = {
    "der", "die", "das", "und", "nicht", "wird", "werden", "über", "für",
    "kein", "keine", "muss", "soll", "darf", "dann", "noch", "schon", "beim",
    "vom", "zum", "eine", "einen", "einem", "wenn", "aber", "auch", "sich",
    "nur", "sind", "ist", "haben", "hat", "wurde", "diese", "dieser", "damit",
    "weil", "durch", "gegen", "ohne", "steht", "gibt", "macht",
}


def _dateien():
    for teil in DURCHSUCHT:
        for pfad in (WURZEL / teil).rglob("*"):
            if pfad.suffix in ENDUNGEN and "node_modules" not in str(pfad):
                yield pfad


def _kommentare(pfad: Path):
    """Every comment and docstring of a file, as (line number, text)."""
    text = pfad.read_text(errors="replace")
    if pfad.suffix == ".py":
        for nr, zeile in enumerate(text.splitlines(), 1):
            if "#" in zeile:
                yield nr, zeile[zeile.index("#"):]
        for treffer in re.finditer(r'"""(.*?)"""', text, re.S):
            yield text[: treffer.start()].count("\n") + 1, treffer.group(1)
        return
    for muster in (r"//(.*)$", r"/\*(.*?)\*/", r"<!--(.*?)-->"):
        flags = re.M if muster.endswith("$") else re.S
        for treffer in re.finditer(muster, text, flags):
            yield text[: treffer.start()].count("\n") + 1, treffer.group(1)


def test_kein_deutscher_kommentar_im_quelltext():
    """A comment carrying two German-only words is German, not English."""
    gefunden = []
    for pfad in _dateien():
        for nr, kommentar in _kommentare(pfad):
            woerter = {w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", kommentar)}
            if len(woerter & DEUTSCHE_WOERTER) >= 2:
                knapp = " ".join(kommentar.split())[:70]
                gefunden.append(f"{pfad.relative_to(WURZEL)}:{nr}  {knapp}")
    assert not gefunden, "Deutsche Kommentare im Quelltext:\n" + "\n".join(gefunden)


def test_namensnennungen_werden_nicht_mehr():
    """No comment carries a person's name.

    Every hit is a regression: the reasoning belongs in the comment, the
    origin does not.
    """
    stellen = [
        f"{pfad.relative_to(WURZEL)}:{nr}"
        for pfad in _dateien()
        for nr, kommentar in _kommentare(pfad)
        if re.search(r"\bChris\b", kommentar)
    ]
    assert len(stellen) <= NAMEN_OBERGRENZE, (
        f"{len(stellen)} Namensnennungen, erlaubt sind {NAMEN_OBERGRENZE}. Neu dazu:\n"
        + "\n".join(stellen[NAMEN_OBERGRENZE:])
    )


# Where a literal really is allowed to stand in the markup: the product name
# is a proper noun and reads the same in every language.
TEXT_ERLAUBT = {"frontend/src/teile/Wortmarke.svelte"}


def _ohne_ausdruecke(stueck: str) -> str:
    """Strips {...} including nested braces.

    A counter and not a pattern, because `{t('x', { a: b })}` has braces
    inside it — a non-greedy pattern stops at the inner one and leaves the
    rest looking like prose.
    """
    raus, tiefe = [], 0
    for zeichen in stueck:
        if zeichen == "{":
            tiefe += 1
        elif zeichen == "}":
            tiefe = max(0, tiefe - 1)
        elif tiefe == 0:
            raus.append(zeichen)
    return "".join(raus)


def test_kein_oberflaechentext_steht_fest_im_bauteil():
    """Visible words that never pass through t() cannot be translated.

    Checked are text between tags and the three attributes a person reads:
    title, placeholder, aria-label. Everything inside {...} is an expression
    and none of this business.
    """
    gefunden = []
    for pfad in (WURZEL / "frontend/src").rglob("*.svelte"):
        if str(pfad.relative_to(WURZEL)) in TEXT_ERLAUBT:
            continue
        markup = re.sub(
            r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", pfad.read_text()
        )
        markup = re.sub(r"<!--[\s\S]*?-->", "", markup)
        for nr, zeile in enumerate(markup.splitlines(), 1):
            stuecke = re.findall(r">([^<>]*)<", zeile)
            stuecke += [
                wert
                for _, wert in re.findall(
                    r'\b(title|placeholder|aria-label)="([^"]*)"', zeile
                )
            ]
            for stueck in stuecke:
                woerter = re.findall(
                    r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß'’-]{2,}", _ohne_ausdruecke(stueck)
                )
                if woerter:
                    gefunden.append(
                        f"{pfad.relative_to(WURZEL)}:{nr}  {' '.join(stueck.split())[:60]}"
                    )
    assert not gefunden, (
        "Oberflächentext steht fest im Bauteil statt im Katalog:\n" + "\n".join(gefunden)
    )
