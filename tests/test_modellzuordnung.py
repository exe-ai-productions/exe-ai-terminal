"""The folder manifest that binds a model to its companions.

What is tested is the part that has to hold: a bond written down comes back
the same, a corrupt note is treated as no note, a name that reaches outside
the folder is refused, and a companion that has since been deleted disappears
from the answer.
"""

from __future__ import annotations

from pathlib import Path

from app import modellzuordnung


# --- Round trip -----------------------------------------------------------


def test_ein_eintrag_kommt_gleich_zurueck(tmp_path: Path):
    (tmp_path / "modell-mmproj-BF16.gguf").write_bytes(b"x")
    (tmp_path / "modell-mtp-Q8.gguf").write_bytes(b"x")

    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "modell-mmproj-BF16.gguf")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mtp", "modell-mtp-Q8.gguf")

    assert modellzuordnung.fuer(tmp_path, "modell.gguf") == {
        "mmproj": "modell-mmproj-BF16.gguf",
        "mtp": "modell-mtp-Q8.gguf",
    }


def test_ein_zweiter_eintrag_ersetzt_die_rolle(tmp_path: Path):
    (tmp_path / "alt-mmproj.gguf").write_bytes(b"x")
    (tmp_path / "neu-mmproj.gguf").write_bytes(b"x")

    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "alt-mmproj.gguf")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "neu-mmproj.gguf")

    assert modellzuordnung.fuer(tmp_path, "modell.gguf")["mmproj"] == "neu-mmproj.gguf"


def test_ohne_note_ist_alles_leer(tmp_path: Path):
    assert modellzuordnung.lade(tmp_path) == {}
    assert modellzuordnung.fuer(tmp_path, "modell.gguf") == {"mmproj": None, "mtp": None}


# --- A note that cannot be trusted ----------------------------------------


def test_eine_kaputte_note_gilt_als_keine(tmp_path: Path):
    (tmp_path / modellzuordnung.ZUORDNUNG_DATEI).write_text("{ this is not json")
    # A corrupt file must never raise — the runner falls back to its heuristic.
    assert modellzuordnung.lade(tmp_path) == {}
    assert modellzuordnung.fuer(tmp_path, "modell.gguf") == {"mmproj": None, "mtp": None}


def test_ein_name_der_hinausfuehrt_wird_verworfen(tmp_path: Path):
    modellzuordnung.eintragen(tmp_path, "../boese.gguf", "mmproj", "gut.gguf")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "../boese.gguf")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "unter/tief.gguf")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", ".versteckt.gguf")
    # None of the four unsafe names may have been written.
    assert modellzuordnung.lade(tmp_path) == {}


def test_eine_unbekannte_rolle_wird_ignoriert(tmp_path: Path):
    (tmp_path / "modell-mmproj.gguf").write_bytes(b"x")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "sonstwas", "modell-mmproj.gguf")
    assert modellzuordnung.lade(tmp_path) == {}


# --- A companion that is gone ---------------------------------------------


def test_ein_geloeschter_begleiter_faellt_raus(tmp_path: Path):
    begleiter = tmp_path / "modell-mmproj-BF16.gguf"
    begleiter.write_bytes(b"x")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "modell-mmproj-BF16.gguf")
    assert modellzuordnung.fuer(tmp_path, "modell.gguf")["mmproj"] == "modell-mmproj-BF16.gguf"

    # The file leaves; the answer forgets it, though the note still holds it.
    begleiter.unlink()
    assert modellzuordnung.fuer(tmp_path, "modell.gguf")["mmproj"] is None
    assert "modell.gguf" in modellzuordnung.lade(tmp_path)


def test_entfernen_loescht_den_ganzen_eintrag(tmp_path: Path):
    (tmp_path / "modell-mmproj.gguf").write_bytes(b"x")
    modellzuordnung.eintragen(tmp_path, "modell.gguf", "mmproj", "modell-mmproj.gguf")
    modellzuordnung.entfernen(tmp_path, "modell.gguf")
    assert "modell.gguf" not in modellzuordnung.lade(tmp_path)
