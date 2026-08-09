"""Fetching the model server itself."""

from __future__ import annotations

import io
import tarfile

import pytest

from app import serverdownload
from app.serverdownload import (
    BUILD,
    Serverdownload,
    ServerdownloadFehler,
    gefundener_server,
    paketname,
)


def test_fuer_diese_maschine_gibt_es_ein_paket():
    # The build machine itself must be coverable, whatever it is.
    assert paketname() is not None


def test_ohne_entpackten_server_wird_nichts_gefunden(tmp_path):
    assert gefundener_server(tmp_path) is None


def test_ein_entpackter_server_wird_gefunden(tmp_path):
    ziel = tmp_path / "llama.cpp" / BUILD / "build" / "bin"
    ziel.mkdir(parents=True)
    (ziel / "llama-server").write_bytes(b"x")
    gefunden = gefundener_server(tmp_path)
    assert gefunden is not None and gefunden.name == "llama-server"


def test_was_schon_da_ist_wird_nicht_nochmal_geholt(tmp_path):
    ziel = tmp_path / "llama.cpp" / BUILD
    ziel.mkdir(parents=True)
    (ziel / "llama-server").write_bytes(b"x")
    download = Serverdownload(tmp_path)
    with pytest.raises(ServerdownloadFehler) as fehler:
        download.starten()
    assert fehler.value.grund == "schon_da"


def test_ohne_paket_fuer_die_maschine_ein_ehrlicher_fehler(tmp_path, monkeypatch):
    monkeypatch.setattr(serverdownload, "paketname", lambda: None)
    with pytest.raises(ServerdownloadFehler) as fehler:
        Serverdownload(tmp_path).starten()
    assert fehler.value.grund == "kein_paket"


class FalscherStrom:
    """Stands in for httpx.stream and delivers a tiny tar archive."""

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


def _archiv_mit_server() -> bytes:
    speicher = io.BytesIO()
    with tarfile.open(fileobj=speicher, mode="w:gz") as tf:
        inhalt = b"#!/bin/sh\n"
        info = tarfile.TarInfo("build/bin/llama-server")
        info.size = len(inhalt)
        tf.addfile(info, io.BytesIO(inhalt))
    return speicher.getvalue()


def test_holen_entpackt_und_findet_den_server(tmp_path, monkeypatch):
    import time

    monkeypatch.setattr(serverdownload.httpx, "stream", FalscherStrom(_archiv_mit_server()))
    download = Serverdownload(tmp_path)
    download.starten()
    ende = time.time() + 5
    while time.time() < ende and download.laeuft():
        time.sleep(0.02)
    stand = download.stand()
    assert stand is not None and stand.fertig and stand.fehler is None
    assert gefundener_server(tmp_path) is not None
