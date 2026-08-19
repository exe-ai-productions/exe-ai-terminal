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


@pytest.mark.parametrize(
    "datei", ["../weg.gguf", "unter/../weg.gguf", ".versteckt.gguf", "/weg.gguf", "unter/.geheim.gguf"]
)
def test_ein_name_ist_nie_ein_pfad(tmp_path, datei):
    """A traversal, a leading slash or dot, or a hidden segment is refused —
    on the remote name too, even though a plain sub-folder is now allowed."""
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", datei)
    assert fehler.value.grund == "name"


def test_ein_remote_unterordner_ist_erlaubt(tmp_path, strom):
    """A drafter lives at MTP/…gguf on the hub — the remote name may sit in a
    sub-folder. The local file keeps only the flat last segment; the folder
    never rides along."""
    strom(b"m" * 4096)
    download = Modelldownload(tmp_path)
    download.starten("repo", "MTP/mtp-modell.gguf")
    assert warten_bis(lambda: download.stand().fertig)
    assert (tmp_path / "mtp-modell.gguf").is_file()
    assert not (tmp_path / "MTP").exists()


def test_der_lokale_name_bleibt_flach(tmp_path):
    """`ziel` names a file in our folder — it must never be a path."""
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", "MTP/x.gguf", ziel="unter/x.gguf")
    assert fehler.value.grund == "name"


@pytest.mark.parametrize("datei", ["modell.safetensors", "modell.bin", "modell"])
def test_nur_gguf_wird_geholt(tmp_path, datei):
    """Default (chat/embedding): GGUF only, the one form the runner starts."""
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", datei)
    assert fehler.value.grund == "endung"


def test_bild_darf_safetensors_holen(tmp_path, strom):
    """An image model is safetensors — the image folder accepts it, and the
    endings the caller allows decide, not a hardcoded .gguf."""
    from app.modelldownload import BILD_ENDUNGEN
    strom(b"abc")
    download = Modelldownload(tmp_path)
    download.starten("repo/bild", "CyberRealisticXL.safetensors", endungen=BILD_ENDUNGEN)
    assert warten_bis(lambda: download.stand().fertig)
    assert (tmp_path / "CyberRealisticXL.safetensors").is_file()


def test_bild_lehnt_eine_zip_trotzdem_ab(tmp_path):
    """The set is the image forms, not everything — a .zip is still refused."""
    from app.modelldownload import BILD_ENDUNGEN
    with pytest.raises(DownloadFehler) as fehler:
        Modelldownload(tmp_path).starten("repo", "modell.zip", endungen=BILD_ENDUNGEN)
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


# --- The bond into the folder manifest ------------------------------------


def test_ein_begleiter_wird_im_manifest_vermerkt(tmp_path, strom):
    from app import modellzuordnung

    # A projector fetched next to a model writes the bond, so the runner
    # later reads it instead of guessing from name prefixes.
    strom(b"abc")
    download = Modelldownload(tmp_path)
    # The projector lands in the vision sub-folder; the bond is written to the
    # model folder (the root), where the runner reads it.
    download.starten(
        "wer/was",
        "mmproj-BF16.gguf",
        ziel="modell-mmproj-BF16.gguf",
        gehoert_zu="modell.gguf",
        rolle="mmproj",
        ordner=tmp_path / "vision",
        manifest_ordner=tmp_path,
    )
    assert warten_bis(lambda: download.stand().fertig)
    assert (tmp_path / "vision" / "modell-mmproj-BF16.gguf").is_file()
    assert (
        modellzuordnung.fuer(tmp_path, "modell.gguf")["mmproj"]
        == "modell-mmproj-BF16.gguf"
    )


def test_ein_schlichter_download_vermerkt_nichts(tmp_path, strom):
    from app import modellzuordnung

    # No parent and no role: nothing but the file itself is left behind.
    strom(b"abc")
    download = Modelldownload(tmp_path)
    download.starten("wer/was", "modell.gguf")
    assert warten_bis(lambda: download.stand().fertig)
    assert modellzuordnung.lade(tmp_path) == {}


def test_ein_anderer_zielordner_bekommt_die_datei(tmp_path, strom):
    """A download routed to another kind's folder lands THERE — an
    embedding model in the chat folder would be invisible to the embedding
    server and a broken entry in the chat list."""
    strom(b"abc")
    chat = tmp_path / "chat"
    einbettung = tmp_path / "einbettung"
    download = Modelldownload(chat)
    download.starten("wer/was", "embed.gguf", ordner=einbettung)
    assert warten_bis(lambda: download.stand().fertig)
    assert (einbettung / "embed.gguf").is_file()
    assert not (chat / "embed.gguf").exists()


def test_schon_da_gilt_im_zielordner(tmp_path, strom):
    strom(b"abc")
    einbettung = tmp_path / "einbettung"
    einbettung.mkdir()
    (einbettung / "embed.gguf").write_bytes(b"alt")
    download = Modelldownload(tmp_path / "chat")
    with pytest.raises(DownloadFehler) as fehler:
        download.starten("wer/was", "embed.gguf", ordner=einbettung)
    assert fehler.value.grund == "schon_da"


def test_der_begleiter_vermerk_folgt_dem_zielordner(tmp_path, strom):
    from app import modellzuordnung

    strom(b"abc")
    einbettung = tmp_path / "einbettung"
    download = Modelldownload(tmp_path / "chat")
    download.starten("wer/was", "mmproj.gguf", ziel="m-mmproj.gguf",
                     gehoert_zu="m.gguf", rolle="mmproj", ordner=einbettung)
    assert warten_bis(lambda: download.stand().fertig)
    assert modellzuordnung.lade(einbettung) != {}
    assert modellzuordnung.lade(tmp_path / "chat") == {}
