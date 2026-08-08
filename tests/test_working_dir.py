"""The working folders per chat.

A chat may have up to four folders shared with it. Only the substructure here: column, checks, round trip through
the API. The UI (button, folder mark, pill row) is its own step.
"""

from __future__ import annotations

from pathlib import Path


def test_neuer_chat_hat_keine(client, chat_id):
    chat = client.get(f"/api/v1/chats/{chat_id}").json()
    assert chat["working_dirs"] == []


def test_setzen_und_rundreise(client, chat_id, tmp_path):
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(tmp_path)]}
    )
    assert antwort.status_code == 200
    assert antwort.json()["working_dirs"] == [str(tmp_path.resolve())]

    chat = client.get(f"/api/v1/chats/{chat_id}").json()
    assert chat["working_dirs"] == [str(tmp_path.resolve())]


def test_mehrere_ordner(client, chat_id, tmp_path):
    ordner = []
    for name in ("eins", "zwei", "drei"):
        pfad = tmp_path / name
        pfad.mkdir()
        ordner.append(str(pfad))

    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": ordner})
    assert antwort.status_code == 200
    assert antwort.json()["working_dirs"] == [str(Path(o).resolve()) for o in ordner]


def test_reihenfolge_bleibt(client, chat_id, tmp_path):
    """The first folder is the working directory — its position matters."""
    ordner = []
    for name in ("zuerst", "danach"):
        pfad = tmp_path / name
        pfad.mkdir()
        ordner.append(str(pfad.resolve()))

    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": ordner})
    assert antwort.json()["working_dirs"] == ordner

    gedreht = list(reversed(ordner))
    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": gedreht})
    assert antwort.json()["working_dirs"] == gedreht


def test_mehr_als_vier_wird_abgewiesen(client, chat_id, tmp_path):
    ordner = []
    for nummer in range(5):
        pfad = tmp_path / f"ordner{nummer}"
        pfad.mkdir()
        ordner.append(str(pfad))

    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": ordner})
    assert antwort.status_code == 400
    assert "4" in antwort.json()["detail"]


def test_genau_vier_gehen(client, chat_id, tmp_path):
    ordner = []
    for nummer in range(4):
        pfad = tmp_path / f"ordner{nummer}"
        pfad.mkdir()
        ordner.append(str(pfad))

    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": ordner})
    assert antwort.status_code == 200
    assert len(antwort.json()["working_dirs"]) == 4


def test_doppelte_werden_zusammengefasst(client, chat_id, tmp_path):
    """The same folder twice is not a second share."""
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}",
        json={"working_dirs": [str(tmp_path), str(tmp_path)]},
    )
    assert antwort.status_code == 200
    assert antwort.json()["working_dirs"] == [str(tmp_path.resolve())]


def test_tilde_wird_aufgeloest(client, chat_id):
    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": ["~"]})
    assert antwort.status_code == 200
    assert antwort.json()["working_dirs"] == [str(Path.home().resolve())]


def test_relativer_pfad_wird_abgewiesen(client, chat_id):
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}", json={"working_dirs": ["irgendwo/relativ"]}
    )
    assert antwort.status_code == 400
    assert "absoluter Pfad" in antwort.json()["detail"]


def test_fehlender_ordner_wird_abgewiesen(client, chat_id, tmp_path):
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}",
        json={"working_dirs": [str(tmp_path / "gibt-es-nicht")]},
    )
    assert antwort.status_code == 400
    assert "gibt es nicht" in antwort.json()["detail"]


def test_ein_schlechter_kippt_alle(client, chat_id, tmp_path):
    """All or nothing: a bad path must not let the good ones through."""
    gut = tmp_path / "gut"
    gut.mkdir()
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}",
        json={"working_dirs": [str(gut), str(tmp_path / "gibt-es-nicht")]},
    )
    assert antwort.status_code == 400

    chat = client.get(f"/api/v1/chats/{chat_id}").json()
    assert chat["working_dirs"] == []


def test_datei_statt_ordner_wird_abgewiesen(client, chat_id, tmp_path):
    datei = tmp_path / "datei.txt"
    datei.write_text("x", encoding="utf-8")
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(datei)]}
    )
    assert antwort.status_code == 400
    assert "kein Ordner" in antwort.json()["detail"]


def test_leere_liste_waehlt_ab(client, chat_id, tmp_path):
    client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(tmp_path)]})
    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": []})
    assert antwort.status_code == 200
    assert antwort.json()["working_dirs"] == []


def test_andere_felder_bleiben_unberuehrt(client, chat_id, tmp_path):
    client.patch(f"/api/v1/chats/{chat_id}", json={"title": "Mein Titel"})
    client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(tmp_path)]})
    chat = client.get(f"/api/v1/chats/{chat_id}").json()
    assert chat["title"] == "Mein Titel"
    assert chat["working_dirs"] == [str(tmp_path.resolve())]
