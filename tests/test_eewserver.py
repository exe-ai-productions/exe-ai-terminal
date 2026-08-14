"""Extended Workflow: the guardian's own server, from outside."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import eewserver
from app.waechter import KONTEXT


def test_der_platz_ist_ein_eigener():
    """Its own pid file and its own port — sharing either was the whole
    reason the embedding server got a runner of its own."""
    from app import einbettungsserver

    assert eewserver.PID_DATEI != einbettungsserver.PID_DATEI
    assert eewserver.SCHLUESSEL_VARIABLE != einbettungsserver.SCHLUESSEL_VARIABLE
    assert eewserver.PORT_VORGABE == 8083


def test_das_fenster_steht_nur_einmal_in_der_zeile():
    """The runner writes `--ctx-size` itself. A second one from here made a
    command line that carried the flag twice — it worked by accident, because
    llama.cpp takes the last."""
    assert "--ctx-size" not in eewserver.FLAGS
    zeile = " ".join(
        _runner_attrappe().befehl("m.gguf", KONTEXT, 99, eewserver.PORT_VORGABE)
    )
    assert zeile.count("--ctx-size") == 1
    assert f"--ctx-size {KONTEXT}" in zeile


def _runner_attrappe():
    from pathlib import Path

    return eewserver.runner_bauen(Path("/tmp"), "llama-server")


def test_die_vorgabe_ist_das_gemessene_modell():
    assert eewserver.MODELL_VORGABE == "qwen2.5-coder-3b-instruct-q4_k_m.gguf"


def test_auskunft_nennt_ordner_und_vorgabe(client: TestClient):
    antwort = client.get("/api/v1/eew")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["laeuft"] is False
    assert daten["vorgabe"] == eewserver.MODELL_VORGABE
    assert daten["port"] == eewserver.PORT_VORGABE
    assert isinstance(daten["modelle"], list)


def test_start_ohne_modell_wird_abgewiesen(client: TestClient):
    """A name that is not in the folder never reaches a command line."""
    antwort = client.post("/api/v1/eew/start", json={"modell": "gibtsnicht.gguf"})
    assert antwort.status_code in (404, 412)


def test_stop_ist_immer_erlaubt(client: TestClient):
    """Stopping something that is not running is the state we wanted."""
    assert client.post("/api/v1/eew/stop").status_code == 200


def test_es_taucht_nicht_in_der_modellwahl_auf(client: TestClient):
    """This model writes repair suggestions. A picker offering it would let
    somebody send a conversation to a server started for something else."""
    kennungen = [m["id"] for m in client.get("/api/v1/models").json()]
    assert not any("eew" in k for k in kennungen)
