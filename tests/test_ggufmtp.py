"""Reading a GGUF file's own header for embedded multi-token-prediction
weights.

No real model file is downloaded here — a handful of bytes in the exact
shape llama.cpp writes is the whole test. What matters is that the reader
trusts only the header's own key, never the name of the file it opened,
and that a header which is not what it claims to be answers "no" instead
of raising.
"""

from __future__ import annotations

import struct
from pathlib import Path

from app.ggufmtp import traegt_eingebettetes_mtp

_ZEICHENKETTE = 8
_FELD = 9
_U32 = 4


def _wert_bytes(art: int, wert) -> bytes:
    if art == _ZEICHENKETTE:
        rohdaten = wert.encode("utf-8")
        return struct.pack("<Q", len(rohdaten)) + rohdaten
    if art == _U32:
        return struct.pack("<I", wert)
    if art == _FELD:
        elementart, werte = wert
        stueck = struct.pack("<I", elementart) + struct.pack("<Q", len(werte))
        for eintrag in werte:
            stueck += _wert_bytes(elementart, eintrag)
        return stueck
    raise ValueError(f"unhandled type in this test's own builder: {art}")


def _gguf_bytes(paare: list[tuple[str, int, object]], *, version: int = 3) -> bytes:
    """The bytes of a minimal GGUF header, built the same way the real
    format is laid out — never the shortcuts an eager parser would allow."""
    kopf = bytearray(b"GGUF")
    kopf += struct.pack("<I", version)
    kopf += struct.pack("<Q", 0)  # tensor count — irrelevant to this reader
    kopf += struct.pack("<Q", len(paare))
    for schluessel, art, wert in paare:
        roh = schluessel.encode("utf-8")
        kopf += struct.pack("<Q", len(roh)) + roh
        kopf += struct.pack("<I", art)
        kopf += _wert_bytes(art, wert)
    return bytes(kopf)


def _datei(tmp_path: Path, inhalt: bytes) -> Path:
    pfad = tmp_path / "modell.gguf"
    pfad.write_bytes(inhalt)
    return pfad


def test_eingebettetes_mtp_wird_am_schluessel_erkannt(tmp_path):
    inhalt = _gguf_bytes([
        ("general.architecture", _ZEICHENKETTE, "qwen35moe"),
        ("qwen35moe.block_count", _U32, 41),
        ("qwen35moe.nextn_predict_layers", _U32, 1),
    ])
    assert traegt_eingebettetes_mtp(_datei(tmp_path, inhalt)) is True


def test_ein_gewoehnliches_modell_traegt_kein_mtp(tmp_path):
    inhalt = _gguf_bytes([
        ("general.architecture", _ZEICHENKETTE, "qwen35moe"),
        ("qwen35moe.block_count", _U32, 41),
    ])
    assert traegt_eingebettetes_mtp(_datei(tmp_path, inhalt)) is False


def test_die_schicht_null_zaehlt_nicht_als_eingebettet(tmp_path):
    # Present but zero is the architecture saying "I could, this build
    # doesn't" — the same as not being there at all.
    inhalt = _gguf_bytes([("qwen35moe.nextn_predict_layers", _U32, 0)])
    assert traegt_eingebettetes_mtp(_datei(tmp_path, inhalt)) is False


def test_ein_grosses_feld_davor_wird_sauber_uebersprungen(tmp_path):
    # A vocabulary-sized string array standing before the marker — the
    # shape every real chat model's header actually has.
    woerter = [f"tok{i}" for i in range(500)]
    inhalt = _gguf_bytes([
        ("tokenizer.ggml.tokens", _FELD, (_ZEICHENKETTE, woerter)),
        ("deepseek2.nextn_predict_layers", _U32, 1),
    ])
    assert traegt_eingebettetes_mtp(_datei(tmp_path, inhalt)) is True


def test_kein_gguf_ist_kein_absturz(tmp_path):
    pfad = _datei(tmp_path, b"not a gguf file at all, just some bytes")
    assert traegt_eingebettetes_mtp(pfad) is False


def test_ein_abgeschnittener_kopf_ist_kein_absturz(tmp_path):
    voll = _gguf_bytes([("qwen35moe.nextn_predict_layers", _U32, 1)])
    inhalt = voll[: len(voll) - 5]
    assert traegt_eingebettetes_mtp(_datei(tmp_path, inhalt)) is False


def test_eine_unbekannte_version_wird_abgelehnt(tmp_path):
    inhalt = _gguf_bytes([("qwen35moe.nextn_predict_layers", _U32, 1)], version=1)
    assert traegt_eingebettetes_mtp(_datei(tmp_path, inhalt)) is False


def test_eine_fehlende_datei_ist_kein_absturz(tmp_path):
    assert traegt_eingebettetes_mtp(tmp_path / "gibtsnicht.gguf") is False
