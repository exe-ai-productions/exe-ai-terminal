"""The origin guard: writes from foreign web pages bounce, everything
else passes untouched."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.herkunftswaechter import Herkunftswaechter


def _app() -> TestClient:
    app = FastAPI()
    app.add_middleware(Herkunftswaechter)

    @app.post("/schreiben")
    def schreiben() -> dict:
        return {"ok": True}

    @app.get("/lesen")
    def lesen() -> dict:
        return {"ok": True}

    return TestClient(app, base_url="http://127.0.0.1:8090")


def test_fremde_herkunft_wird_abgewiesen():
    client = _app()
    antwort = client.post("/schreiben", headers={"origin": "https://boese.example"})
    assert antwort.status_code == 403


def test_eigene_herkunft_darf_schreiben():
    client = _app()
    antwort = client.post("/schreiben", headers={"origin": "http://127.0.0.1:8090"})
    assert antwort.status_code == 200


def test_ohne_herkunft_darf_schreiben():
    # curl, providers, native code: no browser, no Origin, no problem.
    client = _app()
    assert client.post("/schreiben").status_code == 200


def test_lesen_bleibt_offen():
    # Answers to reads are protected by the browser itself.
    client = _app()
    antwort = client.get("/lesen", headers={"origin": "https://boese.example"})
    assert antwort.status_code == 200


def test_gross_klein_im_wirt_ist_egal():
    client = _app()
    antwort = client.post("/schreiben", headers={"origin": "http://127.0.0.1:8090".upper()})
    assert antwort.status_code == 200
