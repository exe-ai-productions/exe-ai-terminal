"""The model server, seen from the API.

The runner itself is tested next door (test_modellrunner.py); here stands
what the endpoints add on top — above all that a started server joins the
model list by itself and leaves it when stopped. That link is the last one
in the chain "fetch, start, chat", and it was the one that broke.
"""

from __future__ import annotations

from pathlib import Path

from app.api.v1 import runner as runner_api
from app.modellrunner import Lauf, RunnerFehler


class StummerRunner:
    """Stands in for the real runner: keeps the story, starts nothing."""

    def __init__(self, ordner: Path = Path("/tmp")):
        self.ordner = ordner
        self.programm = Path("/bin/echo")
        self._lauf = None

    def modelle(self):
        return []

    def mmproj(self):
        return []

    def mtp(self):
        return []

    def laeuft(self):
        return self._lauf is not None

    def lauf(self):
        return self._lauf

    def belegt_gb(self):
        return None

    def protokoll(self):
        return []

    def flash_attn_zustand(self):
        return None

    def mtp_zustand(self):
        return None

    def starten(self, modell, *, kontext=8192, schichten=99, port=8080, drafter=None,
                fein=None, vision=None):
        # The advanced settings are kept so a test can look at what arrived.
        self.fein = fein
        self.vision = vision
        self._lauf = Lauf(modell=modell, kontext=kontext, schichten=schichten, port=port)
        return self._lauf

    def stoppen(self):
        self._lauf = None
        return True


class KaputterRunner(StummerRunner):
    def starten(self, modell, **_):
        raise RunnerFehler("kein_modell")


def test_start_meldet_den_server_bei_der_discovery_an(client):
    client.app.state.modellrunner = StummerRunner()
    antwort = client.post(
        "/api/v1/runner/start", json={"modell": "m.gguf", "port": 8123}
    )
    assert antwort.status_code == 200

    zustand = client.app.state.discovery.zustaende.get("runner")
    assert zustand is not None
    assert zustand.endpunkt.base_url == "http://127.0.0.1:8123/v1"
    assert zustand.endpunkt.group == "local"
    assert zustand.endpunkt.parameter_dialect == "llama_cpp"


def test_stop_meldet_ihn_wieder_ab(client):
    client.app.state.modellrunner = StummerRunner()
    client.post("/api/v1/runner/start", json={"modell": "m.gguf", "port": 8123})
    client.post("/api/v1/runner/stop")
    assert "runner" not in client.app.state.discovery.zustaende


def test_ein_fehlstart_meldet_nichts_an(client):
    client.app.state.modellrunner = KaputterRunner()
    antwort = client.post("/api/v1/runner/start", json={"modell": "fehlt.gguf"})
    assert antwort.status_code == 404
    assert "runner" not in client.app.state.discovery.zustaende


def test_download_legt_zubehoer_in_den_unterordner(client):
    """A companion with `unterordner` lands in that sub-folder of its art — the
    endpoint joins the folder before handing the download off, so a VAE reaches
    data/bildmodelle/vae/ and shows up in the picture window at once."""
    from app.modelldownload import Fortschritt

    gefangen = {}

    class FangDownload:
        def starten(self, repo, datei, ziel=None, gehoert_zu=None, rolle=None,
                    ordner=None, endungen=(".gguf",), manifest_ordner=None):
            gefangen["ordner"] = ordner
            return Fortschritt(datei=datei, geladen=0, gesamt=0)

        def stand(self):
            return Fortschritt(datei="vae.safetensors", geladen=0, gesamt=1)

    client.app.state.modelldownload = FangDownload()
    client.app.state.modellordner_je_art = {
        "bild": "/data/bildmodelle", "chat": "/data/modelle",
    }
    antwort = client.post(
        "/api/v1/runner/download",
        json={"repo": "r", "datei": "vae.safetensors", "art": "bild", "unterordner": "vae"},
    )
    assert antwort.status_code == 200
    assert gefangen["ordner"] == "/data/bildmodelle/vae"


def test_download_ohne_unterordner_bleibt_in_der_wurzel(client):
    from app.modelldownload import Fortschritt

    gefangen = {}

    class FangDownload:
        def starten(self, repo, datei, ziel=None, gehoert_zu=None, rolle=None,
                    ordner=None, endungen=(".gguf",), manifest_ordner=None):
            gefangen["ordner"] = ordner
            return Fortschritt(datei=datei, geladen=0, gesamt=0)

        def stand(self):
            return Fortschritt(datei="m.gguf", geladen=0, gesamt=1)

    client.app.state.modelldownload = FangDownload()
    client.app.state.modellordner_je_art = {"chat": "/data/modelle"}
    antwort = client.post(
        "/api/v1/runner/download", json={"repo": "r", "datei": "m.gguf", "art": "chat"}
    )
    assert antwort.status_code == 200
    assert gefangen["ordner"] == "/data/modelle"


def test_der_modellordner_laesst_sich_zeigen(client, tmp_path, monkeypatch):
    client.app.state.modellrunner = StummerRunner(ordner=tmp_path / "modelle")
    gezeigt = []
    monkeypatch.setattr(runner_api, "ordner_oeffnen", gezeigt.append)

    antwort = client.post("/api/v1/runner/folder")
    assert antwort.status_code == 200
    assert gezeigt == [tmp_path / "modelle"]


def test_ohne_dateimanager_kommt_ein_satz(client, monkeypatch):
    client.app.state.modellrunner = StummerRunner()

    def geht_nicht(_):
        raise runner_api.OeffnenNichtMoeglich()

    monkeypatch.setattr(runner_api, "ordner_oeffnen", geht_nicht)
    assert client.post("/api/v1/runner/folder").status_code == 501
