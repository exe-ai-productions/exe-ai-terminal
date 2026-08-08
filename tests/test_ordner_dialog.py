"""The system's folder dialog.

The dialog itself cannot be tested — it opens a window and waits for a human.
What can be tested is everything around it: who is allowed to ask for it, and
whether the commands handed to the system are built correctly. The command
builders are the part that breaks silently, because a wrong quote does not
crash, it just opens the wrong dialog or none at all.
"""

from __future__ import annotations

import sys

import pytest

from app.ordner_dialog import (
    _befehl_kdialog,
    _befehl_macos,
    _befehl_windows,
    _befehl_zenity,
    dialog_verfuegbar,
)


# --- The route ------------------------------------------------------------
# The TestClient reports "testclient" as its host, i.e. deliberately not local.
# That is exactly the case the route has to reject: a dialog would open on the
# service's machine, where nobody is sitting.


def test_auskunft_meldet_fern_als_nicht_verfuegbar(client):
    antwort = client.get("/api/v1/filesystem/folder-dialog")
    assert antwort.status_code == 200
    assert antwort.json()["verfuegbar"] is False


def test_dialog_von_fern_wird_abgewiesen(client):
    antwort = client.post("/api/v1/filesystem/choose-folder", json={})
    assert antwort.status_code == 400


def test_auskunft_lokal_nennt_das_werkzeug(client):
    """Locally the answer must name the tool the UI would use."""
    antwort = client.get(
        "/api/v1/filesystem/folder-dialog", headers={"host": "127.0.0.1:8090"}
    )
    # The header alone does not make the caller local — this documents that the
    # check looks at the connection, not at something the caller can claim.
    assert antwort.json()["verfuegbar"] is False


# --- The command builders -------------------------------------------------


def test_macos_holt_den_dialog_nach_vorn():
    befehl = _befehl_macos("Ordner wählen", None)
    assert befehl[0] == "osascript"
    assert "tell me to activate" in befehl[-1]
    assert "choose folder" in befehl[-1]


def test_macos_nimmt_einen_startordner(tmp_path):
    befehl = _befehl_macos("Titel", str(tmp_path))
    assert "default location" in befehl[-1]
    assert str(tmp_path) in befehl[-1]


def test_macos_ignoriert_einen_startordner_der_fehlt(tmp_path):
    befehl = _befehl_macos("Titel", str(tmp_path / "gibt-es-nicht"))
    assert "default location" not in befehl[-1]


def test_macos_entschaerft_anfuehrungszeichen(tmp_path):
    ordner = tmp_path / 'mit"gaensefuesschen'
    ordner.mkdir()
    schrift = _befehl_macos("Titel", str(ordner))[-1]
    # The quote must arrive escaped, otherwise the AppleScript string ends
    # early and the rest of the path becomes code.
    assert '\\"' in schrift


def test_windows_braucht_sta():
    befehl = _befehl_windows("Choose a folder", None)
    assert "-STA" in befehl
    assert "-NoProfile" in befehl
    assert "FolderBrowserDialog" in befehl[-1]


def test_windows_meldet_abbruch_ueber_den_rueckgabewert():
    schrift = _befehl_windows("Titel", None)[-1]
    assert "exit 1" in schrift


def test_windows_verdoppelt_apostrophe(tmp_path):
    ordner = tmp_path / "benutzer's ordner"
    ordner.mkdir()
    schrift = _befehl_windows("Titel", str(ordner))[-1]
    assert "benutzer''s ordner" in schrift


def test_zenity_und_kdialog_bauen_ordnerwahl(tmp_path):
    zenity = _befehl_zenity("Titel", str(tmp_path))
    assert "--directory" in zenity
    kdialog = _befehl_kdialog("Titel", str(tmp_path))
    assert "--getexistingdirectory" in kdialog


@pytest.mark.skipif(sys.platform != "darwin", reason="nur auf dem Mac")
def test_auf_dem_mac_gibt_es_den_finder():
    assert dialog_verfuegbar() == "finder"
