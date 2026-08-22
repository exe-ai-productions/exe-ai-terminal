"""Chat API (phase 1.3)."""

from __future__ import annotations


def test_chat_anlegen_mit_titel(client):
    antwort = client.post("/api/v1/chats", json={"title": "Netzwerk"})
    assert antwort.status_code == 201
    daten = antwort.json()
    assert daten["title"] == "Netzwerk"
    # The service's own default user, not a fixture value — see
    # STANDARD_BENUTZER in app/api/abhaengigkeiten.py.
    assert daten["user_id"] == "standard"


def test_chat_ohne_titel_bekommt_uebersetzten_standardtitel(client):
    deutsch = client.post("/api/v1/chats", json={}, headers={"Accept-Language": "de"})
    englisch = client.post("/api/v1/chats", json={}, headers={"Accept-Language": "en"})
    assert deutsch.json()["title"] == "Unbenannter Chat"
    assert englisch.json()["title"] == "Untitled chat"


def test_chats_auflisten_und_suchen(client):
    client.post("/api/v1/chats", json={"title": "Netzwerk-Probleme"})
    client.post("/api/v1/chats", json={"title": "Kochrezepte"})

    alle = client.get("/api/v1/chats").json()
    assert len(alle) == 2

    treffer = client.get("/api/v1/chats", params={"suche": "Netzwerk"}).json()
    assert len(treffer) == 1
    assert treffer[0]["title"] == "Netzwerk-Probleme"


def test_chat_holen(client, chat_id):
    antwort = client.get(f"/api/v1/chats/{chat_id}")
    assert antwort.status_code == 200
    assert antwort.json()["id"] == chat_id


def test_unbekannter_chat_gibt_404_in_der_richtigen_sprache(client):
    deutsch = client.get("/api/v1/chats/gibtsnicht", headers={"Accept-Language": "de"})
    englisch = client.get("/api/v1/chats/gibtsnicht", headers={"Accept-Language": "en"})
    assert deutsch.status_code == 404
    assert deutsch.json()["detail"] == "Chat nicht gefunden"
    assert englisch.json()["detail"] == "Chat not found"


def test_chat_felder_aendern(client, chat_id):
    """Model parameters are not among them any more — they are settings now."""
    antwort = client.patch(
        f"/api/v1/chats/{chat_id}",
        json={"prompt_aus": True, "title": "Neu"},
    )
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["title"] == "Neu"
    assert daten["prompt_aus"] is True
    assert daten["title"] == "Neu"


def test_teilweises_aendern_laesst_den_rest_stehen(client, chat_id):
    client.patch(f"/api/v1/chats/{chat_id}", json={"prompt_aus": True})
    client.patch(f"/api/v1/chats/{chat_id}", json={"title": "Nur der Titel"})
    daten = client.get(f"/api/v1/chats/{chat_id}").json()
    assert daten["title"] == "Nur der Titel"
    assert daten["prompt_aus"] is True


def test_parameter_gehoeren_nicht_mehr_an_den_chat(client, chat_id):
    """They are silently ignored here — the settings route is the way in."""
    antwort = client.patch(f"/api/v1/chats/{chat_id}", json={"temperature": 0.7})
    assert antwort.status_code == 200
    assert "temperature" not in antwort.json()
    for veraltet in ({"top_p": -1}, {"max_tokens": 0}, {"parameter": {"top_k": 5}}):
        assert client.patch(f"/api/v1/chats/{chat_id}", json=veraltet).status_code == 200

    # And the settings route does check what it is given: values outside
    # their range are clamped, invented names dropped entirely.
    assert client.put(
        "/api/v1/settings/global/parameter", json={"wert": {"top_p": -1}}
    ).json()["wert"] == {"top_p": 0}
    assert client.put(
        "/api/v1/settings/global/parameter", json={"wert": {"erfunden": 1}}
    ).json()["wert"] is None


def test_chat_loeschen(client, chat_id):
    assert client.delete(f"/api/v1/chats/{chat_id}").status_code == 204
    assert client.get(f"/api/v1/chats/{chat_id}").status_code == 404


def test_loeschen_eines_unbekannten_chats_gibt_404(client):
    assert client.delete("/api/v1/chats/gibtsnicht").status_code == 404


# --- Messages --------------------------------------------------------------


def test_nachricht_speichern_und_lesen(client, chat_id):
    angelegt = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"role": "user", "content": "Hallo"},
    )
    assert angelegt.status_code == 201

    nachrichten = client.get(f"/api/v1/chats/{chat_id}/messages").json()
    assert len(nachrichten) == 1
    assert nachrichten[0]["content"] == "Hallo"
    assert nachrichten[0]["stats"] == {}


def test_nachricht_mit_gedankengang_und_messwerten(client, chat_id):
    client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={
            "role": "assistant",
            "content": "Antwort",
            "reasoning": "Kurz überlegt",
            "stats": {"tokens_pro_sekunde": 12.4},
        },
    )
    nachricht = client.get(f"/api/v1/chats/{chat_id}/messages").json()[0]
    assert nachricht["reasoning"] == "Kurz überlegt"
    assert nachricht["stats"]["tokens_pro_sekunde"] == 12.4


def test_ungueltige_rolle_wird_abgewiesen(client, chat_id):
    antwort = client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"role": "hausmeister", "content": "x"}
    )
    assert antwort.status_code == 422


def test_nachricht_hebt_den_chat_in_der_sortierung(client):
    erster = client.post("/api/v1/chats", json={"title": "Erster"}).json()["id"]
    client.post("/api/v1/chats", json={"title": "Zweiter"})

    client.post(f"/api/v1/chats/{erster}/messages", json={"content": "Hallo"})

    liste = client.get("/api/v1/chats").json()
    assert liste[0]["id"] == erster


def test_nachricht_loeschen(client, chat_id):
    message_id = client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"content": "Weg damit"}
    ).json()["id"]

    assert client.delete(f"/api/v1/chats/{chat_id}/messages/{message_id}").status_code == 204
    assert client.get(f"/api/v1/chats/{chat_id}/messages").json() == []


def test_nachricht_eines_fremden_chats_wird_nicht_geloescht(client, chat_id):
    anderer = client.post("/api/v1/chats", json={"title": "Anderer"}).json()["id"]
    message_id = client.post(
        f"/api/v1/chats/{anderer}/messages", json={"content": "Meine"}
    ).json()["id"]

    antwort = client.delete(f"/api/v1/chats/{chat_id}/messages/{message_id}")
    assert antwort.status_code == 404
    assert len(client.get(f"/api/v1/chats/{anderer}/messages").json()) == 1


def test_chat_loeschen_raeumt_nachrichten_mit_ab(client, chat_id):
    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Hallo"})
    client.delete(f"/api/v1/chats/{chat_id}")
    assert client.get(f"/api/v1/chats/{chat_id}/messages").status_code == 404


# --- System prompt: one file, read fresh on every request (3.10) -----------


def test_system_prompt_ist_zu_beginn_leer(client):
    """Nothing ships by default — no preinstalled personality."""
    daten = client.get("/api/v1/system-prompt").json()
    assert daten["text"] == ""
    assert daten["datei"].endswith(".md")


def test_system_prompt_sichern_und_wieder_lesen(client):
    client.put("/api/v1/system-prompt", json={"text": "  Antworte knapp.  "})
    assert client.get("/api/v1/system-prompt").json()["text"] == "Antworte knapp."


def test_geaenderter_prompt_gilt_auch_in_alten_chats(client, chat_id):
    """The core of the rebuild: no more copy at creation time.

    The chat is created first, the prompt is written afterwards — yet it
    must apply in this chat. Previously the chat held a copy from the
    time of creation that never saw later changes.
    """
    from app.api.v1.generierung import _verlauf_bauen

    client.put("/api/v1/system-prompt", json={"text": "Sei Mana."})
    chat = client.app.state.repositories.chats.holen(chat_id)
    verlauf = _verlauf_bauen(
        chat, client.app.state.repositories, client.app.state.config.system_prompt_lesen()
    )
    assert verlauf[0].role == "system"
    assert verlauf[0].content == "Sei Mana."


def test_aussetzen_gilt_nur_fuer_diesen_chat(client, chat_id):
    """The switch suspends the USER's layer, not the shipped instructions.

    Those describe how this machine works and include the rule that a tool
    result is data and not an order. Switching them off to see a model answer
    "raw" would drop the guard rails with it, and nothing on the switch says
    so — so it does not.
    """
    from app.providers import MockProvider, mock_endpunkt
    from tests.conftest import provider_setzen

    client.put("/api/v1/system-prompt", json={"text": "Sei Mana."})
    client.patch(f"/api/v1/chats/{chat_id}", json={"prompt_aus": True})

    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    system = [n for n in provider.letzte_anfrage.nachrichten if n.role == "system"]
    assert len(system) == 1
    assert "Sei Mana." not in system[0].content
    assert "inside Exe AI" in system[0].content

    # A new chat carries the user's layer again.
    neuer_id = client.post("/api/v1/chats", json={"title": "Neu"}).json()["id"]
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": neuer_id, "endpoint_id": "test", "content": "hallo"},
    )
    system = [n for n in provider.letzte_anfrage.nachrichten if n.role == "system"]
    assert system[0].content.endswith("Sei Mana.")


def test_leerer_prompt_wird_nicht_vorangestellt(client, chat_id):
    from app.api.v1.generierung import _verlauf_bauen

    chat = client.app.state.repositories.chats.holen(chat_id)
    verlauf = _verlauf_bauen(chat, client.app.state.repositories, "")
    assert all(n.role != "system" for n in verlauf)


def test_ask_user_frage_und_antwort_bleiben_im_verlauf(client, chat_id):
    """The model's question and the user's answer survive the run.

    Both lived only in the tool log; a later request rebuilt the history
    without them, so the model no longer knew what it had asked — and
    answered as if the exchange never happened.
    """
    from app.api.v1.generierung import _verlauf_bauen

    repositories = client.app.state.repositories
    repositories.messages.speichern(chat_id=chat_id, role="user", content="pick one")
    repositories.messages.speichern(
        chat_id=chat_id,
        role="assistant",
        content="Done.",
        stats={
            "werkzeuge": [
                {
                    "name": "ask_user",
                    "argumente": {"question": "Blue or green?"},
                    "ergebnis": "green",
                    "fehlgeschlagen": False,
                }
            ]
        },
    )
    chat = repositories.chats.holen(chat_id)
    letzte = _verlauf_bauen(chat, repositories, "")[-1]
    assert "Blue or green?" in letzte.content
    assert "green" in letzte.content
    assert "Done." in letzte.content


def test_erzeugtes_bild_reist_als_satz_nicht_als_bildteil(client, chat_id):
    """A generated picture is stored as an assistant message with no text.

    Sent onward as an image part it ends every following request on
    OpenAI-style servers — image parts are only valid in user messages —
    and the chat cannot be answered in any more. The model gets a sentence
    instead, and never an empty turn.
    """
    from app.api.v1.generierung import _verlauf_bauen

    repositories = client.app.state.repositories
    repositories.messages.speichern(chat_id=chat_id, role="user", content="a dog")
    repositories.messages.speichern(chat_id=chat_id, role="assistant", content="", bild="a.png")
    chat = repositories.chats.holen(chat_id)
    letzte = _verlauf_bauen(chat, repositories, "")[-1]
    assert letzte.role == "assistant"
    assert letzte.bild_url is None
    assert letzte.content


def test_bild_im_verlauf_faellt_ohne_vision_weg(client, chat_id):
    """An earlier attachment must not reach a model that cannot see.

    The guard on new uploads already refuses them; the history walked past
    it. Dropped with a note, so the model can say so instead of inventing
    the picture's contents.
    """
    from app.api.v1.generierung import _verlauf_bauen

    repositories = client.app.state.repositories
    repositories.messages.speichern(
        chat_id=chat_id, role="user", content="what is this?", bild="a.png"
    )
    chat = repositories.chats.holen(chat_id)
    letzte = _verlauf_bauen(chat, repositories, "", vision=False)[-1]
    assert letzte.bild_url is None
    assert "cannot see" in letzte.content
