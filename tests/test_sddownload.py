"""Fetching the picture generator itself.

What matters here is the path from a fresh installation to a working
generator: is there a package for this machine, does it land where the
runner looks, does it come out able to run, and does a machine without a
network get an honest sentence instead of a half-unpacked folder.
"""

from __future__ import annotations

import io
import os
import sys
import time
import zipfile

import pytest

from app import bildrunner, sddownload
from app.sddownload import (
    BAU,
    ORDNER,
    PROGRAMM,
    Sddownload,
    SddownloadFehler,
    gefundenes_programm,
    paketname,
)


# --- The package table ----------------------------------------------------


def test_alle_drei_systeme_haben_ein_paket():
    """macOS, Windows and Linux — the three the installers ship for."""
    tisch = sddownload._PAKETE
    for schluessel in (("darwin", "arm64"), ("win32", "amd64"), ("linux", "x86_64")):
        assert schluessel in tisch
        assert tisch[schluessel].endswith(".zip")


def test_ein_intel_mac_bekommt_dasselbe_paket():
    """The macOS package is universal — one file serves both kinds of Mac."""
    tisch = sddownload._PAKETE
    assert tisch[("darwin", "x86_64")] == tisch[("darwin", "arm64")]


def test_die_maschine_wird_erkannt(monkeypatch):
    monkeypatch.setattr(sddownload.sys, "platform", "darwin")
    monkeypatch.setattr(sddownload.platform, "machine", lambda: "arm64")
    assert paketname() == sddownload._PAKETE[("darwin", "arm64")]

    monkeypatch.setattr(sddownload.sys, "platform", "linux")
    monkeypatch.setattr(sddownload.platform, "machine", lambda: "x86_64")
    assert paketname() == sddownload._PAKETE[("linux", "x86_64")]

    # Windows reports its architecture in several spellings; all of them
    # mean the same machine and must not fall through to "no package".
    monkeypatch.setattr(sddownload.sys, "platform", "win32")
    for geschrieben in ("AMD64", "x86_64", "x64"):
        monkeypatch.setattr(sddownload.platform, "machine", lambda g=geschrieben: g)
        assert paketname() == sddownload._PAKETE[("win32", "amd64")]


def test_eine_maschine_ohne_paket_wird_zugegeben(monkeypatch):
    """A refusal is better than downloading something that cannot run."""
    monkeypatch.setattr(sddownload.sys, "platform", "linux")
    monkeypatch.setattr(sddownload.platform, "machine", lambda: "riscv64")
    assert paketname() is None


# --- Where it lands -------------------------------------------------------


def test_ohne_entpacktes_programm_wird_nichts_gefunden(tmp_path):
    assert gefundenes_programm(tmp_path) is None


def test_ein_von_hand_abgelegtes_programm_wird_gefunden(tmp_path):
    ordner = tmp_path / ORDNER
    ordner.mkdir()
    pfad = ordner / PROGRAMM
    pfad.write_bytes(b"x")
    pfad.chmod(0o755)
    assert gefundenes_programm(tmp_path) == pfad


def test_ein_geholtes_programm_wird_unter_dem_bau_gefunden(tmp_path):
    ordner = tmp_path / ORDNER / BAU
    ordner.mkdir(parents=True)
    pfad = ordner / PROGRAMM
    pfad.write_bytes(b"x")
    pfad.chmod(0o755)
    gefunden = gefundenes_programm(tmp_path)
    assert gefunden is not None and gefunden.name == PROGRAMM


def test_der_bildrunner_findet_was_geholt_wurde(tmp_path, monkeypatch):
    """The whole point: the fetch and the search must meet somewhere."""
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: None)
    assert bildrunner.programm_finden(tmp_path) is None
    ordner = tmp_path / ORDNER / BAU
    ordner.mkdir(parents=True)
    pfad = ordner / PROGRAMM
    pfad.write_bytes(b"x")
    pfad.chmod(0o755)
    assert bildrunner.programm_finden(tmp_path) == pfad


# --- The guards before a fetch starts -------------------------------------


def test_was_schon_da_ist_wird_nicht_nochmal_geholt(tmp_path):
    ordner = tmp_path / ORDNER / BAU
    ordner.mkdir(parents=True)
    pfad = ordner / PROGRAMM
    pfad.write_bytes(b"x")
    pfad.chmod(0o755)
    with pytest.raises(SddownloadFehler) as fehler:
        Sddownload(tmp_path).starten()
    assert fehler.value.grund == "schon_da"


def test_ohne_paket_fuer_die_maschine_ein_ehrlicher_fehler(tmp_path, monkeypatch):
    monkeypatch.setattr(sddownload, "paketname", lambda: None)
    with pytest.raises(SddownloadFehler) as fehler:
        Sddownload(tmp_path).starten()
    assert fehler.value.grund == "kein_paket"


# --- The fetch itself -----------------------------------------------------


class FalscherStrom:
    """Stands in for httpx.stream and delivers a tiny zip archive."""

    def __init__(self, daten: bytes):
        self._daten = daten
        self.headers = {"content-length": str(len(daten))}

    def __call__(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_bytes(self, groesse):
        yield self._daten


class KaputterStrom:
    """A machine without a network, as the library reports it."""

    def __call__(self, *a, **k):
        raise OSError("kein Netz")


def _archiv_mit_programm() -> bytes:
    """Flat, like the real packages: the binary and its library side by side."""
    speicher = io.BytesIO()
    with zipfile.ZipFile(speicher, "w") as zf:
        zf.writestr(PROGRAMM, "#!/bin/sh\n")
        zf.writestr("libstable-diffusion.dylib", "x")
    return speicher.getvalue()


def _warten(download: Sddownload) -> None:
    ende = time.time() + 5
    while time.time() < ende and download.laeuft():
        time.sleep(0.02)


def test_holen_entpackt_und_macht_ausfuehrbar(tmp_path, monkeypatch):
    monkeypatch.setattr(sddownload.httpx, "stream", FalscherStrom(_archiv_mit_programm()))
    download = Sddownload(tmp_path)
    download.starten()
    _warten(download)

    stand = download.stand()
    assert stand is not None and stand.fertig and stand.fehler is None

    programm = gefundenes_programm(tmp_path)
    assert programm is not None
    # A zip file carries no permission bits, so an unpacked binary arrives
    # unable to run — which would look exactly like never having fetched it.
    if sys.platform != "win32":
        assert os.access(programm, os.X_OK)
    # And the shared library lies beside it, where the binary looks for it.
    assert (programm.parent / "libstable-diffusion.dylib").is_file()


def test_der_bildrunner_nimmt_das_geholte_programm(tmp_path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: None)
    monkeypatch.setattr(sddownload.httpx, "stream", FalscherStrom(_archiv_mit_programm()))
    download = Sddownload(tmp_path)
    download.starten()
    _warten(download)
    assert bildrunner.Bildrunner(tmp_path).programm is not None


def test_ohne_netz_bleibt_kein_halbes_ergebnis_liegen(tmp_path, monkeypatch):
    monkeypatch.setattr(sddownload.httpx, "stream", KaputterStrom())
    download = Sddownload(tmp_path)
    download.starten()
    _warten(download)

    stand = download.stand()
    assert stand is not None and stand.fehler == "fehlgeschlagen" and not stand.fertig
    # Nothing half-unpacked stays behind, or the next attempt would find
    # something that looks like a generator and is not one.
    assert gefundenes_programm(tmp_path) is None
    assert not list((tmp_path / ORDNER).glob("*" + sddownload.UNFERTIG))


def test_ein_kaputtes_archiv_ist_ein_fehler_und_kein_programm(tmp_path, monkeypatch):
    monkeypatch.setattr(sddownload.httpx, "stream", FalscherStrom(b"das ist kein zip"))
    download = Sddownload(tmp_path)
    download.starten()
    _warten(download)

    stand = download.stand()
    assert stand is not None and stand.fehler == "fehlgeschlagen"
    assert gefundenes_programm(tmp_path) is None
