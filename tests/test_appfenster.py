"""The own-window opener: picks a browser, never launches one here."""

from __future__ import annotations

from app import appfenster


def test_ohne_browser_kommt_ein_ehrliches_nein(monkeypatch):
    monkeypatch.setattr(appfenster, "_MAC_KANDIDATEN", [])
    monkeypatch.setattr(appfenster, "_WIN_KANDIDATEN", [])
    monkeypatch.setattr(appfenster, "_PATH_KANDIDATEN", [])
    assert appfenster.oeffnen("http://127.0.0.1:8090/app/") is False


def test_ein_gefundener_browser_wird_als_fenster_gestartet(monkeypatch, tmp_path):
    programm = tmp_path / "chrome"
    programm.write_text("")

    befehle = []
    monkeypatch.setattr(appfenster, "_programm", lambda: str(programm))
    monkeypatch.setattr(
        appfenster.subprocess, "Popen", lambda befehl, **_: befehle.append(befehl)
    )

    assert appfenster.oeffnen("http://127.0.0.1:8090/app/") is True
    assert befehle == [[str(programm), "--app=http://127.0.0.1:8090/app/"]]


def test_ein_kaputter_start_faellt_auf_den_tab_zurueck(monkeypatch):
    def scheitert(*_a, **_k):
        raise OSError("weg")

    monkeypatch.setattr(appfenster, "_programm", lambda: "/gibt/es/nicht")
    monkeypatch.setattr(appfenster.subprocess, "Popen", scheitert)
    assert appfenster.oeffnen("http://127.0.0.1:8090/app/") is False


def test_der_pfadfund_prueft_bekannte_namen(monkeypatch):
    gesucht = []
    monkeypatch.setattr(appfenster, "_MAC_KANDIDATEN", [])
    monkeypatch.setattr(appfenster, "_WIN_KANDIDATEN", [])
    monkeypatch.setattr(
        appfenster.shutil, "which", lambda name: gesucht.append(name) or None
    )
    assert appfenster._programm() is None
    assert "chromium" in gesucht and "google-chrome" in gesucht
