"""The image-metadata switch: on strips, off keeps, and it ships on.

The switch is written through the real settings route in at least one test on
purpose: that route discards falsy values as "unset", and a switch stored as a
bare bool could never be turned off against a default of on. The route is the
part that has to be proven, not just the stripping.
"""

from __future__ import annotations

import struct
import zlib

from app.bildschutz import SCHLUESSEL


def _block(typ: bytes, koerper: bytes) -> bytes:
    pruef = zlib.crc32(typ + koerper) & 0xFFFFFFFF
    return struct.pack(">I", len(koerper)) + typ + koerper + struct.pack(">I", pruef)


def _png_mit_text() -> bytes:
    """A real, parseable PNG that carries a text chunk to strip."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _block(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    text = _block(b"tEXt", b"parameters\x00GEHEIM-prompt-und-seed")
    idat = _block(b"IDAT", zlib.compress(b"\x00\x11\x22\x33"))
    iend = _block(b"IEND", b"")
    return sig + ihdr + text + idat + iend


PNG = _png_mit_text()


def _hochladen_und_holen(client) -> bytes:
    antwort = client.post(
        "/api/v1/images", content=PNG, headers={"Content-Type": "image/png"}
    )
    assert antwort.status_code == 201
    name = antwort.json()["bild"]
    return client.get(f"/api/v1/images/{name}").content


def test_standard_putzt_hochgeladene_bilder(client):
    # Nothing set — the default must be on, so the text chunk is gone.
    client.app.state.repositories.einstellungen.loeschen("global", SCHLUESSEL)
    inhalt = _hochladen_und_holen(client)
    assert b"tEXt" not in inhalt
    assert b"GEHEIM" not in inhalt
    assert inhalt != PNG


def test_schalter_aus_laesst_alles_stehen(client):
    client.app.state.repositories.einstellungen.setzen("global", SCHLUESSEL, {"an": False})
    inhalt = _hochladen_und_holen(client)
    # Switch off — the picture is stored exactly as it came in.
    assert inhalt == PNG


def test_schalter_an_putzt_wieder(client):
    client.app.state.repositories.einstellungen.setzen("global", SCHLUESSEL, {"an": True})
    inhalt = _hochladen_und_holen(client)
    assert b"tEXt" not in inhalt
    assert b"GEHEIM" not in inhalt


def test_schalter_aus_ueber_die_api_bleibt_aus(client):
    """Through the real route: off has to survive the falsy-is-unset rule, or
    the switch could never be turned off against a default of on."""
    gesetzt = client.put(
        "/api/v1/settings/global/bildmetadaten", json={"wert": {"an": False}}
    )
    assert gesetzt.status_code == 200
    gespeichert = client.get("/api/v1/settings/global/bildmetadaten").json()["wert"]
    assert gespeichert == {"an": False}
    assert _hochladen_und_holen(client) == PNG


def test_schalter_an_ueber_die_api_putzt(client):
    gesetzt = client.put(
        "/api/v1/settings/global/bildmetadaten", json={"wert": {"an": True}}
    )
    assert gesetzt.status_code == 200
    inhalt = _hochladen_und_holen(client)
    assert b"tEXt" not in inhalt
