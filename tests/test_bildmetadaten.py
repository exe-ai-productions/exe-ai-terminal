"""The strip step must leave a picture with pixels and nothing else."""

from __future__ import annotations

import struct
import zlib

from app.bildmetadaten import metadaten_entfernen

_PNG_SIGNATUR = b"\x89PNG\r\n\x1a\n"


def _png_block(typ: bytes, koerper: bytes) -> bytes:
    """One PNG chunk with a correct length and CRC, as a real file has."""
    pruef = zlib.crc32(typ + koerper) & 0xFFFFFFFF
    return struct.pack(">I", len(koerper)) + typ + koerper + struct.pack(">I", pruef)


def _jpeg_marker(marker: int, koerper: bytes) -> bytes:
    """One JPEG marker segment with its length, as a real file has."""
    return bytes([0xFF, marker]) + struct.pack(">H", len(koerper) + 2) + koerper


def _png_mit_metadaten() -> tuple[bytes, bytes]:
    """A tiny PNG that carries every kind of text/EXIF/time chunk."""
    ihdr = _png_block(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = _png_block(b"IDAT", zlib.compress(b"\x00\x11\x22\x33"))
    iend = _png_block(b"IEND", b"")
    metadaten = (
        _png_block(b"tEXt", b"parameters\x00GEHEIM-prompt-und-seed")
        + _png_block(b"zTXt", b"note\x00\x00" + zlib.compress(b"GEHEIM-komprimiert"))
        + _png_block(b"iTXt", b"XML\x00\x00\x00\x00\x00GEHEIM-xmp")
        + _png_block(b"eXIf", b"GEHEIM-exif-block")
        + _png_block(b"tIME", struct.pack(">HBBBBB", 2026, 8, 20, 11, 34, 0))
    )
    png = _PNG_SIGNATUR + ihdr + metadaten + idat + iend
    return png, idat


def test_png_verliert_jede_metadate_und_behaelt_die_pixel():
    png, idat = _png_mit_metadaten()
    sauber = metadaten_entfernen(png)

    for typ in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"):
        assert typ not in sauber
    assert b"GEHEIM" not in sauber

    # The picture itself is byte-for-byte the same.
    assert sauber.startswith(_PNG_SIGNATUR)
    assert b"IHDR" in sauber
    assert idat in sauber
    assert sauber.endswith(_png_block(b"IEND", b""))


def test_png_putzen_ist_wiederholbar():
    png, _ = _png_mit_metadaten()
    einmal = metadaten_entfernen(png)
    # A file that is already clean must come back untouched.
    assert metadaten_entfernen(einmal) == einmal


def test_jpeg_verliert_exif_und_kommentar_behaelt_farbe_und_pixel():
    soi = b"\xff\xd8"
    app1 = _jpeg_marker(0xE1, b"Exif\x00\x00GEHEIM-gps")
    app0 = _jpeg_marker(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    kommentar = _jpeg_marker(0xFE, b"GEHEIM-kommentar")
    scan = b"\xff\xda" + struct.pack(">H", 3) + b"\x00" + b"PIXELDATEN"
    eoi = b"\xff\xd9"
    jpg = soi + app1 + app0 + kommentar + scan + eoi

    sauber = metadaten_entfernen(jpg)

    assert b"Exif" not in sauber
    assert b"GEHEIM" not in sauber
    assert b"JFIF" in sauber  # the colour/JFIF header stays for a true picture
    assert sauber.startswith(b"\xff\xd8") and sauber.endswith(b"\xff\xd9")
    assert b"PIXELDATEN" in sauber
    assert metadaten_entfernen(sauber) == sauber


def test_fremdes_format_bleibt_unangetastet():
    fremd = b"this is not an image at all"
    assert metadaten_entfernen(fremd) == fremd


def test_abgeschnittenes_png_wird_nicht_kaputtgemacht():
    png, _ = _png_mit_metadaten()
    stumpf = png[:-4]  # cut into the final chunk
    # A broken input is handed back as it came, never turned into garbage.
    assert metadaten_entfernen(stumpf) == stumpf
