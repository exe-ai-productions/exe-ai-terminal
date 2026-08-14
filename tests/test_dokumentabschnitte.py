"""Where the section search meets the chat.

This is the layer that decides WHETHER the expensive part runs at all, and
every one of its answers has to be safe when something is missing. A machine
without the embedding program, a model that was moved, a switch turned off
after the fact — none of them may end with a hundred-page document being
sent whole into a context that has room for eight thousand tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app import dokumentabschnitte, einbettung


@dataclass
class _Dokument:
    id: str = "dok"
    filename: str = "bericht.pdf"
    extracted_text: str = ""


class _Abschnitte:
    """Just enough repository to answer the two questions asked of it."""

    def __init__(self, gespeichert=None):
        self.gespeichert = gespeichert or {}
        self.geschrieben = None
        self.gefragt_nach_modell = None

    def auflisten(self, document_id, *, modell=None):
        self.gefragt_nach_modell = modell
        return self.gespeichert.get(document_id, [])

    def speichern(self, *, document_id, abschnitte, modell=""):
        self.geschrieben = (document_id, abschnitte)
        self.modell = modell
        return len(abschnitte)


class _Repositories:
    def __init__(self, an=True, gespeichert=None):
        self.abschnitte = _Abschnitte(gespeichert)
        self.einstellungen = _Einstellungen(an)


class _Einstellungen:
    def __init__(self, an: bool):
        self.an = an
        self.gefragt = []

    def zusammengefuehrt(self, schluessel, vorgabe=None, modell=None, chat=None):
        self.gefragt.append((schluessel, modell, chat))
        return {"an": self.an}


@dataclass
class _Config:
    datenverzeichnis: Path
    app: object = None

    def pfad(self, _wert):
        return self.datenverzeichnis / "einbettungsmodelle"


def _config(tmp_path: Path) -> _Config:
    class _App:
        einbettungsmodelle_verzeichnis = "./einbettungsmodelle"

    return _Config(datenverzeichnis=tmp_path, app=_App())


def test_ohne_programm_wird_nichts_eingebettet(tmp_path, monkeypatch):
    """A machine without the program keeps the old behaviour, silently."""
    monkeypatch.setattr(einbettung, "programm_finden", lambda *a, **k: None)
    dokument = _Dokument(extracted_text="x " * 20000)
    repositories = _Repositories()
    assert (
        dokumentabschnitte.einbetten(_config(tmp_path), None, repositories, dokument) == 0
    )
    assert repositories.abschnitte.geschrieben is None


def test_kurze_dokumente_ruehren_das_programm_nicht_an(tmp_path, monkeypatch):
    """Below the threshold nothing is started — not even a lookup."""

    def nie(*_a, **_k):
        raise AssertionError("darf nicht gerufen werden")

    monkeypatch.setattr(einbettung, "programm_finden", nie)
    dokument = _Dokument(extracted_text="kurz")
    assert (
        dokumentabschnitte.einbetten(_config(tmp_path), None, _Repositories(), dokument) == 0
    )


def test_ein_scheiterndes_programm_reisst_den_upload_nicht_um(tmp_path, monkeypatch):
    monkeypatch.setattr(einbettung, "programm_finden", lambda *a, **k: Path("/sd"))
    monkeypatch.setattr(einbettung, "modell_finden", lambda *_a: Path("/m.gguf"))

    def kaputt(*_a, **_k):
        raise einbettung.EinbettungFehler("einbettung.gescheitert")

    monkeypatch.setattr(einbettung, "vektoren", kaputt)
    dokument = _Dokument(extracted_text="wort " * 20000)
    assert (
        dokumentabschnitte.einbetten(_config(tmp_path), None, _Repositories(), dokument) == 0
    )


def test_der_waehler_fragt_den_schalter_im_richtigen_bereich(tmp_path, monkeypatch):
    """Model and chat, not just the global default.

    The upload asks in the chat's scope. A chooser that asked globally would
    answer differently from the decision that shaped the document — and the
    disagreement would show up as a whole book in the context.
    """
    monkeypatch.setattr(einbettung, "programm_finden", lambda *a, **k: None)
    repositories = _Repositories()
    dokumentabschnitte.kontext_waehler(
        _config(tmp_path), None, repositories, "eine Frage", "gemma", "chat-7"
    )
    assert repositories.einstellungen.gefragt == [("einbettung", "gemma", "chat-7")]


def test_ausgeschalteter_schalter_waehlt_nichts_aus(tmp_path, monkeypatch):
    def nie(*_a, **_k):
        raise AssertionError("darf nicht gerufen werden")

    monkeypatch.setattr(einbettung, "programm_finden", nie)
    waehler = dokumentabschnitte.kontext_waehler(
        _config(tmp_path), None, _Repositories(an=False), "eine Frage"
    )
    assert waehler(_Dokument()) is None


def test_der_waehler_liefert_die_passenden_abschnitte(tmp_path, monkeypatch):
    monkeypatch.setattr(einbettung, "programm_finden", lambda *a, **k: Path("/e"))
    monkeypatch.setattr(einbettung, "modell_finden", lambda *_a: Path("/m.gguf"))
    monkeypatch.setattr(einbettung, "vektoren", lambda *_a: [[0.0, 1.0]])
    gespeichert = {
        "dok": [
            (1, "über Katzen", [1.0, 0.0]),
            (2, "über Leuchttürme", [0.0, 1.0]),
        ]
    }
    waehler = dokumentabschnitte.kontext_waehler(
        _config(tmp_path), None, _Repositories(gespeichert=gespeichert), "Leuchtturm?"
    )
    text = waehler(_Dokument())
    assert "über Leuchttürme" in text
    assert "bericht.pdf" in text


def test_ein_dokument_ohne_abschnitte_waehlt_nichts_aus(tmp_path, monkeypatch):
    """No sections means: fall back, do not invent an empty selection."""
    monkeypatch.setattr(einbettung, "programm_finden", lambda *a, **k: Path("/e"))
    monkeypatch.setattr(einbettung, "modell_finden", lambda *_a: Path("/m.gguf"))
    monkeypatch.setattr(einbettung, "vektoren", lambda *_a: [[0.0, 1.0]])
    waehler = dokumentabschnitte.kontext_waehler(
        _config(tmp_path), None, _Repositories(), "eine Frage"
    )
    assert waehler(_Dokument()) is None


def test_eine_leere_frage_startet_nichts(tmp_path, monkeypatch):
    def nie(*_a, **_k):
        raise AssertionError("darf nicht gerufen werden")

    monkeypatch.setattr(einbettung, "programm_finden", nie)
    waehler = dokumentabschnitte.kontext_waehler(
        _config(tmp_path), None, _Repositories(), "   "
    )
    assert waehler(_Dokument()) is None
