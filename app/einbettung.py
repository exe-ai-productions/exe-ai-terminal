"""Big documents, without blowing the context.

A hundred-page PDF attached to a chat used to go into every request whole.
That works until it does not: past a certain size the model server refuses,
or worse, silently drops the front of the conversation to make room — and
the answer is then confidently wrong about a document that WAS attached.

So past a threshold the document stops travelling as a block. It is cut
into sections, each section gets a vector, and every question carries only
the handful of sections that actually have to do with it. Below the
threshold nothing changes: a two-page letter is cheaper to send whole than
to search.

**No second server.** The vectors come from llama.cpp's one-shot
``llama-embedding`` — one call per document, the program starts, computes,
prints and is gone. The runner lock in this house says one model server at
a time, and an embedding server running beside the language model would
break it for a job that takes two seconds.

**No numpy.** Cosine similarity over a few thousand sections is a few
thousand multiply-adds, which plain Python does in milliseconds. A
dependency that ships a hundred megabytes of compiled code for that would
have to be carried into every installer on every platform, and the house
rule says the installer decides.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

PROGRAMM = "llama-embedding.exe" if sys.platform == "win32" else "llama-embedding"

# A section is about this many words, and consecutive sections share this
# many. The overlap is what keeps a sentence that straddles a boundary from
# being lost to both sides — the single most common way a search like this
# misses the one paragraph it was built for.
WOERTER = 600
UEBERLAPPUNG = 100

# Above this many characters a document is cut up instead of sent whole.
# Roughly forty pages: below it, sending everything is both cheaper and
# more faithful than any selection could be.
SCHWELLE = 15000

# How many sections ride along with a question. Six is enough for an answer
# to quote across two or three passages and still leave the context room
# for the conversation itself.
MITREISENDE = 6

ZEITGRENZE = 300


class EinbettungFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


@dataclass(frozen=True)
class Treffer:
    nummer: int
    text: str
    naehe: float


def programm_finden(datenordner: Path, neben: Path | None = None) -> Path | None:
    """The llama-embedding binary, or nothing if this machine has none.

    Looked for beside the model server first when one is known: the two come
    out of the same package, so a machine that has one almost always has the
    other in the same folder — including the copy this program fetched
    itself, which is on no PATH.
    """
    if neben is not None:
        geschwister = Path(neben).parent / PROGRAMM
        if geschwister.is_file() and os.access(geschwister, os.X_OK):
            return geschwister
    gefunden = shutil.which(PROGRAMM)
    if gefunden:
        return Path(gefunden)
    wurzel = Path(datenordner).expanduser() / "llama.cpp"
    if wurzel.is_dir():
        treffer = sorted(wurzel.rglob(PROGRAMM))
        if treffer:
            return treffer[0]
    return None


def modelle(ordner: Path) -> list[str]:
    """The embedding models lying in their own folder, by file name."""
    verzeichnis = Path(ordner).expanduser()
    if not verzeichnis.is_dir():
        return []
    return sorted(
        p.name for p in verzeichnis.iterdir() if p.is_file() and p.suffix == ".gguf"
    )


def modell_finden(ordner: Path) -> Path | None:
    """The embedding model to use, or nothing.

    The FOLDER says what a file is — not its name. The first build read the
    name and looked for "embed" in it, which put an embedding model into the
    language model's picker, sent its start against a port that was already
    taken, and pointed "open model folder" at the wrong folder. A file lying
    in the embedding folder is an embedding model, and nothing else has to
    be guessed.
    """
    gefunden = modelle(ordner)
    return Path(ordner).expanduser() / gefunden[0] if gefunden else None


def zerlegen(text: str, woerter: int = WOERTER, ueberlappung: int = UEBERLAPPUNG) -> list[str]:
    """Cut a document into overlapping sections.

    Deterministic on purpose: the same document must give the same sections
    every time, or a stored vector would stop belonging to the text it was
    computed from.

    Newlines come out. One section is ONE line for the embedding program,
    which reads its inputs line by line — a section that kept its paragraph
    breaks would arrive as several unrelated inputs.
    """
    if ueberlappung >= woerter:
        raise ValueError("Überlappung muss kleiner als die Abschnittslänge sein")
    stuecke = (text or "").split()
    if not stuecke:
        return []
    schritt = woerter - ueberlappung
    abschnitte: list[str] = []
    start = 0
    while start < len(stuecke):
        abschnitte.append(" ".join(stuecke[start : start + woerter]))
        # The last section is whatever is left. Without this the loop would
        # append an extra section made entirely of overlap.
        if start + woerter >= len(stuecke):
            break
        start += schritt
    return abschnitte


def kosinus(a: list[float], b: list[float]) -> float:
    """How close two vectors point. 1 is the same direction, 0 unrelated."""
    if not a or not b or len(a) != len(b):
        return 0.0
    punkt = betrag_a = betrag_b = 0.0
    for x, y in zip(a, b):
        punkt += x * y
        betrag_a += x * x
        betrag_b += y * y
    if betrag_a <= 0 or betrag_b <= 0:
        return 0.0
    return punkt / math.sqrt(betrag_a * betrag_b)


def packen(vektor: list[float]) -> bytes:
    """A vector as a blob. Single precision: the seventh decimal place of a
    similarity score has never decided which paragraph was the right one,
    and half the bytes is half the database."""
    return struct.pack(f"<{len(vektor)}f", *vektor)


def entpacken(rohdaten: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(rohdaten) // 4}f", rohdaten))


# One embedding run at a time, for the same reason the picture generator has
# one: the program loads a model of its own, and two of them beside the
# language model share one pool of memory. Two large uploads arriving
# together would otherwise start two loads at once.
_SCHLOSS = threading.Lock()


def vektoren(programm: Path, modell: Path, abschnitte: list[str]) -> list[list[float]]:
    """One call for the whole batch. Returns one vector per section.

    The sections go through a file rather than the command line: a hundred
    sections of six hundred words each is far past any shell's limit, and a
    temporary file has no such ceiling.
    """
    if not abschnitte:
        return []
    with _SCHLOSS:
        return _rechnen(programm, modell, abschnitte)


def _rechnen(programm: Path, modell: Path, abschnitte: list[str]) -> list[list[float]]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as datei:
        # One section per line — that is how the program separates inputs.
        datei.write("\n".join(a.replace("\n", " ") for a in abschnitte))
        pfad = Path(datei.name)
    try:
        lauf = subprocess.run(
            [
                str(programm),
                "-m", str(modell),
                "-f", str(pfad),
                "--embd-output-format", "array",
                # Mean pooling: one vector for a whole section, which is what
                # a section IS here. Without it the program answers per token
                # and there is nothing to compare.
                "--pooling", "mean",
            ],
            capture_output=True,
            text=True,
            timeout=ZEITGRENZE,
        )
    except subprocess.TimeoutExpired as fehler:
        raise EinbettungFehler("einbettung.zeit_abgelaufen") from fehler
    except OSError as fehler:
        raise EinbettungFehler("einbettung.kein_programm") from fehler
    finally:
        pfad.unlink(missing_ok=True)
    if lauf.returncode != 0:
        log.warning("Einbettung gescheitert (%s): %s", lauf.returncode, lauf.stderr[-500:])
        raise EinbettungFehler("einbettung.gescheitert")
    try:
        gelesen = json.loads(lauf.stdout)
    except json.JSONDecodeError as fehler:
        raise EinbettungFehler("einbettung.gescheitert") from fehler
    if len(gelesen) != len(abschnitte):
        # A mismatch means the sections and the vectors no longer line up,
        # and a wrong pairing is worse than no search at all.
        log.warning("Einbettung: %d Vektoren für %d Abschnitte", len(gelesen), len(abschnitte))
        raise EinbettungFehler("einbettung.gescheitert")
    return [[float(z) for z in vektor] for vektor in gelesen]


def naechste(
    frage: list[float],
    gespeichert: list[tuple[int, str, list[float]]],
    anzahl: int = MITREISENDE,
) -> list[Treffer]:
    """The sections closest to a question, best first.

    Only sections that actually point somewhere come back. A vector of a
    different length scores 0.0 — and so does one that genuinely has nothing
    to do with the question. Sorting a list of zeros is still sorting: it
    leaves the sections in the order they were inserted, which is document
    order, so the first few sections of the file would come back looking
    exactly like an answer.

    Nothing found is a real answer here and a safe one: the caller reads an
    empty list as "no selection" and sends the whole document instead.
    """
    if not frage:
        return []
    bewertet = [
        treffer
        for treffer in (
            Treffer(nummer=nummer, text=text, naehe=kosinus(frage, vektor))
            for nummer, text, vektor in gespeichert
            if len(vektor) == len(frage)
        )
        if treffer.naehe > 0
    ]
    bewertet.sort(key=lambda t: t.naehe, reverse=True)
    return bewertet[:anzahl]


def als_kontext(dateiname: str, treffer: list[Treffer]) -> str:
    """The sections, written so the model can cite where it read something.

    Every section says which document and which number it came from. A
    model that quotes "from report.pdf, section 12" can be checked; one that
    quotes a floating paragraph cannot.
    """
    if not treffer:
        return ""
    teile = [f'[From "{dateiname}", the passages that fit the question]']
    for eintrag in treffer:
        teile.append(f"[{dateiname}, section {eintrag.nummer}]\n{eintrag.text}")
    teile.append("[End of passages]")
    return "\n\n".join(teile)
