"""Whether a GGUF file carries its own multi-token-prediction layers.

Some model releases fold their MTP ("NextN") weights into the main file
instead of shipping them as a separate draft model next to it. The file
name and the repository it came from are both just words somebody chose;
the file's own GGUF header is the only place this is actually written
down.
"""

from __future__ import annotations

import struct
from pathlib import Path

# GGUF value types, from the format's own spec — only the ones this reader
# has to either read or skip past show up here.
_ZEICHENKETTE = 8
_FELD = 9
_FESTE_GROESSE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

# The key llama.cpp writes on every architecture that carries embedded
# next-token-prediction layers — always this suffix behind the
# architecture's own name ("qwen35moe.nextn_predict_layers",
# "deepseek2.nextn_predict_layers", …). Present and greater than zero is
# the only honest signal; a file without it, or with it at zero, carries
# no embedded MTP.
_SCHLUESSEL_ENDUNG = ".nextn_predict_layers"

# A metadata section this large is not a metadata section any more —
# either the file is not a real GGUF or the header is corrupt. Real
# headers, vocabularies included, stay far under this.
_HOECHSTE_SCHLUESSEL_ANZAHL = 100_000


def traegt_eingebettetes_mtp(pfad: Path) -> bool:
    """Does this GGUF file carry its own multi-token-prediction layers?

    Reads only the metadata section at the front of the file, never the
    tensors themselves — cheap even for a model tens of gigabytes large.
    Anything that is not a current, well-formed GGUF header (wrong magic,
    an unsupported version, a truncated or hand-edited file) answers
    False instead of raising: a broken header proves nothing either way,
    and a model must still be startable without it.
    """
    try:
        with open(pfad, "rb") as datei:
            return _kopf_lesen(datei)
    except Exception:
        return False


def _genau(datei, anzahl: int) -> bytes:
    stueck = datei.read(anzahl)
    if len(stueck) != anzahl:
        raise EOFError("the header ended before this value did")
    return stueck


def _u32(datei) -> int:
    return struct.unpack("<I", _genau(datei, 4))[0]


def _u64(datei) -> int:
    return struct.unpack("<Q", _genau(datei, 8))[0]


def _zeichenkette(datei) -> str:
    laenge = _u64(datei)
    return _genau(datei, laenge).decode("utf-8")


def _wert_lesen(datei, art: int) -> int | float | bool | str:
    """The value's own bytes, decoded — only ever called on the one key
    this reader is actually looking for, never on the whole header."""
    if art == _ZEICHENKETTE:
        return _zeichenkette(datei)
    if art == _FELD:
        # An array where a plain count was expected is not the marker
        # this reader knows how to trust — treated as "no" by the caller.
        elementart = _u32(datei)
        anzahl = _u64(datei)
        for _ in range(anzahl):
            _wert_ueberspringen(datei, elementart)
        return False
    if art == 7:
        return _genau(datei, 1)[0] != 0
    rohdaten = _genau(datei, _FESTE_GROESSE[art])
    if art in (4, 10):
        return int.from_bytes(rohdaten, "little", signed=False)
    if art in (5, 11):
        return int.from_bytes(rohdaten, "little", signed=True)
    if art == 6:
        return struct.unpack("<f", rohdaten)[0]
    if art == 12:
        return struct.unpack("<d", rohdaten)[0]
    return int.from_bytes(rohdaten, "little", signed=False)


def _wert_ueberspringen(datei, art: int) -> None:
    """Moves the file position past one value without decoding it — most
    of the header, and the only part a vocabulary-sized array costs."""
    if art == _ZEICHENKETTE:
        _zeichenkette(datei)
        return
    if art == _FELD:
        elementart = _u32(datei)
        anzahl = _u64(datei)
        for _ in range(anzahl):
            _wert_ueberspringen(datei, elementart)
        return
    datei.seek(_FESTE_GROESSE[art], 1)


def _kopf_lesen(datei) -> bool:
    if _genau(datei, 4) != b"GGUF":
        return False
    version = _u32(datei)
    if version not in (2, 3):
        return False
    _u64(datei)  # tensor count — the metadata this reader wants comes first
    schluessel_anzahl = _u64(datei)
    if schluessel_anzahl > _HOECHSTE_SCHLUESSEL_ANZAHL:
        return False
    for _ in range(schluessel_anzahl):
        schluessel = _zeichenkette(datei)
        art = _u32(datei)
        if schluessel.endswith(_SCHLUESSEL_ENDUNG):
            wert = _wert_lesen(datei, art)
            return isinstance(wert, (int, float)) and not isinstance(wert, bool) and wert > 0
        _wert_ueberspringen(datei, art)
    return False
