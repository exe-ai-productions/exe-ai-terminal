"""The file list of a found repository.

Nothing here talks to Hugging Face: the answer is faked, because what is
being tested is our side — which files we consider startable, in which
order they come back, and what happens when the other side has a bad day.
"""

from __future__ import annotations

import httpx
import pytest

from app.api.v1 import modelldateien


class FalscheAntwort:
    def __init__(self, daten, fehler=None):
        self._daten = daten
        self._fehler = fehler

    def raise_for_status(self):
        if self._fehler:
            raise self._fehler

    def json(self):
        return self._daten


class FalscherKlient:
    letzte_adresse: str | None = None

    def __init__(self, daten, fehler=None):
        self._antwort = FalscheAntwort(daten, fehler)

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, adresse, params=None):
        FalscherKlient.letzte_adresse = adresse
        if isinstance(self._antwort._fehler, httpx.HTTPError):
            raise self._antwort._fehler
        return self._antwort


@pytest.fixture
def baum(monkeypatch):
    def setzen(daten, fehler=None):
        monkeypatch.setattr(
            modelldateien.httpx, "AsyncClient", FalscherKlient(daten, fehler)
        )
    return setzen


def _eintrag(pfad, groesse):
    return {"path": pfad, "size": groesse}


# --- What counts as a file ------------------------------------------------


def test_nur_startbare_gguf_dateien_kommen_zurueck(client, baum):
    baum(
        [
            _eintrag("README.md", 4000),
            _eintrag("modell-F16.gguf", 20_000_000_000),
            _eintrag("modell-Q4_K_M.gguf", 5_000_000_000),
            # A shard alone is not a model — fetching one produces a file
            # that looks like a model and is not.
            _eintrag("gross-00001-of-00003.gguf", 9_000_000_000),
            # A vision companion is no model either — it rides along in its
            # own field instead.
            _eintrag("mmproj-BF16.gguf", 900_000_000),
            "kein Eintrag",
        ]
    )
    antwort = client.get("/api/v1/models/files?repo=wer/was")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert [d["datei"] for d in daten["dateien"]] == ["modell-Q4_K_M.gguf", "modell-F16.gguf"]
    assert daten["mmproj"]["datei"] == "mmproj-BF16.gguf"


def test_ohne_projektor_bleibt_das_feld_leer(client, baum):
    baum([_eintrag("modell.gguf", 5_000_000_000)])
    assert client.get("/api/v1/models/files?repo=wer/was").json()["mmproj"] is None


def test_der_kleinste_projektor_wird_genannt(client, baum):
    # They only differ in precision, and the small one sees the same.
    baum(
        [
            _eintrag("modell.gguf", 5_000_000_000),
            _eintrag("modell-mmproj-F32.gguf", 1_800_000_000),
            _eintrag("modell-mmproj-Q8_0.gguf", 600_000_000),
        ]
    )
    daten = client.get("/api/v1/models/files?repo=wer/was").json()
    assert daten["mmproj"]["datei"] == "modell-mmproj-Q8_0.gguf"


def test_kleinste_datei_steht_vorn(client, baum):
    # "Which one fits my machine" is answered from small to large.
    baum(
        [
            _eintrag("gross.gguf", 30_000_000_000),
            _eintrag("klein.gguf", 2_000_000_000),
        ]
    )
    dateien = client.get("/api/v1/models/files?repo=wer/was").json()["dateien"]
    assert dateien[0]["datei"] == "klein.gguf"
    assert dateien[0]["groesse_gb"] == 2.0


def test_der_repo_name_steht_in_der_adresse(client, baum):
    baum([])
    client.get("/api/v1/models/files?repo=wer/was")
    assert "/wer/was/tree/main" in FalscherKlient.letzte_adresse


# --- What does not go into an address -------------------------------------


@pytest.mark.parametrize(
    "repo", ["a..b", "wer", "wer/was/extra", "/wer/was", "wer /was", "wer/was?x=1"]
)
def test_kein_repo_name_kein_aufruf(client, baum, repo):
    baum([])
    antwort = client.get(
        "/api/v1/models/files", params={"repo": repo}
    )
    assert antwort.status_code == 400


# --- When the other side has a bad day ------------------------------------


def test_katalog_antwortet_nicht(client, baum):
    baum(None, httpx.ConnectError("weg"))
    assert client.get("/api/v1/models/files?repo=wer/was").status_code == 502


def test_katalog_antwortet_unsinn(client, baum):
    baum({"unerwartet": True})
    assert client.get("/api/v1/models/files?repo=wer/was").status_code == 502
