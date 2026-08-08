"""Fetching a model file.

Nothing is downloaded here — the answer is faked. What is tested is our
side: which names are allowed through, that a half file never looks like a
model, and that a failure leaves nothing behind.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

from app import modelldownload
from app.modelldownload import DownloadFehler, Modelldownload


class FalscherStrom:
    """Stands in for httpx.stream and hands out fixed bytes."""

    def __init__(self, daten: bytes, fehler: Exception | None = None):
        self._daten = daten
        self._fehler = fehler
        self.headers = {"content-length": str(len(daten))}
        self.adresse: str | None = None

    def __call__(self, methode, adresse, **kwargs):
        self.adresse = adresse
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self._fehler:
            raise self._fehler

    def iter_bytes(self, groesse):
        for i in range(0, len(self._daten), groesse):
            yield self._daten[i : i + groesse]


def warten_bis(bedingung, sekunden=3.0):
    """The download runs in a thread; the test waits for it, briefly."""
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def strom(monkeypatch):
    def setzen(daten=b"x" * 5000, fehler=None):
        falsch = FalscherStrom(daten, fehler)
        monkeypatch.setattr(modelldownload.httpx, "stream", falsch)
        return falsch
    return setzen


# --- The normal case ------------------------------------------------------


def test_ein_modell_landet_im_ordner(tmp_path, strom):
    falsch = strom(b"y" * 4096)
    download = Modelldownload(tmp_path)
    download.starten("prism-ml/Bonsai-27B-gguf", "Bonsai-27B-Q1_0.gguf")

    assert warten_bis(lambda: download.stand().fertig)
    ziel = tmp_path / "Bonsai-27B-Q1_0.gguf"
    assert ziel.read_bytes() == b"y" * 4096
    assert falsch.adresse.endswith("/prism-ml/Bonsai-27B-gguf/resolve/main/Bonsai-27B-Q1_0.gguf")


def test_waehrend_es_laeuft_heisst_die_datei_anders(tmp_path, strom):
    strom(b"z" * 3_000_000)
    download = Modelldownload(tmp_path)
    download.starten("repo", "gross.gguf")

    # A half file must never look like a model — the runner would take it.
    assert warten_bis(lambda: (tmp_path / "gross.gguf.teil").exists() or download.stand().fertig)
    assert warten_bis(lambda: download.stand().fertig)
    assert not (tmp_path / "gross.gguf.teil").exists()


# --- Where it has to refuse -----------------------------------------------


@pytest.mark.parametrize("datei", ["../weg.gguf", "unter/tief.gguf", ".versteckt.gguf"])
def test_ein_name_ist_nie_ein_pfad(tmp_path, datei):
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", datei)
    assert fehler.value.grund == "name"


@pytest.mark.parametrize("datei", ["modell.safetensors", "modell.bin", "modell"])
def test_nur_gguf_wird_geholt(tmp_path, datei):
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", datei)
    assert fehler.value.grund == "endung"


def test_was_schon_da_ist_wird_nicht_nochmal_geholt(tmp_path):
    (tmp_path / "da.gguf").write_bytes(b"schon da")
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", "da.gguf")
    assert fehler.value.grund == "schon_da"


# --- When it goes wrong ---------------------------------------------------


def test_ein_fehler_laesst_nichts_liegen(tmp_path, strom):
    strom(b"", httpx.HTTPStatusError("weg", request=None, response=None))
    download = Modelldownload(tmp_path)
    download.starten("repo", "kaputt.gguf")

    assert warten_bis(lambda: download.stand().fehler is not None)
    assert download.stand().fehler == "fehlgeschlagen"
    assert list(tmp_path.iterdir()) == []


def test_der_anteil_bleibt_bei_null_ohne_groesse(tmp_path):
    stand = modelldownload.Fortschritt(datei="x.gguf", geladen=5, gesamt=0)
    assert stand.anteil == 0.0


def test_der_anteil_rechnet(tmp_path):
    stand = modelldownload.Fortschritt(datei="x.gguf", geladen=25, gesamt=100)
    assert stand.anteil == 0.25


def test_der_zielname_darf_vom_fernen_abweichen(tmp_path, strom):
    # Several repositories call their projector plainly mmproj-BF16.gguf;
    # the local name carries the model, so two of those never collide.
    falsch = strom(b"abc")
    download = Modelldownload(tmp_path)
    download.starten("wer/was", "mmproj-BF16.gguf", ziel="modell-mmproj-BF16.gguf")
    assert warten_bis(lambda: download.stand().fertig)
    assert (tmp_path / "modell-mmproj-BF16.gguf").read_bytes() == b"abc"
    assert not (tmp_path / "mmproj-BF16.gguf").exists()
    # The address keeps the remote name — only the local file is renamed.
    assert falsch.adresse.endswith("/wer/was/resolve/main/mmproj-BF16.gguf")


def test_auch_der_zielname_ist_nie_ein_pfad(tmp_path):
    download = Modelldownload(tmp_path)
    try:
        download.starten("wer/was", "gut.gguf", ziel="../boese.gguf")
        raise AssertionError("kein Fehler")
    except DownloadFehler as fehler:
        assert fehler.grund == "name"


def test_schon_da_zaehlt_fuer_den_zielnamen(tmp_path):
    (tmp_path / "da-mmproj.gguf").write_bytes(b"x")
    download = Modelldownload(tmp_path)
    try:
        download.starten("wer/was", "mmproj-BF16.gguf", ziel="da-mmproj.gguf")
        raise AssertionError("kein Fehler")
    except DownloadFehler as fehler:
        assert fehler.grund == "schon_da"
