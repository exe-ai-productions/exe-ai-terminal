"""Searching the model catalogue.

Nothing here talks to Hugging Face: the answer is faked, because what is
being tested is our side — which kinds we allow, what we make of an entry,
and what happens when somebody else's server has a bad day.
"""

from __future__ import annotations

import httpx
import pytest

from app.api.v1 import modellsuche


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
    """Stands in for httpx and remembers what it was asked for."""

    letzte_parameter: dict | None = None
    alle_parameter: list[dict] = []

    def __init__(self, daten, fehler=None):
        self._antwort = FalscheAntwort(daten, fehler)

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, adresse, params=None):
        FalscherKlient.letzte_parameter = params
        FalscherKlient.alle_parameter.append(params)
        if isinstance(self._antwort._fehler, httpx.HTTPError):
            raise self._antwort._fehler
        return self._antwort


@pytest.fixture
def katalog(monkeypatch):
    def setzen(daten, fehler=None):
        FalscherKlient.letzte_parameter = None
        FalscherKlient.alle_parameter = []
        monkeypatch.setattr(modellsuche.httpx, "AsyncClient", FalscherKlient(daten, fehler))
    return setzen


EINTRAG = {
    "modelId": "lmstudio-community/Qwen3.6-27B-MLX-6bit",
    "downloads": 829410,
    "likes": 14,
    "pipeline_tag": "text-generation",
}


# --- What comes back ------------------------------------------------------


def test_ein_eintrag_wird_zu_einem_fund(client, katalog):
    katalog([EINTRAG])
    antwort = client.get("/api/v1/models/search?q=qwen3")
    assert antwort.status_code == 200

    fund = antwort.json()[0]
    assert fund["anbieter"] == "lmstudio-community"
    assert fund["name"] == "Qwen3.6-27B-MLX-6bit"
    assert fund["ladungen"] == 829410
    assert fund["beliebt"] == 14
    assert "art" not in fund


def test_ein_name_ohne_anbieter_bleibt_ganz(client, katalog):
    katalog([{"modelId": "einzelname", "downloads": 5}])
    fund = client.get("/api/v1/models/search?q=x").json()[0]
    assert fund["anbieter"] == ""
    assert fund["name"] == "einzelname"


def test_muell_im_katalog_wird_uebergangen(client, katalog):
    katalog([EINTRAG, "kein Eintrag", None])
    assert len(client.get("/api/v1/models/search?q=x").json()) == 1


# --- What we ask for ------------------------------------------------------


def test_gesucht_wird_nach_ladungen_sortiert(client, katalog):
    katalog([])
    client.get("/api/v1/models/search?q=qwen&art=chat&anzahl=5")
    parameter = FalscherKlient.letzte_parameter
    assert parameter["filter"] == "gguf"
    assert parameter["sort"] == "downloads"
    assert parameter["limit"] == 5


def test_chat_sucht_ohne_etikett_und_haelt_die_anderen_arten_draussen(client, katalog):
    """The chat tab queries WITHOUT a pipeline tag — most community quant
    repositories carry none, and a hard tag filter would hide them — and
    drops the kinds the other tabs own from the answer instead."""
    katalog([
        EINTRAG,
        {"modelId": "leise/ohne-etikett", "downloads": 7},
        {"modelId": "fremd/einbettung", "downloads": 9, "pipeline_tag": "feature-extraction"},
        {"modelId": "fremd/aehnlichkeit", "downloads": 9, "pipeline_tag": "sentence-similarity"},
        {"modelId": "fremd/bild", "downloads": 9, "pipeline_tag": "text-to-image"},
    ])
    antwort = client.get("/api/v1/models/search?q=x&art=chat").json()
    assert "pipeline_tag" not in FalscherKlient.letzte_parameter
    assert [f["id"] for f in antwort] == [EINTRAG["modelId"], "leise/ohne-etikett"]


def test_einbettung_fragt_beide_etiketten_und_meldet_jeden_fund_einmal(client, katalog):
    """Half the known embedding repositories say "sentence-similarity"
    instead of "feature-extraction" — one tag alone loses them. A repo
    carrying both tags may come back twice and must be answered once."""
    katalog([{"modelId": "nomic/embed", "downloads": 12, "pipeline_tag": "feature-extraction"}])
    antwort = client.get("/api/v1/models/search?q=x&art=einbettung").json()
    etiketten = {p.get("pipeline_tag") for p in FalscherKlient.alle_parameter}
    assert etiketten == {"feature-extraction", "sentence-similarity"}
    assert [f["id"] for f in antwort] == ["nomic/embed"]


def test_bild_fragt_nur_sein_eigenes_etikett(client, katalog):
    katalog([])
    client.get("/api/v1/models/search?q=x&art=bild")
    assert [p.get("pipeline_tag") for p in FalscherKlient.alle_parameter] == ["text-to-image"]


def test_bild_sucht_ohne_gguf_zwang(client, katalog):
    """The shipped drawer reads safetensors too, and the big image
    checkpoints live on HF almost only as safetensors — a gguf filter hid
    exactly what people came for. Chat and embedding keep the filter."""
    katalog([])
    client.get("/api/v1/models/search?q=cyber&art=bild")
    assert "filter" not in FalscherKlient.letzte_parameter
    katalog([])
    client.get("/api/v1/models/search?q=qwen&art=chat")
    assert FalscherKlient.letzte_parameter["filter"] == "gguf"
    katalog([])
    client.get("/api/v1/models/search?q=nomic&art=einbettung")
    assert FalscherKlient.letzte_parameter["filter"] == "gguf"


def test_der_alte_name_gguf_zaehlt_als_chat(client, katalog):
    # A page from before the tabs still asks with art=gguf. It meant what
    # the chat tab means now, and it must not be told "unknown kind".
    katalog([EINTRAG])
    antwort = client.get("/api/v1/models/search?q=x&art=gguf")
    assert antwort.status_code == 200
    assert "pipeline_tag" not in FalscherKlient.letzte_parameter


@pytest.mark.parametrize("art", ["safetensors", "pytorch", "onnx", "mlx", ""])
def test_andere_arten_werden_abgelehnt(client, katalog, art):
    # Only what the program can fetch as one file and start by itself —
    # everything else would be a promise we cannot keep. MLX is on this
    # list for the same reason it left the runner.
    katalog([])
    assert client.get(f"/api/v1/models/search?q=x&art={art}").status_code == 400


def test_ohne_suchbegriff_geht_nichts(client, katalog):
    katalog([])
    assert client.get("/api/v1/models/search?q=").status_code == 422


# --- When the other side has a bad day ------------------------------------


def test_katalog_antwortet_nicht(client, katalog):
    katalog(None, httpx.ConnectError("weg"))
    assert client.get("/api/v1/models/search?q=x").status_code == 502


def test_katalog_antwortet_unsinn(client, katalog):
    # An empty list means "nothing found"; something that is not a list at
    # all means the catalogue is broken, and that must not look the same.
    katalog({"unerwartet": True})
    assert client.get("/api/v1/models/search?q=x").status_code == 502


# --- The tab vocabulary lives in three places; this keeps them one ---------


def test_tab_namen_laufen_ueberall_gleich():
    """The kinds are named in the backend (ARTEN), in the frontend tab row
    (modellempfehlungen.js ARTEN) and as locale labels (katalog.art_*).
    Nothing ties them together at runtime — this test does."""
    import json
    import re
    from pathlib import Path

    wurzel = Path(__file__).resolve().parent.parent
    js = (wurzel / "frontend/src/lib/modellempfehlungen.js").read_text(encoding="utf-8")
    treffer = re.search(r"export const ARTEN = \[([^\]]*)\]", js)
    assert treffer, "frontend ARTEN nicht gefunden"
    vorn = re.findall(r"'([a-z]+)'", treffer.group(1))

    assert vorn == list(modellsuche.ARTEN), "Frontend-Tabs != Backend-Arten"

    for sprache in ("de", "en"):
        texte = json.loads((wurzel / f"app/locales/{sprache}.json").read_text(encoding="utf-8"))
        for art in modellsuche.ARTEN:
            assert texte["katalog"].get(f"art_{art}"), f"{sprache}: katalog.art_{art} fehlt"
