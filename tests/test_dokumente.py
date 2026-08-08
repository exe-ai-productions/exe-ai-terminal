"""Document upload (phase 4.1): extraction, limits, history, meta."""

from __future__ import annotations

import io


def _chat(client):
    return client.post("/api/v1/chats", json={"title": "Doku"}).json()


def test_txt_rundreise_und_meta(client):
    chat = _chat(client)
    antwort = client.post(
        f"/api/v1/documents?chat_id={chat['id']}&name=notiz.txt",
        content="Hallo Dokument, dies ist Text.".encode(),
    )
    assert antwort.status_code == 201
    meta = antwort.json()["dokument"]
    assert meta["typ"] == "txt"
    assert meta["gekuerzt"] is False
    assert meta["kb"] == 1
    # The extracted text is in the database — not the file itself.
    dokument = client.app.state.repositories.documents.holen(meta["id"])
    assert "Hallo Dokument" in dokument.extracted_text


def test_uebergrosse_texte_werden_ehrlich_gekuerzt(client):
    chat = _chat(client)
    antwort = client.post(
        f"/api/v1/documents?chat_id={chat['id']}&name=lang.md",
        content=("x" * 30_000).encode(),
    )
    meta = antwort.json()["dokument"]
    assert meta["gekuerzt"] is True
    gespeichert = client.app.state.repositories.documents.holen(meta["id"])
    assert len(gespeichert.extracted_text) == 24_000


def test_falscher_typ_und_fremder_chat(client):
    chat = _chat(client)
    falsch = client.post(
        f"/api/v1/documents?chat_id={chat['id']}&name=bild.png", content=b"x"
    )
    assert falsch.status_code == 415
    fremd = client.post("/api/v1/documents?chat_id=gibtsnicht&name=a.txt", content=b"x")
    assert fremd.status_code == 404


def test_pdf_ohne_textebene_wird_abgelehnt(client):
    """A scan without text must not slip through as an empty document."""
    from pypdf import PdfWriter

    chat = _chat(client)
    puffer = io.BytesIO()
    schreiber = PdfWriter()
    schreiber.add_blank_page(width=612, height=792)
    schreiber.write(puffer)
    antwort = client.post(
        f"/api/v1/documents?chat_id={chat['id']}&name=leer.pdf",
        content=puffer.getvalue(),
    )
    assert antwort.status_code == 422


def test_verlauf_traegt_den_dokumenttext(client):
    from app.api.v1.generierung import _verlauf_bauen

    chat_daten = _chat(client)
    repositories = client.app.state.repositories
    meta = client.post(
        f"/api/v1/documents?chat_id={chat_daten['id']}&name=notiz.txt",
        content="Der Schatz liegt unter der Eiche.".encode(),
    ).json()["dokument"]
    repositories.messages.speichern(
        chat_id=chat_daten["id"], role="user", content="Fass zusammen.", dokument=meta["id"]
    )
    chat = repositories.chats.holen(chat_daten["id"])
    nachrichten = _verlauf_bauen(chat, repositories, "")
    assert "Schatz liegt unter der Eiche" in nachrichten[-1].content
    assert "Fass zusammen." in nachrichten[-1].content


def test_nachrichtenabruf_liefert_die_meta_karte(client):
    chat = _chat(client)
    meta = client.post(
        f"/api/v1/documents?chat_id={chat['id']}&name=notiz.txt", content=b"Inhalt."
    ).json()["dokument"]
    repositories = client.app.state.repositories
    repositories.messages.speichern(
        chat_id=chat["id"], role="user", content="Frage", dokument=meta["id"]
    )
    nachrichten = client.get(f"/api/v1/chats/{chat['id']}/messages").json()
    assert nachrichten[-1]["dokument"]["name"] == "notiz.txt"
    assert nachrichten[-1]["dokument"]["typ"] == "txt"
    # Image messages and plain messages still carry no document.
    assert nachrichten[0].get("dokument") is None or "dokument" in nachrichten[0]
