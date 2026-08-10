"""Internationalization: catalog upkeep and fallback behavior."""

from __future__ import annotations

import json

from app.i18n import LOCALES_VERZEICHNIS, STANDARDSPRACHE, t, verfuegbare_sprachen


def _schluessel_sammeln(knoten, praefix=""):
    for name, wert in knoten.items():
        pfad = f"{praefix}{name}"
        if isinstance(wert, dict):
            yield from _schluessel_sammeln(wert, f"{pfad}.")
        else:
            yield pfad


def test_deutsch_und_englisch_vorhanden():
    assert set(verfuegbare_sprachen()) >= {"de", "en"}


def test_kataloge_haben_dieselben_schluessel():
    """A text that exists in only one language is an error."""
    kataloge = {
        sprache: json.loads((LOCALES_VERZEICHNIS / f"{sprache}.json").read_text("utf-8"))
        for sprache in verfuegbare_sprachen()
    }
    referenz = set(_schluessel_sammeln(kataloge[STANDARDSPRACHE]))
    for sprache, katalog in kataloge.items():
        assert set(_schluessel_sammeln(katalog)) == referenz, f"Abweichung in {sprache}.json"


def test_kein_text_steht_unuebersetzt_in_beiden_katalogen():
    """The same wording in both files usually means one was copied and never
    translated — that is how two English sentences ended up in the German
    catalogue and stood there unnoticed.

    Some words really are the same in both languages. They are named here, one
    by one, so the list stays an argument and not a hiding place.
    """
    gleich_erlaubt = {
        # Proper names and marks.
        "app.name", "beta.marke", "app.ok",
        # Words English and German share unchanged.
        "chat.alle", "menue.chat", "menue.cloud", "jobs.bereich_chats",
        "editor.quelle_tools", "werkzeuge.eingebaut",
        "editor.gruppe_app", "editor.gruppe_prompts", "jobs.agent_waehlen",
        "einstellungen.auto", "parameter.aus_global",
        # Language names stand in their own language, on purpose.
        "einstellungen.sprache_deutsch", "einstellungen.sprache_englisch",
        # Pure units and placeholders.
        "nachricht.wartezeit_kurz", "werkzeug.laeuft",
        # "Skill" is the name of the thing, in both languages. Translating it
        # would invent a German word nobody types into the slash list.
        "skills.quelle",
        # VRAM is the label on graphics memory in both languages — a German
        # spelling of it does not exist outside dictionaries.
        "modell.vram_label",
        # Server is the German word for server as much as the English one.
        "modell.server_status_label",
        # A network port is called a port in German too. "Anschluss" is the
        # dictionary answer and not what anybody says or reads.
        "modell.feld_port",
        # German tech speech says "downloaded"; the dictionary word would be
        # longer without being clearer.
        "modell.im_ordner",
        # "Vision" is what both communities call a model that sees; only the
        # capital letter differs and the comparison is case-sensitive anyway.
        "modell.augen",
        # "Name" is the same word in both languages, and an example address
        # is a literal — translating either would only invent a difference.
        "modell.eigener_name", "modell.eigener_adresse_beispiel",
    }

    def flach(knoten, praefix=""):
        for name, wert in knoten.items():
            pfad = f"{praefix}{name}"
            if isinstance(wert, dict):
                yield from flach(wert, f"{pfad}.")
            else:
                yield pfad, wert

    de = dict(flach(json.loads((LOCALES_VERZEICHNIS / "de.json").read_text("utf-8"))))
    en = dict(flach(json.loads((LOCALES_VERZEICHNIS / "en.json").read_text("utf-8"))))

    verdaechtig = sorted(
        schluessel
        for schluessel, text in de.items()
        if schluessel not in gleich_erlaubt and en.get(schluessel) == text
    )
    assert not verdaechtig, (
        "Gleicher Text in beiden Katalogen — vermutlich nicht übersetzt: "
        + ", ".join(verdaechtig)
    )


def test_uebersetzung_je_sprache():
    assert t("chat.neu", "de") == "Neuer Chat"
    assert t("chat.neu", "en") == "New chat"


def test_platzhalter_werden_gesetzt():
    text = t("fehler.modell_nicht_erreichbar", "de", name="Mana")
    assert "Mana" in text


def test_unbekannte_sprache_faellt_zurueck():
    assert t("chat.neu", "fr") == t("chat.neu", STANDARDSPRACHE)


def test_unbekannter_schluessel_gibt_schluessel_zurueck():
    assert t("gibt.es.nicht", "de") == "gibt.es.nicht"


def test_fehlender_platzhalter_stuerzt_nicht_ab():
    # No crash — just the unchanged text.
    assert "{" in t("kontext.auslastung", "de")
