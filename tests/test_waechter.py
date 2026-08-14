"""The guardian: its allowance, its memory, and the one request it makes.

The loop guard is the part worth testing hardest. A guardian that reacts to
every failed step in a run that is going badly turns one problem into a
column of suggestions — which is exactly the situation in which somebody
needs a clear screen.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import eewserver, waechter, waechterwahl
from app.providers.mock import MockProvider
from app.waechter_ausloeser import Befund


def _befund(art: str = "befehl_gescheitert") -> Befund:
    return Befund(
        art=art,
        werkzeug="run_command",
        ergebnis="[exit code 1]",
        auftrag="Bau bitte das Frontend.",
        argumente={"command": "npm run baun"},
    )


def _zustand(provider=None, *, thinking: bool | None = None, erkannt: bool = False):
    """A stand-in for the guardian's endpoint state.

    Only the two things the guardian reads: whom to talk to, and whether the
    chat template over there knows the thinking flag at all.
    """
    return SimpleNamespace(
        provider=provider,
        endpunkt=SimpleNamespace(capabilities=SimpleNamespace(thinking=thinking)),
        thinking_erkannt=erkannt,
    )


@pytest.fixture
def wache():
    return waechter.Waechter()


def test_hoechstens_zwei_vorschlaege_je_auftrag(wache):
    assert wache.aufnehmen("chat", _befund()) is not None
    assert wache.aufnehmen("chat", _befund()) is not None
    # The third is where the guardian goes quiet.
    assert wache.aufnehmen("chat", _befund()) is None
    assert len(wache.liste("chat")) == 2


def test_ein_neuer_auftrag_setzt_die_erlaubnis_zurueck(wache):
    wache.aufnehmen("chat", _befund())
    wache.aufnehmen("chat", _befund())
    assert wache.darf_noch("chat") is False
    wache.neuer_auftrag("chat")
    assert wache.darf_noch("chat") is True
    assert wache.aufnehmen("chat", _befund()) is not None
    # The earlier findings stay: the allowance is for new ones, it is not
    # an eraser for what is still standing in the panel.
    assert len(wache.liste("chat")) == 3


def test_jeder_chat_zaehlt_fuer_sich(wache):
    wache.aufnehmen("a", _befund())
    wache.aufnehmen("a", _befund())
    assert wache.aufnehmen("b", _befund()) is not None
    assert len(wache.liste("b")) == 1


def test_verwerfen_und_vergessen(wache):
    eintrag = wache.aufnehmen("chat", _befund())
    assert wache.verwerfen("chat", eintrag.id) is True
    assert wache.verwerfen("chat", eintrag.id) is False
    wache.aufnehmen("chat", _befund())
    wache.vergessen("chat")
    assert wache.liste("chat") == []


def test_offene_sind_die_ohne_vorschlag(wache):
    eins = wache.aufnehmen("chat", _befund())
    zwei = wache.aufnehmen("chat", _befund())
    eins.vorschlag = "npm run build"
    assert [e.id for e in wache.offene("chat")] == [zwei.id]


def test_die_frage_traegt_auftrag_und_ergebnis():
    anfrage = waechter.frage_bauen(_befund())
    system, benutzer = anfrage.nachrichten
    assert system.content == waechter.ANWEISUNG
    assert "Bau bitte das Frontend." in benutzer.content
    assert "[exit code 1]" in benutzer.content
    assert "run_command" in benutzer.content


# --- The thinking switch is asked for, not stated --------------------------


def test_das_denken_wird_abgeschaltet_wo_die_vorlage_es_kennt():
    """On a model that reasons, a short ceiling is spent entirely on the
    reasoning — in a channel the panel never sees — and the answer never
    starts."""
    anfrage = waechter.frage_bauen(_befund(), None, _zustand(thinking=True))
    assert anfrage.zusatz == {"chat_template_kwargs": {"enable_thinking": False}}


def test_wo_die_vorlage_den_schalter_nicht_kennt_wird_nichts_gesendet():
    """Sent blindly the flag switches nothing off — it lands in the rendered
    prompt as text, which is worse than not asking."""
    assert waechter.frage_bauen(_befund(), None, _zustand(thinking=False)).zusatz == {}
    # Nothing configured and nothing detected is the same answer.
    assert waechter.frage_bauen(_befund(), None, _zustand()).zusatz == {}
    # Nothing configured, but the server's own template says it knows it.
    anfrage = waechter.frage_bauen(_befund(), None, _zustand(erkannt=True))
    assert anfrage.zusatz == {"chat_template_kwargs": {"enable_thinking": False}}


def test_ohne_endpunkt_wird_nichts_behauptet():
    """No endpoint, no opinion — the same answer as one that reveals nothing."""
    assert waechter.frage_bauen(_befund()).zusatz == {}


def test_der_vorschlag_wird_auf_die_anweisung_reduziert():
    assert waechter.vorschlag_saeubern("  npm run build  ") == "npm run build"
    assert waechter.vorschlag_saeubern("```\nnpm run build\n```") == "npm run build"
    assert waechter.vorschlag_saeubern("```bash\nnpm run build\n```") == "npm run build"
    lang = waechter.vorschlag_saeubern("x" * 900)
    assert len(lang) == waechter.VORSCHLAG_GRENZE


async def test_ein_vorschlag_kommt_vom_eigenen_server():
    provider = MockProvider(haeppchen=["Run ", "npm run build"])
    text = await waechter.vorschlag_holen(_zustand(provider), "qwen", _befund())
    assert text == "Run npm run build"


async def test_ein_gescheiterter_vorschlag_bleibt_stumm():
    """An extra that fails must not become a second error on top of the first."""
    provider = MockProvider(fehler="Server weg")
    assert await waechter.vorschlag_holen(_zustand(provider), "qwen", _befund()) == ""


def test_der_schalter_ist_ab_werk_an():
    assert waechterwahl.VORGABE == {"an": True}
    assert waechterwahl.schalter_pruefen({"an": False}) == {"an": False}
    # Anything that is not the switch is not stored.
    assert waechterwahl.schalter_pruefen(True) == {}
    assert waechterwahl.schalter_pruefen({"etwas": 1}) == {}


def test_die_modellwahl_ueberlebt_das_speichern():
    """The window sends the chosen file with the switch; it used to be thrown
    away here, so the choice was gone after the next restart."""
    assert waechterwahl.schalter_pruefen({"an": True, "modell": "klein.gguf"}) == {
        "an": True,
        "modell": "klein.gguf",
    }
    # Picked without touching the switch.
    assert waechterwahl.schalter_pruefen({"modell": " klein.gguf "}) == {
        "modell": "klein.gguf"
    }
    # Nothing picked is not a choice: the window sends null, and an empty
    # string stored here would override the scope above with nothing.
    assert waechterwahl.schalter_pruefen({"an": True, "modell": None}) == {"an": True}
    assert waechterwahl.schalter_pruefen({"an": True, "modell": "   "}) == {"an": True}
    lang = waechterwahl.schalter_pruefen({"modell": "x" * 500})
    assert len(lang["modell"]) == waechterwahl.MODELL_HOECHSTLAENGE


# --- The report carries what an answer needs -------------------------------


def test_freigegebene_ordner_stehen_im_befund():
    """Without them the "path outside" finding cannot be repaired at all."""
    anfrage = waechter.frage_bauen(_befund(), ["/Users/exe/Projekte/laden"])
    text = anfrage.nachrichten[1].content
    assert "Released folders: /Users/exe/Projekte/laden" in text


def test_mehrere_ordner_stehen_alle_drin():
    anfrage = waechter.frage_bauen(_befund(), ["/a/eins", "/b/zwei"])
    assert "Released folders: /a/eins, /b/zwei" in anfrage.nachrichten[1].content


def test_ohne_ordner_keine_leere_zeile():
    """A chat that has released nothing says nothing about folders."""
    text = waechter.frage_bauen(_befund(), []).nachrichten[1].content
    assert "Released folders" not in text
    assert waechter.frage_bauen(_befund()).nachrichten[1].content == text


def test_die_anweisung_verlangt_das_konkrete():
    anweisung = waechter.frage_bauen(_befund()).nachrichten[0].content
    for satz in ["ONE instruction", "Never repeat the call that just failed",
                 "own shell"]:
        assert satz in anweisung


def test_die_festen_werte_stehen_am_aufruf():
    anfrage = waechter.frage_bauen(_befund())
    assert anfrage.temperature == waechter.TEMPERATUR == 0.1
    assert anfrage.max_tokens == waechter.ANTWORT_GRENZE == 200


def test_viele_ordner_werden_ganz_weggelassen_statt_halbiert():
    """Half a path is a folder that does not exist, and naming one is worse
    than naming none."""
    ordner = [f"/Users/eins/projekte/{'p' * 90}/nummer{n}" for n in range(20)]
    zeile = waechter.ordnerzeile(ordner)
    assert len(zeile) <= waechter.ORDNER_GRENZE
    # What is there is there whole — every entry in the line is one of the
    # paths that went in, not the front half of one.
    for pfad in zeile.split(", "):
        assert pfad in ordner


# --- The window and the cutting limits are one decision --------------------


# Two ways to fill the argument block right up: one value far too long, and
# a great many that are each harmless. Both have to be tried — the per-value
# ceiling bounds the first and only the total bounds the second, and a
# worst case that exercises one of them says nothing about the other.
_ARGUMENTSCHAEDEN = {
    "ein riesiger Wert": {"old_text": "a" * 40000},
    "sehr viele kleine": {f"argument_nummer_{n}": "a" * 40 for n in range(200)},
    "Listen und Objekte": {f"liste_{n}": ["/ein/pfad" * 400] for n in range(50)},
}

# Folders short enough that several of them fit — the line has its own
# ceiling, and one path longer than the whole line would never reach it.
_ORDNER = [f"/Users/eins/projekte/{'p' * 40}/nummer{n}" for n in range(40)]


def _groesster_befund(argumente):
    """A finding with every one of its ceilings pushed against.

    Built through `pruefen` rather than by hand: the point is what the code
    really lets through, not what a test author believes it lets through.
    """
    from app import waechter_ausloeser as ausloeser

    return ausloeser.pruefen(
        # Not the shell tool, so a long name survives the catalogue — and
        # long, because the name comes out of the model's call.
        name="w" * 500,
        ergebnis="'" + "d" * 20000 + "' does not exist.",
        fehlgeschlagen=True,
        argumente=argumente,
        auftrag="b" * 20000,
    )


@pytest.mark.parametrize("argumente", _ARGUMENTSCHAEDEN.values(), ids=_ARGUMENTSCHAEDEN)
def test_der_groesste_moegliche_prompt_passt_ins_fenster(argumente):
    """The real guard on `KONTEXT`.

    A request that does not fit is not refused by the model server — it
    silently drops the front of it, and the suggestion then answers half a
    report. So the largest request this code can assemble is assembled here
    and measured. Raise a cutting limit without raising the window and this
    fails; that is what it is for.
    """
    befund = _groesster_befund(argumente)
    assert befund is not None
    anfrage = waechter.frage_bauen(befund, _ORDNER, _zustand(thinking=True))
    assert waechter.fenster_bedarf(anfrage) <= waechter.KONTEXT


@pytest.mark.parametrize("argumente", _ARGUMENTSCHAEDEN.values(), ids=_ARGUMENTSCHAEDEN)
def test_die_grenzen_halten_am_groessten_befund(argumente):
    """Each part of that worst case really is bounded — otherwise the test
    above would be measuring a prompt that happens to be small today."""
    from app import waechter_ausloeser as ausloeser

    befund = _groesster_befund(argumente)
    assert len(befund.werkzeug) == ausloeser.WERKZEUG_GRENZE
    assert len(befund.auftrag) == ausloeser.AUFTRAG_GRENZE
    assert len(befund.ergebnis) == ausloeser.ERGEBNIS_GRENZE
    assert len(str(befund.argumente)) <= ausloeser.ARGUMENTE_GRENZE
    assert len(waechter.ordnerzeile(_ORDNER)) <= waechter.ORDNER_GRENZE


# --- The guardian's own server ---------------------------------------------


def test_der_endpunkt_zeigt_auf_den_eigenen_server():
    endpunkt = eewserver.endpunkt_bauen()
    assert endpunkt.base_url == f"http://127.0.0.1:{eewserver.PORT_VORGABE}/v1"
    # The key the runner hands its server at every start. Without it the
    # request is turned away — the lock against pages knocking on localhost.
    assert endpunkt.api_key_env == eewserver.SCHLUESSEL_VARIABLE
    assert eewserver.endpunkt_bauen(9001).base_url == "http://127.0.0.1:9001/v1"


async def test_ohne_laufenden_server_gibt_es_keinen_stillen_rueckfall():
    """The whole point of the feature: no server, no suggestion, and it is
    said so. A second-best model is what this must never reach for."""
    with pytest.raises(eewserver.NichtBereit) as gefangen:
        await eewserver.wachzustand(None)
    assert gefangen.value.grund == "waechter.kein_server"

    aus = SimpleNamespace(lauf=lambda: None)
    with pytest.raises(eewserver.NichtBereit):
        await eewserver.wachzustand(aus)


async def test_der_laufende_server_wird_einmal_gefragt(monkeypatch):
    """What the server says about itself is asked of the server, once per
    loaded file — not maintained anywhere and not asked again per finding."""
    gefragt: list[str] = []

    async def _faehigkeiten(base_url, zeitgrenze, schluessel_variable):
        gefragt.append(base_url)
        return {"thinking": True, "tool_calls": False, "vision": False}

    async def _modellname(self, timeout=3.0):
        return "klein.gguf"

    monkeypatch.setattr(eewserver, "faehigkeiten_erkennen", _faehigkeiten)
    monkeypatch.setattr(
        "app.providers.openai_kompatibel.OpenAIKompatiblerProvider.modellname",
        _modellname,
    )
    monkeypatch.setattr(eewserver, "_zustaende", {})

    runner = SimpleNamespace(
        lauf=lambda: SimpleNamespace(port=8083, modell="klein.gguf", kontext=4096)
    )
    zustand, name = await eewserver.wachzustand(runner)
    assert zustand.endpunkt.base_url == "http://127.0.0.1:8083/v1"
    assert name == "klein.gguf"
    # The template over there knows the flag, so the guardian may switch the
    # thinking pass off on this endpoint.
    anfrage = waechter.frage_bauen(_befund(), None, zustand)
    assert anfrage.zusatz == {"chat_template_kwargs": {"enable_thinking": False}}

    await eewserver.wachzustand(runner)
    assert len(gefragt) == 1
