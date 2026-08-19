"""The storage-locations route: read, set, reset, and the guard rails."""

from __future__ import annotations


def test_uebersicht_listet_jeden_ort(client):
    antwort = client.get("/api/v1/speicherorte")
    assert antwort.status_code == 200
    namen = {z["name"] for z in antwort.json()}
    assert namen == {"bilder", "bildmodelle", "modelle", "einbettung"}
    for zeile in antwort.json():
        assert zeile["ist_standard"] is True
        assert zeile["pfad"] == zeile["standard"]


def test_setzen_wirkt_und_zuruecksetzen_kehrt_zurueck(client, tmp_path):
    ziel = tmp_path / "meine-bilder"
    gesetzt = client.put("/api/v1/speicherorte/bilder", json={"pfad": str(ziel)})
    assert gesetzt.status_code == 200
    assert gesetzt.json()["ist_standard"] is False
    assert gesetzt.json()["pfad"] == str(ziel.resolve())

    # A fresh read sees it too — it is really stored, not only echoed.
    jetzt = {z["name"]: z for z in client.get("/api/v1/speicherorte").json()}
    assert jetzt["bilder"]["pfad"] == str(ziel.resolve())

    zurueck = client.delete("/api/v1/speicherorte/bilder")
    assert zurueck.status_code == 200
    assert zurueck.json()["ist_standard"] is True


def test_unbekannter_ort_gibt_404(client, tmp_path):
    assert client.put(
        "/api/v1/speicherorte/gibtsnicht", json={"pfad": str(tmp_path)}
    ).status_code == 404
    assert client.delete("/api/v1/speicherorte/gibtsnicht").status_code == 404


def test_pfad_auf_eine_datei_wird_abgewiesen(client, tmp_path):
    datei = tmp_path / "eine-datei.txt"
    datei.write_text("kein ordner", encoding="utf-8")
    antwort = client.put("/api/v1/speicherorte/bilder", json={"pfad": str(datei)})
    assert antwort.status_code == 400


def test_leerer_pfad_wird_abgewiesen(client):
    assert client.put(
        "/api/v1/speicherorte/bilder", json={"pfad": "   "}
    ).status_code == 400
