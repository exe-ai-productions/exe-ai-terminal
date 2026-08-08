"""Streaming proxy end to end (phase 1.5).

These are the integration tests for the whole chain: request → proxy →
provider → response → database. The mock stands in for a real model server.
"""

from __future__ import annotations

import json

import pytest

from app.providers import MockProvider, mock_endpunkt
from tests.conftest import provider_setzen


def _ereignisse(text: str) -> list[dict]:
    return [
        json.loads(zeile[5:].strip())
        for zeile in text.splitlines()
        if zeile.startswith("data:")
    ]


def _text_aus(ereignisse: list[dict], typ: str) -> str:
    return "".join(e.get("text", "") for e in ereignisse if e["typ"] == typ)


def test_antwort_wird_gestreamt_und_gespeichert(client, chat_id):
    provider_setzen(client, MockProvider(haeppchen=["Guten ", "Tag"]))

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Hallo"},
    )
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("text/event-stream")

    ereignisse = _ereignisse(antwort.text)
    assert ereignisse[0]["typ"] == "start"
    assert ereignisse[0]["generation_id"]
    assert _text_aus(ereignisse, "content") == "Guten Tag"
    assert ereignisse[-1]["typ"] == "done"
    assert ereignisse[-1]["abgebrochen"] is False

    gespeichert = client.get(f"/api/v1/chats/{chat_id}/messages").json()
    assert [n["role"] for n in gespeichert] == ["user", "assistant"]
    assert gespeichert[0]["content"] == "Hallo"
    assert gespeichert[1]["content"] == "Guten Tag"


def test_gedankengang_wird_getrennt_gespeichert(client, chat_id):
    """think tags: the reasoning must not end up in the answer bubble."""
    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test", reasoning_format="think"),
            haeppchen=["<think>Ich überlege</think>", "Die Antwort"],
        ),
    )

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Frage"},
    )
    ereignisse = _ereignisse(antwort.text)
    assert _text_aus(ereignisse, "reasoning") == "Ich überlege"
    assert _text_aus(ereignisse, "content") == "Die Antwort"

    nachricht = client.get(f"/api/v1/chats/{chat_id}/messages").json()[1]
    assert nachricht["content"] == "Die Antwort"
    assert nachricht["reasoning"] == "Ich überlege"


def test_verlauf_wird_mitgeschickt(client, chat_id):
    provider = provider_setzen(client, MockProvider(haeppchen=["ok"]))
    client.put("/api/v1/system-prompt", json={"text": "Sei knapp."})
    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Erste Frage"})

    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Zweite Frage"},
    )

    rollen = [n.role for n in provider.letzte_anfrage.nachrichten]
    inhalte = [n.content for n in provider.letzte_anfrage.nachrichten]
    # The user's prompt is a layer on the shipped one now, so it sits at the
    # end of the single system message instead of being the whole of it.
    assert rollen[0] == "system" and inhalte[0].endswith("Sei knapp.")
    assert "Erste Frage" in inhalte and "Zweite Frage" in inhalte


def test_eingestellte_parameter_werden_verwendet(client, chat_id):
    """What is set for the chat reaches the model — through the cascade now."""
    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.put(
        f"/api/v1/settings/chat:{chat_id}/parameter",
        json={"wert": {"temperature": 0.42, "top_k": 17}},
    )
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hi"},
    )
    assert provider.letzte_anfrage.temperature == 0.42
    assert provider.letzte_anfrage.parameter["top_k"] == 17

def test_parameter_der_anfrage_haben_vorrang(client, chat_id):
    provider = provider_setzen(client, MockProvider(haeppchen=["ok"]))
    client.patch(f"/api/v1/chats/{chat_id}", json={"temperature": 0.3})

    client.post(
        "/api/v1/chat/completions",
        json={
            "chat_id": chat_id,
            "endpoint_id": "test",
            "content": "Frage",
            "temperature": 1.1,
        },
    )
    assert provider.letzte_anfrage.temperature == 1.1


def test_modellwahl_bleibt_am_chat_haengen(client, chat_id):
    provider_setzen(client, MockProvider(haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Frage"},
    )
    assert client.get(f"/api/v1/chats/{chat_id}").json()["endpoint_id"] == "test"


def test_ohne_content_wird_auf_dem_verlauf_weitergearbeitet(client, chat_id):
    """Foundation for "regenerate"."""
    provider = provider_setzen(client, MockProvider(haeppchen=["nochmal"]))
    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Frage"})

    client.post(
        "/api/v1/chat/completions", json={"chat_id": chat_id, "endpoint_id": "test"}
    )
    # The shipped instructions always travel, even with no user prompt set —
    # what is left of them still says answer in the user's language, do not
    # write files unasked, do not invent results.
    rollen = [n.role for n in provider.letzte_anfrage.nachrichten]
    inhalte = [n.content for n in provider.letzte_anfrage.nachrichten]
    assert rollen == ["system", "user"]
    assert inhalte[1] == "Frage"


def test_messwerte_landen_in_der_datenbank(client, chat_id):
    provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["a", "b", "c"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Frage"},
    )
    stats = client.get(f"/api/v1/chats/{chat_id}/messages").json()[1]["stats"]
    assert stats["haeppchen"] == 3
    assert stats["endpunkt"] == "test"
    assert stats["abgebrochen"] is False


# --- Error cases ---------------------------------------------------------


def test_unbekannter_chat_gibt_404(client):
    provider_setzen(client, MockProvider())
    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": "gibtsnicht", "endpoint_id": "test", "content": "x"},
    )
    assert antwort.status_code == 404


def test_nicht_erreichbares_modell_gibt_503(client, chat_id):
    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "abwesend", "content": "x"},
        headers={"Accept-Language": "de"},
    )
    assert antwort.status_code == 503
    assert "nicht erreichbar" in antwort.json()["detail"]


def test_unbekannter_endpunkt_gibt_404(client, chat_id):
    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "phantasie", "content": "x"},
    )
    assert antwort.status_code == 404


def test_ohne_modellwahl_gibt_400(client, chat_id):
    antwort = client.post(
        "/api/v1/chat/completions", json={"chat_id": chat_id, "content": "x"}
    )
    assert antwort.status_code == 400


def test_fehler_des_anbieters_landet_im_strom_und_nicht_als_absturz(client, chat_id):
    provider_setzen(client, MockProvider(fehler="Modell ist explodiert"))

    antwort = client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "Frage"},
    )
    assert antwort.status_code == 200
    ereignisse = _ereignisse(antwort.text)
    assert any(e["typ"] == "error" for e in ereignisse)
    assert "explodiert" in _text_aus(ereignisse, "error")

    # The bubble is not left behind as a corpse — it is saved and flagged.
    nachricht = client.get(f"/api/v1/chats/{chat_id}/messages").json()[1]
    assert nachricht["stats"]["fehler"] == "Modell ist explodiert"


# --- Cancellation --------------------------------------------------------


def test_stop_ohne_angaben_gibt_400(client):
    assert client.post("/api/v1/chat/stop", json={}).status_code == 400


def test_stop_einer_unbekannten_generierung_meldet_null(client):
    antwort = client.post("/api/v1/chat/stop", json={"generation_id": "gibtsnicht"})
    assert antwort.json() == {"abgebrochen": 0}


@pytest.mark.asyncio
async def test_abbruch_stoppt_den_strom_und_rettet_den_text(laufender_server):
    """The actual stop button: set the signal, the stream ends, the text is kept.

    Deliberately runs against a real uvicorn process. The ASGI test transport
    collects the entire response before handing it out — a cancellation in the
    middle of the stream could not be tested that way at all.
    """
    import httpx

    app, basis_adresse = laufender_server
    provider = MockProvider(
        mock_endpunkt("test"), haeppchen=[f"Teil{i} " for i in range(50)], verzoegerung=0.05
    )
    zustand = app.state.discovery.zustaende["test"]
    zustand.provider = provider
    zustand.erreichbar = True

    async with httpx.AsyncClient(base_url=basis_adresse, timeout=30) as client:
        chat_id = (await client.post("/api/v1/chats", json={"title": "Abbruch"})).json()["id"]

        gelesen: list[dict] = []
        generation_id = None
        async with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={"chat_id": chat_id, "endpoint_id": "test", "content": "Los"},
        ) as antwort:
            async for zeile in antwort.aiter_lines():
                if not zeile.startswith("data:"):
                    continue
                ereignis = json.loads(zeile[5:].strip())
                gelesen.append(ereignis)
                if ereignis["typ"] == "start":
                    generation_id = ereignis["generation_id"]
                elif ereignis["typ"] == "content" and len(gelesen) == 4:
                    await client.post(
                        "/api/v1/chat/stop", json={"generation_id": generation_id}
                    )

        assert gelesen[-1]["typ"] == "done"
        assert gelesen[-1]["abgebrochen"] is True
        # Cancelled well before the 50 chunks.
        assert provider.ausgegebene_haeppchen < 50
        # The provider noticed that the stream was closed.
        assert provider.abgebrochen is True

        nachrichten = (await client.get(f"/api/v1/chats/{chat_id}/messages")).json()
        assert nachrichten[1]["content"].startswith("Teil0")
        assert nachrichten[1]["content"] != ""
        assert nachrichten[1]["stats"]["abgebrochen"] is True


@pytest.mark.asyncio
async def test_abbruch_ueber_chat_id_trifft_alle_laufenden(config):
    from app.generationen import Generierungsverwaltung

    verwaltung = Generierungsverwaltung()
    a = verwaltung.anmelden(chat_id="chat1", endpoint_id="test")
    b = verwaltung.anmelden(chat_id="chat1", endpoint_id="test")
    c = verwaltung.anmelden(chat_id="chat2", endpoint_id="test")

    assert verwaltung.alle_im_chat_abbrechen("chat1") == 2
    assert a.soll_abbrechen and b.soll_abbrechen
    assert not c.soll_abbrechen


@pytest.mark.asyncio
async def test_abgemeldete_generierung_laesst_sich_nicht_mehr_abbrechen():
    from app.generationen import Generierungsverwaltung

    verwaltung = Generierungsverwaltung()
    generierung = verwaltung.anmelden(chat_id="c", endpoint_id="e")
    verwaltung.abmelden(generierung.id)
    assert verwaltung.abbrechen(generierung.id) is False


# --- Metrics across tool rounds ------------------------------------------


def test_messwerte_summieren_token_und_erzeugungszeit_getrennt():
    """Two rounds with a tool run in between.

    The wait between the rounds — the tool plus processing the grown
    prompt — belongs in the total duration, but not in the speed.
    """
    from app.api.v1.generierung import _messwerte_mergen

    erste = {
        "dauer_sekunden": 4.0, "erzeugte_tokens": 30, "erzeugungs_sekunden": 1.0,
        "haeppchen": 30, "tempo_quelle": "server", "erstes_token_nach_sekunden": 3.0,
    }
    zweite = {
        "dauer_sekunden": 12.0, "erzeugte_tokens": 90, "erzeugungs_sekunden": 3.0,
        "haeppchen": 90, "tempo_quelle": "server", "erstes_token_nach_sekunden": 9.0,
    }
    zusammen = _messwerte_mergen(erste, zweite)

    assert zusammen["dauer_sekunden"] == 16.0        # honest: that's how long it took
    assert zusammen["erzeugungs_sekunden"] == 4.0
    assert zusammen["tokens_pro_sekunde"] == 30.0    # 120 tokens / 4 s
    assert zusammen["erstes_token_nach_sekunden"] == 3.0  # from the first round


def test_eine_ungenaue_runde_macht_die_ganze_zahl_ungenau():
    from app.api.v1.generierung import _messwerte_mergen

    zusammen = _messwerte_mergen(
        {"erzeugte_tokens": 10, "erzeugungs_sekunden": 1.0, "tempo_quelle": "server"},
        {"erzeugte_tokens": 10, "erzeugungs_sekunden": 1.0, "tempo_quelle": "geschaetzt"},
    )
    assert zusammen["tempo_quelle"] == "geschaetzt"


def test_erste_runde_wird_unveraendert_uebernommen():
    from app.api.v1.generierung import _messwerte_mergen

    neu = {"dauer_sekunden": 2.0, "tokens_pro_sekunde": 12.5}
    assert _messwerte_mergen({}, neu) == neu
