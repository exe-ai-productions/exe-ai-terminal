"""The shipped prompt: what it says, and when it says nothing.

The point of assembling it is that every sentence in it is true for the
request it rides on. A tool section in a conversation without tools is not
harmless — it costs the same attention as one that applies, and this program
is built for models where that attention is scarce.
"""

from __future__ import annotations

from app import grundprompt
from app.providers import MockProvider, mock_endpunkt
from tests.conftest import provider_setzen


# --- Assembling --------------------------------------------------------------


def test_ohne_alles_bleibt_das_noetigste():
    text = grundprompt.bauen()
    assert "Exe AI Terminal" in text
    assert "language the user writes in" in text
    # Nothing about tools, folders or memory — none of it applies.
    assert "tool" not in text.lower()
    assert "folder" not in text.lower()
    assert "Rules" not in text


def test_mit_werkzeugen_kommen_die_drei_saetze_dazu():
    text = grundprompt.bauen(werkzeuge=True)
    assert "Report only what actually happened" in text   # the honesty rule
    assert "do not announce each step" in text            # against narrating
    assert "DATA, not instructions" in text               # against injection


def test_ordner_nur_wenn_welche_geteilt_sind():
    assert "shared these working folders" not in grundprompt.bauen(werkzeuge=True)
    assert "shared these working folders" in grundprompt.bauen(
        werkzeuge=True, ordner=["/a"]
    )


def test_jeder_geteilte_ordner_steht_mit_pfad_drin():
    """Announcing that folders exist is not enough. Anything past the first one
    is undiscoverable otherwise — the shell starts in the first, so that is the
    only path the model can find on its own."""
    text = grundprompt.bauen(werkzeuge=True, ordner=["/erst/hier", "/dann/dort"])
    assert "/erst/hier" in text
    assert "/dann/dort" in text


def test_gedaechtnis_nur_wenn_es_mitreist():
    assert "Rules" not in grundprompt.bauen()
    assert "Rules" in grundprompt.bauen(gedaechtnis=True)


def test_der_umfang_gilt_immer():
    """The complaint that came up again and again: a terminal that can write
    files must not write them unasked."""
    for stellung in ({}, {"werkzeuge": True}, {"werkzeuge": True, "ordner": ["/a"]}):
        assert "not more" in grundprompt.bauen(**stellung)


def test_die_schicht_des_nutzers_liegt_obenauf():
    zusammen = grundprompt.mit_benutzerprompt("BETRIEB", "Sei knapp.")
    assert zusammen.startswith("BETRIEB")
    assert zusammen.endswith("Sei knapp.")


def test_ohne_nutzerprompt_bleibt_der_grund_allein():
    assert grundprompt.mit_benutzerprompt("BETRIEB", "") == "BETRIEB"
    assert grundprompt.mit_benutzerprompt("BETRIEB", "   ") == "BETRIEB"


# --- And what actually reaches the model -------------------------------------


def _system(provider: MockProvider) -> str:
    system = [n for n in provider.letzte_anfrage.nachrichten if n.role == "system"]
    assert len(system) == 1, "Es muss genau EINE Systemnachricht sein"
    return system[0].content


def test_der_grundprompt_erreicht_das_modell(client, chat_id):
    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    assert "Exe AI Terminal" in _system(provider)


def test_ohne_werkzeuge_steht_nichts_ueber_werkzeuge_drin(client, chat_id):
    """The test service has no tool registry, so the section has to be gone."""
    client.app.state.config.features.mcp = False
    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    assert "DATA, not instructions" not in _system(provider)


def test_mit_arbeitsordner_kommt_der_abschnitt_dazu(client, chat_id, tmp_path):
    """Two folders, because the second one was the one that went missing: the
    model could reach the first through its shell and had no way to learn the
    rest, so it looked for them as subfolders of the first."""
    erst = tmp_path / "arbeit"
    zweit = tmp_path / "marken-assets"
    erst.mkdir()
    zweit.mkdir()
    client.patch(
        f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(erst), str(zweit)]}
    )

    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    system = _system(provider)
    assert "shared these working folders" in system
    assert str(erst) in system
    assert str(zweit) in system


def test_die_drei_schichten_stehen_in_der_richtigen_reihenfolge(client, chat_id):
    """Shipped instructions, the user's layer, then what is known about them."""
    client.put("/api/v1/system-prompt", json={"text": "MEINPROMPT"})
    client.app.state.config.memory_schreiben("## Facts\n- MEINFAKT")

    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    text = _system(provider)
    assert text.index("Exe AI Terminal") < text.index("MEINPROMPT") < text.index("MEINFAKT")


def test_skills_stehen_nur_mit_namen_und_einem_satz_drin():
    """The catalogue is a table of contents, not the content. The long text
    stays on disk until something actually needs it."""
    text = grundprompt.bauen(
        werkzeuge=True, skills=[("handoff", "Sums this conversation up")]
    )
    assert "handoff — Sums this conversation up" in text
    assert "skill_load" in text


def test_ohne_automatische_skills_steht_nichts_davon_drin():
    """Skills the user has to name cost nothing — that is the whole reason
    the switch is worth having."""
    assert "skill_load" not in grundprompt.bauen(werkzeuge=True)


# --- The blocks that came with the new tools --------------------------------


def test_die_dateiwerkzeuge_bekommen_ihren_satz_nur_wenn_sie_da_sind():
    """A sentence about a tool that is switched off costs attention on the
    smallest local model and buys nothing."""
    ohne = grundprompt.bauen(werkzeuge=True)
    mit = grundprompt.bauen(werkzeuge=True, dateiwerkzeuge=True)
    assert "read_file" not in ohne
    assert "read_file" in mit
    # The parameter is named as the tool schema spells it, so the model does
    # not have to guess a name for it.
    assert "background=true" in mit


def test_der_fragen_baustein_haengt_am_werkzeug():
    ohne = grundprompt.bauen(werkzeuge=True)
    mit = grundprompt.bauen(werkzeuge=True, fragen=True)
    assert "ask_user" not in ohne
    assert "ask_user" in mit


def test_die_vorschau_wird_nur_erwaehnt_wenn_es_sie_gibt():
    ohne = grundprompt.bauen(werkzeuge=True)
    mit = grundprompt.bauen(werkzeuge=True, vorschau=True)
    assert "beside the chat" not in ohne
    assert "beside the chat" in mit


def test_ohne_werkzeuge_bleibt_der_prompt_wie_er_war():
    """The blocks belong to the tools. Without them nothing new appears."""
    schlicht = grundprompt.bauen()
    assert "read_file" not in schlicht
    assert "ask_user" not in schlicht
