"""Model parameters: translation, validation, storage (3.2)."""

from __future__ import annotations

import pytest

from app.config import EndpointConfig
from app.parameter import DIALEKTE, NACH_NAME, PARAMETER, pruefen, uebersetzen, unterstuetzte
from app.providers.openai_kompatibel import OpenAIKompatiblerProvider
from app.providers.base import ChatNachricht, Generierungsanfrage


# --- Translation ----------------------------------------------------------


def test_gleiche_funktion_heisst_je_backend_anders():
    """The heart of the matter: llama.cpp and MLX name the same thing differently."""
    werte = {"repeat_penalty": 1.1, "repeat_last_n": 128}
    assert uebersetzen("llama_cpp", werte) == {"repeat_penalty": 1.1, "repeat_last_n": 128}
    assert uebersetzen("mlx", werte) == {"repetition_penalty": 1.1, "repetition_context_size": 128}


def test_unbekanntes_faellt_beim_uebersetzen_weg():
    """Only llama.cpp knows typical_p — it must not be sent to MLX."""
    assert "typical_p" in uebersetzen("llama_cpp", {"typical_p": 0.9})
    assert uebersetzen("mlx", {"typical_p": 0.9}) == {}


def test_erfundene_namen_werden_nicht_durchgereicht():
    assert uebersetzen("llama_cpp", {"gibt_es_nicht": 5}) == {}


def test_leere_werte_werden_ausgelassen():
    assert uebersetzen("llama_cpp", {"top_k": None, "min_p": 0.05}) == {"min_p": 0.05}


def test_ganzzahlen_bleiben_ganzzahlig():
    ergebnis = uebersetzen("llama_cpp", {"top_k": 40.0, "max_tokens": 2048.0})
    assert isinstance(ergebnis["top_k"], int)
    assert isinstance(ergebnis["max_tokens"], int)


def test_unbekannter_dialekt_faellt_auf_openai_zurueck():
    ergebnis = uebersetzen("gibtsnicht", {"temperature": 0.5, "top_k": 40})
    assert ergebnis == {"temperature": 0.5}   # the common denominator doesn't know top_k


def test_jeder_dialekt_kennt_die_drei_hauptwerte():
    for name, tabelle in DIALEKTE.items():
        assert {"temperature", "top_p", "max_tokens"} <= set(tabelle), name


def test_alle_dialekt_eintraege_sind_bekannte_parameter():
    for name, tabelle in DIALEKTE.items():
        unbekannt = set(tabelle) - set(NACH_NAME)
        assert not unbekannt, f"{name}: {unbekannt}"


# --- Validation -----------------------------------------------------------


def test_werte_werden_auf_ihren_bereich_begrenzt():
    assert pruefen({"temperature": 99})["temperature"] == 2
    assert pruefen({"temperature": -5})["temperature"] == 0
    assert pruefen({"top_p": 3})["top_p"] == 1


def test_unsinn_wird_verworfen():
    assert pruefen({"temperature": "heiß"}) == {}
    assert pruefen({"erfunden": 1}) == {}
    assert pruefen({"top_k": None}) == {}


def test_unterstuetzte_liste_haelt_die_reihenfolge():
    namen = [p.name for p in unterstuetzte("llama_cpp")]
    assert namen[:3] == ["temperature", "top_p", "max_tokens"]
    assert all(p.gruppe == "sichtbar" for p in unterstuetzte("llama_cpp")[:3])


def test_mlx_hat_kein_typical_p():
    assert "typical_p" not in [p.name for p in unterstuetzte("mlx")]
    assert "typical_p" in [p.name for p in unterstuetzte("llama_cpp")]


def test_jeder_parameter_hat_beide_sprachen():
    for p in PARAMETER:
        assert p.label and p.label_en and p.hinweis and p.hinweis_en
        assert p.minimum < p.maximum


# --- In the request body --------------------------------------------------


def _koerper(dialekt: str, **parameter):
    endpunkt = EndpointConfig.model_validate(
        {"id": "p", "name": "P", "base_url": "http://x/v1", "parameter_dialect": dialekt}
    )
    anfrage = Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="hi")], parameter=parameter
    )
    return OpenAIKompatiblerProvider(endpunkt)._koerper_bauen(anfrage)


def test_parameter_landen_uebersetzt_im_koerper():
    koerper = _koerper("mlx", repeat_penalty=1.15, top_k=30)
    assert koerper["repetition_penalty"] == 1.15
    assert koerper["top_k"] == 30
    assert "repeat_penalty" not in koerper


def test_unpassender_parameter_wird_nicht_mitgeschickt():
    """Otherwise the server rejects the entire request as an error."""
    assert "typical_p" not in _koerper("mlx", typical_p=0.9)


def test_hauptwerte_gehen_weiterhin_mit():
    endpunkt = EndpointConfig.model_validate(
        {"id": "p", "name": "P", "base_url": "http://x/v1", "parameter_dialect": "llama_cpp"}
    )
    anfrage = Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="hi")],
        temperature=0.4, top_p=0.8, max_tokens=1024, parameter={"top_k": 20},
    )
    koerper = OpenAIKompatiblerProvider(endpunkt)._koerper_bauen(anfrage)
    assert koerper["temperature"] == 0.4
    assert koerper["top_p"] == 0.8
    assert koerper["max_tokens"] == 1024
    assert koerper["top_k"] == 20


# --- Storage in the cascade -----------------------------------------------
# Parameters used to live on the chat, so every new conversation started at
# the endpoint's bare defaults. They are settings now and sit in the cascade:
# global, then per model, then per chat — the most specific value that is
# actually set wins.


def test_parameter_ueberleben_die_datenbank(repos):
    repos.einstellungen.setzen("modell:qwen", "parameter", {"top_k": 30, "min_p": 0.07})
    assert repos.einstellungen.holen("modell:qwen", "parameter") == {"top_k": 30, "min_p": 0.07}


def test_ein_modell_erbt_was_global_gilt(repos):
    """The point of a cascade: override one knob, keep the rest."""
    repos.einstellungen.setzen("global", "parameter", {"temperature": 0.7, "top_p": 0.9})
    repos.einstellungen.setzen("modell:qwen", "parameter", {"temperature": 0.3})
    aufgeloest = repos.einstellungen.zusammengefuehrt("parameter", modell="qwen")
    assert aufgeloest == {"temperature": 0.3, "top_p": 0.9}


def test_ein_chat_schlaegt_sein_modell(repos):
    repos.einstellungen.setzen("modell:qwen", "parameter", {"temperature": 0.3})
    repos.einstellungen.setzen("chat:abc", "parameter", {"temperature": 1.0})
    assert repos.einstellungen.zusammengefuehrt(
        "parameter", modell="qwen", chat="abc"
    ) == {"temperature": 1.0}


def test_herkunft_sagt_woher_jeder_wert_kommt(repos):
    """Without this the cascade is a black box — a number with no origin."""
    repos.einstellungen.setzen("global", "parameter", {"top_p": 0.9})
    repos.einstellungen.setzen("modell:qwen", "parameter", {"temperature": 0.3})
    woher = repos.einstellungen.herkunft("parameter", modell="qwen")
    assert woher == {"top_p": "global", "temperature": "modell:qwen"}


def test_nichts_gesetzt_heisst_nicht_leer_gesetzt(repos):
    """An unset scope steps aside instead of blanking the one above it."""
    repos.einstellungen.setzen("global", "parameter", {"temperature": 0.7})
    assert repos.einstellungen.zusammengefuehrt(
        "parameter", modell="unbekannt", chat="auch-nicht"
    ) == {"temperature": 0.7}


def test_geloeschter_chat_nimmt_seine_werte_mit(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Test")
    repos.einstellungen.setzen(f"chat:{chat.id}", "parameter", {"top_k": 30})
    repos.chats.loeschen(chat.id)
    assert repos.einstellungen.holen(f"chat:{chat.id}", "parameter") is None


# --- Via the API ----------------------------------------------------------


def test_parameter_ueber_die_api(client):
    antwort = client.put(
        "/api/v1/settings/modell:qwen/parameter", json={"wert": {"top_k": 25}}
    )
    assert antwort.status_code == 200
    assert antwort.json()["wert"] == {"top_k": 25}


def test_unsinn_kommt_auch_ueber_die_api_nicht_durch(client):
    client.put("/api/v1/settings/global/parameter", json={"wert": {"quatsch": 1}})
    assert client.get("/api/v1/settings/global/parameter").json()["wert"] is None


def test_unbekannter_bereich_wird_abgewiesen(client):
    antwort = client.put("/api/v1/settings/irgendwo/parameter", json={"wert": {"top_k": 5}})
    assert antwort.status_code == 400


def test_aufgeloeste_route_zeigt_wert_und_herkunft(client):
    client.put("/api/v1/settings/global/parameter", json={"wert": {"top_p": 0.9}})
    client.put("/api/v1/settings/modell:qwen/parameter", json={"wert": {"temperature": 0.3}})
    daten = client.get("/api/v1/settings/resolved/parameter?modell=qwen").json()
    assert daten["wert"] == {"top_p": 0.9, "temperature": 0.3}
    assert daten["herkunft"]["temperature"] == "modell:qwen"


def test_modelle_melden_ihre_eigenen_regler(client):
    daten = client.get("/api/v1/models").json()[0]
    assert daten["parameter"], "Jedes Modell muss Regler melden"
    sichtbar = [p["name"] for p in daten["parameter"] if p["gruppe"] == "sichtbar"]
    assert sichtbar == ["temperature", "top_p", "max_tokens"]


def test_eingestellte_parameter_gehen_an_das_modell(client, chat_id):
    """The whole reason for the rebuild: set the model once, it holds."""
    from app.providers import MockProvider, mock_endpunkt
    from tests.conftest import provider_setzen

    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.put("/api/v1/settings/modell:test/parameter", json={"wert": {"top_k": 33}})
    client.post("/api/v1/chat/completions",
                json={"chat_id": chat_id, "endpoint_id": "test", "content": "hi"})
    assert provider.letzte_anfrage.parameter["top_k"] == 33


def test_ein_neuer_chat_erbt_die_modelleinstellung(client):
    """No more setting the model again for every new conversation."""
    from app.providers import MockProvider, mock_endpunkt
    from tests.conftest import provider_setzen

    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.put("/api/v1/settings/modell:test/parameter", json={"wert": {"temperature": 0.25}})
    neuer = client.post("/api/v1/chats", json={"title": "Frisch"}).json()["id"]
    client.post("/api/v1/chat/completions",
                json={"chat_id": neuer, "endpoint_id": "test", "content": "hi"})
    assert provider.letzte_anfrage.temperature == 0.25
