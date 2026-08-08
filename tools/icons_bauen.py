#!/usr/bin/env python3
"""Generates the PWA icons from the same geometry as the vector files.

Why drawn instead of converted: none of the machines involved has an SVG
converter, and an image converted after the fact is blurrier at such
small sizes anyway than one created directly in the target raster.

Drawing happens at four times the size and is then scaled down — that
gives clean edges without stair-stepping. Pillow does not add round line
caps on its own, so a circle sits at every line end.

    python3 tools/icons_bauen.py

Creates in static/icons/:
    icon-192.png            home screen, smaller devices
    icon-512.png            home screen, large rendering
    icon-maskable-512.png   for systems that crop the icon

Also creates deploy/icon.icns for the macOS app bundle. Same mark, but
with a margin around the tile: a Mac icon floats on the desktop grid, and
a full-bleed square would look a size too big next to every other
application.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ZIEL = Path(__file__).resolve().parent.parent / "static" / "icons"
ICNS_ZIEL = Path(__file__).resolve().parent.parent / "deploy" / "icon.icns"
ICO_ZIEL = Path(__file__).resolve().parent.parent / "deploy" / "icon.ico"

HINTERGRUND = (20, 20, 19, 255)   # #141413
MARKE = (236, 235, 230, 255)      # #ecebe6

UEBERABTASTUNG = 4

# Geometry of the mark on the 80x64 grid of the vector files.
RASTER_B, RASTER_H = 80.0, 64.0
RAHMEN = (4, 4, 76, 60)
RAHMEN_RADIUS = 15
RAHMEN_STRICH = 5.5
CHEVRON = [(20, 22), (34, 32), (20, 42)]
GRUNDLINIE = [(42, 42), (58, 42)]
INNEN_STRICH = 5


def _linie(zeichner: ImageDraw.ImageDraw, punkte, breite: float, farbe) -> None:
    """Polyline with round joints and round caps."""
    zeichner.line(punkte, fill=farbe, width=round(breite), joint="curve")
    radius = breite / 2
    for x, y in punkte:
        zeichner.ellipse((x - radius, y - radius, x + radius, y + radius), fill=farbe)


def icon_bauen(groesse: int, markenanteil: float, dateiname: str) -> Path:
    """markenanteil: how wide the mark becomes relative to the tile."""
    gross = groesse * UEBERABTASTUNG
    bild = Image.new("RGBA", (gross, gross), (0, 0, 0, 0))
    zeichner = ImageDraw.Draw(bild)

    # Tile. The radius follows the platforms' guidelines
    # (about 22 percent of the edge length).
    zeichner.rounded_rectangle(
        (0, 0, gross - 1, gross - 1), radius=gross * 0.225, fill=HINTERGRUND
    )

    # Fit the mark centered.
    skala = (gross * markenanteil) / RASTER_B
    versatz_x = (gross - RASTER_B * skala) / 2
    versatz_y = (gross - RASTER_H * skala) / 2

    def p(x: float, y: float) -> tuple[float, float]:
        return (versatz_x + x * skala, versatz_y + y * skala)

    x0, y0, x1, y1 = RAHMEN
    zeichner.rounded_rectangle(
        [p(x0, y0), p(x1, y1)],
        radius=RAHMEN_RADIUS * skala,
        outline=MARKE,
        width=max(1, round(RAHMEN_STRICH * skala)),
    )
    _linie(zeichner, [p(*punkt) for punkt in CHEVRON], INNEN_STRICH * skala, MARKE)
    _linie(zeichner, [p(*punkt) for punkt in GRUNDLINIE], INNEN_STRICH * skala, MARKE)

    ZIEL.mkdir(parents=True, exist_ok=True)
    pfad = ZIEL / dateiname
    bild.resize((groesse, groesse), Image.LANCZOS).save(pfad, "PNG", optimize=True)
    return pfad


def _mac_kachel(groesse: int) -> Image.Image:
    """One macOS icon raster: tile with a margin, mark centered on it.

    The margin is the difference between a web tile and a desktop icon —
    macOS draws no frame of its own, but every system icon leaves about a
    tenth of the canvas empty on each side.
    """
    gross = groesse * UEBERABTASTUNG
    bild = Image.new("RGBA", (gross, gross), (0, 0, 0, 0))
    zeichner = ImageDraw.Draw(bild)

    rand = gross * 0.10
    kachel = (rand, rand, gross - rand - 1, gross - rand - 1)
    kantenlaenge = kachel[2] - kachel[0]
    zeichner.rounded_rectangle(kachel, radius=kantenlaenge * 0.225, fill=HINTERGRUND)

    skala = (kantenlaenge * 0.58) / RASTER_B
    versatz_x = (gross - RASTER_B * skala) / 2
    versatz_y = (gross - RASTER_H * skala) / 2

    def p(x: float, y: float) -> tuple[float, float]:
        return (versatz_x + x * skala, versatz_y + y * skala)

    x0, y0, x1, y1 = RAHMEN
    zeichner.rounded_rectangle(
        [p(x0, y0), p(x1, y1)],
        radius=RAHMEN_RADIUS * skala,
        outline=MARKE,
        width=max(1, round(RAHMEN_STRICH * skala)),
    )
    _linie(zeichner, [p(*punkt) for punkt in CHEVRON], INNEN_STRICH * skala, MARKE)
    _linie(zeichner, [p(*punkt) for punkt in GRUNDLINIE], INNEN_STRICH * skala, MARKE)

    return bild.resize((groesse, groesse), Image.LANCZOS)


def icns_bauen() -> Path:
    """The macOS icon file, all sizes drawn in their own raster."""
    groessen = [16, 32, 64, 128, 256, 512, 1024]
    bilder = [_mac_kachel(g) for g in groessen]
    ICNS_ZIEL.parent.mkdir(parents=True, exist_ok=True)
    bilder[-1].save(ICNS_ZIEL, format="ICNS", append_images=bilder[:-1])
    return ICNS_ZIEL


def ico_bauen() -> Path:
    """The Windows icon file — the full tile, like every taskbar icon.

    Windows crops nothing and adds no margin of its own, so here the web
    tile's full-bleed geometry is the right one.
    """
    basis = 256
    gross = basis * UEBERABTASTUNG
    bild = Image.new("RGBA", (gross, gross), (0, 0, 0, 0))
    zeichner = ImageDraw.Draw(bild)
    zeichner.rounded_rectangle(
        (0, 0, gross - 1, gross - 1), radius=gross * 0.225, fill=HINTERGRUND
    )
    skala = (gross * 0.58) / RASTER_B
    versatz_x = (gross - RASTER_B * skala) / 2
    versatz_y = (gross - RASTER_H * skala) / 2

    def p(x: float, y: float) -> tuple[float, float]:
        return (versatz_x + x * skala, versatz_y + y * skala)

    x0, y0, x1, y1 = RAHMEN
    zeichner.rounded_rectangle(
        [p(x0, y0), p(x1, y1)],
        radius=RAHMEN_RADIUS * skala,
        outline=MARKE,
        width=max(1, round(RAHMEN_STRICH * skala)),
    )
    _linie(zeichner, [p(*punkt) for punkt in CHEVRON], INNEN_STRICH * skala, MARKE)
    _linie(zeichner, [p(*punkt) for punkt in GRUNDLINIE], INNEN_STRICH * skala, MARKE)

    ICO_ZIEL.parent.mkdir(parents=True, exist_ok=True)
    bild.resize((basis, basis), Image.LANCZOS).save(
        ICO_ZIEL, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    return ICO_ZIEL


def main() -> None:
    # For maskable, some systems crop up to 20 percent — the mark therefore
    # stays noticeably smaller and thus within the safe area.
    for groesse, anteil, name in [
        (192, 0.58, "icon-192.png"),
        (512, 0.58, "icon-512.png"),
        (512, 0.44, "icon-maskable-512.png"),
    ]:
        pfad = icon_bauen(groesse, anteil, name)
        print(f"{pfad.name:26} {groesse}x{groesse}  {pfad.stat().st_size / 1024:.1f} kB")

    pfad = icns_bauen()
    print(f"{pfad.name:26} icns       {pfad.stat().st_size / 1024:.1f} kB")
    pfad = ico_bauen()
    print(f"{pfad.name:26} ico        {pfad.stat().st_size / 1024:.1f} kB")


if __name__ == "__main__":
    main()
