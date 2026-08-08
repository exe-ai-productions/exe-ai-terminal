"""The terminal inside the terminal — the testable parts.

The drawing itself is not tested (that is judged by an eye, not a test
run). Tested is everything where a wrong decision could silently go
astray: configuration, color opt-out, context bar, attachment
detection, and the parsing of the event stream.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cli import befehle, konfiguration
from cli.farben import Stift, farben_erlaubt
from cli.sitzung import Sitzung, _vorschau


# --- Configuration ---------------------------------------------------------


def test_adresse_wird_hoeflich_ergaenzt():
    # Local stays unencrypted, remote gets encrypted.
    assert konfiguration.adresse_putzen("127.0.0.1:8090") == "http://127.0.0.1:8090"
    assert konfiguration.adresse_putzen("localhost:8090") == "http://localhost:8090"
    assert konfiguration.adresse_putzen("exe-hq.net") == "https://exe-hq.net"
    # A trailing slash only gets in the way.
    assert konfiguration.adresse_putzen("https://exe-hq.net/") == "https://exe-hq.net"
    assert konfiguration.adresse_putzen("") == konfiguration.VORGABE_ADRESSE


def test_konfiguration_schreiben_und_lesen(tmp_path, monkeypatch):
    monkeypatch.setattr(konfiguration, "ORDNER", tmp_path)
    monkeypatch.setattr(konfiguration, "DATEI", tmp_path / "config")
    e = konfiguration.Einstellungen(adresse="https://exe-hq.net", schluessel="geheim")
    datei = konfiguration.schreiben(e)
    # The key is a secret: only the owner may read the file.
    assert oct(datei.stat().st_mode)[-3:] == "600"
    gelesen = konfiguration.lesen()
    assert gelesen.adresse == "https://exe-hq.net"
    assert gelesen.schluessel == "geheim"


def test_umgebung_uebersteuert_die_datei(tmp_path, monkeypatch):
    monkeypatch.setattr(konfiguration, "ORDNER", tmp_path)
    monkeypatch.setattr(konfiguration, "DATEI", tmp_path / "config")
    konfiguration.schreiben(konfiguration.Einstellungen(adresse="http://a"))
    monkeypatch.setenv("EXE_TERMINAL_ADRESSE", "http://b")
    assert konfiguration.lesen().adresse == "http://b"


# --- Colors ----------------------------------------------------------------


def test_keine_farben_wenn_niemand_hinschaut(monkeypatch):
    # Redirected into a file: control characters have no business there.
    class KeinBildschirm:
        def isatty(self):
            return False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert farben_erlaubt(KeinBildschirm()) is False


def test_no_color_wird_geachtet(monkeypatch):
    class Bildschirm:
        def isatty(self):
            return True

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("NO_COLOR", "1")
    assert farben_erlaubt(Bildschirm()) is False


def test_stift_ohne_farbe_laesst_text_unberuehrt():
    s = Stift(an=False)
    assert s.denken("hallo") == "hallo"
    assert s.fett("hallo") == "hallo"
    # And with color the text is still there unchanged, just wrapped.
    bunt = Stift(an=True).denken("hallo")
    assert "hallo" in bunt and bunt != "hallo"


# --- Context bar -----------------------------------------------------------


def _sitzung(context_tokens=1000, verbraucht=0):
    modell = {"id": "m", "name": "M", "context_tokens": context_tokens, "capabilities": {}}
    s = Sitzung(SimpleNamespace(), Stift(an=False), {"id": "c", "title": "t"}, modell)
    s.verbraucht = verbraucht
    return s


def test_kontextleiste_bleibt_still_solange_platz_ist():
    assert _sitzung(verbraucht=100).kontextleiste() is None      # 10 %
    assert _sitzung(verbraucht=690).kontextleiste() is None      # 69 %


def test_kontextleiste_meldet_sich_wenn_es_eng_wird():
    leiste = _sitzung(verbraucht=800).kontextleiste()            # 80 %
    assert leiste is not None and "80%" in leiste
    # German thousands separator, not the English one.
    voll = _sitzung(context_tokens=32768, verbraucht=30000).kontextleiste()
    assert "32.768" in voll and "32,768" not in voll


def test_kontextleiste_auf_wunsch_immer():
    s = _sitzung(verbraucht=10)
    s.kontext_zeigen = True
    assert s.kontextleiste() is not None


def test_ohne_bekannte_kontextgroesse_keine_leiste():
    assert _sitzung(context_tokens=0, verbraucht=500).kontextleiste() is None


# --- Attachments -----------------------------------------------------------


def test_nur_wirklich_vorhandene_dateien_werden_angehaengt(tmp_path):
    echt = tmp_path / "bericht.pdf"
    echt.write_bytes(b"%PDF-1.4")
    assert befehle._pfad_erkennen(str(echt)) == echt
    # Quotes and escaped spaces, the way terminals insert them
    mit_luecke = tmp_path / "mein bericht.txt"
    mit_luecke.write_text("x")
    assert befehle._pfad_erkennen(f'"{mit_luecke}"') == mit_luecke
    assert befehle._pfad_erkennen(str(mit_luecke).replace(" ", "\\ ")) == mit_luecke
    # A merely mentioned path is NOT uploaded.
    assert befehle._pfad_erkennen(str(tmp_path / "gibtsnicht.pdf")) is None
    # And a question stays a question.
    assert befehle._pfad_erkennen("Was steht in bericht.pdf?") is None


def test_unbekannte_endungen_bleiben_text(tmp_path):
    komisch = tmp_path / "programm.exe"
    komisch.write_bytes(b"MZ")
    assert befehle._pfad_erkennen(str(komisch)) is None


# --- Event stream ----------------------------------------------------------


def test_vorschau_nimmt_das_sprechendste_argument():
    assert _vorschau({"query": "Eiffelturm"}) == "Eiffelturm"
    assert _vorschau({"url": "https://example.org"}) == "https://example.org"
    # No known name: any text is better than nothing.
    assert _vorschau({"irgendwas": "trotzdem"}) == "trotzdem"
    assert _vorschau({"anzahl": 3}) == ""
    assert _vorschau(None) == ""


class StromAttrappe:
    """Plays back an event stream the way the server sends it."""

    def __init__(self, ereignisse):
        self.ereignisse = ereignisse
        self.abgebrochen = []

    def antworten(self, **_):
        from cli.verbindung import Ereignis

        for typ, daten in self.ereignisse:
            yield Ereignis(typ, {"typ": typ, **daten})

    def abbrechen(self, gid):
        self.abgebrochen.append(gid)


def test_lauf_sammelt_alles_ein(capsys):
    strom = StromAttrappe([
        ("start", {"generation_id": "g1"}),
        ("reasoning", {"text": "denk denk"}),
        ("tool_call", {"name": "web_search", "argumente": {"query": "Eiffelturm"}}),
        ("tool_result", {"name": "web_search", "fehlgeschlagen": False, "text": "330 m"}),
        ("content", {"text": "Der Turm "}),
        ("content", {"text": "ist 330 m hoch."}),
        ("stats", {"daten": {"tokens_pro_sekunde": 22.5, "dauer_sekunden": 3.1,
                             "nutzung": {"total_tokens": 900}}}),
        ("done", {"abgebrochen": False}),
    ])
    s = Sitzung(strom, Stift(an=False), {"id": "c", "title": "t"},
                {"id": "m", "name": "M", "context_tokens": 1000, "capabilities": {}})
    lauf = s.fragen("Wie hoch ist der Eiffelturm?")

    assert lauf.generation_id == "g1"
    assert lauf.text == "Der Turm ist 330 m hoch."
    assert lauf.denken == len("denk denk")
    assert len(lauf.werkzeuge) == 1 and lauf.werkzeuge[0].fertig
    assert lauf.messwerte["tokens_pro_sekunde"] == 22.5
    # The usage is carried over into the context bar …
    assert s.verbraucht == 900
    # … and since that is 90 %, it now speaks up on its own.
    assert s.kontextleiste() is not None

    ausgabe = capsys.readouterr().out
    assert "Der Turm ist 330 m hoch." in ausgabe
    assert "web_search" in ausgabe          # the tool line stays visible
    assert "Zeichen Gedankengang" in ausgabe  # the thought folds itself up


def test_fehler_im_strom_wird_gemeldet(capsys):
    strom = StromAttrappe([("start", {"generation_id": "g"}),
                           ("error", {"text": "Modell weg"}),
                           ("done", {"abgebrochen": False})])
    s = Sitzung(strom, Stift(an=False), {"id": "c", "title": "t"},
                {"id": "m", "name": "M", "context_tokens": 100, "capabilities": {}})
    lauf = s.fragen("hallo")
    assert lauf.fehler == "Modell weg"
    assert "Modell weg" in capsys.readouterr().out


def test_denkschalter_geht_nur_mit_wenn_das_modell_es_kann():
    gesehen = {}

    class Merker(StromAttrappe):
        def antworten(self, **koerper):
            gesehen.update(koerper)
            return iter(())

    ohne = Sitzung(Merker([]), Stift(an=False), {"id": "c", "title": "t"},
                   {"id": "m", "name": "M", "context_tokens": 10, "capabilities": {}})
    ohne.fragen("hallo")
    assert "thinking" not in gesehen

    gesehen.clear()
    mit = Sitzung(Merker([]), Stift(an=False), {"id": "c", "title": "t"},
                  {"id": "m", "name": "M", "context_tokens": 10,
                   "capabilities": {"thinking": True}})
    mit.denken_an = False
    mit.fragen("hallo")
    assert gesehen["thinking"] is False


# --- Commands --------------------------------------------------------------


def _befehls_sitzung(modelle=None, chats=None):
    class V:
        def __init__(self):
            self.geloescht = []

        def modelle(self):
            return modelle or [{"id": "a", "name": "Alpha", "quelle": "llama.cpp",
                                "capabilities": {"thinking": True}},
                               {"id": "b", "name": "Beta", "quelle": "MLX",
                                "capabilities": {}}]

        def chats(self):
            return chats or [{"id": "c1", "title": "Erster"}, {"id": "c2", "title": "Zweiter"}]

        def chat_anlegen(self, titel="Terminal"):
            return {"id": "neu", "title": titel}

        def chat_loeschen(self, chat_id):
            self.geloescht.append(chat_id)

    v = V()
    s = Sitzung(v, Stift(an=False), {"id": "c1", "title": "Erster"},
                {"id": "a", "name": "Alpha", "context_tokens": 100,
                 "capabilities": {"thinking": True}})
    return s, v


def test_modell_wechseln_per_nummer_und_name():
    s, _ = _befehls_sitzung()
    befehle.ausfuehren("/modell 2", s, Stift(an=False))
    assert s.modell["id"] == "b"
    befehle.ausfuehren("/modell Alpha", s, Stift(an=False))
    assert s.modell["id"] == "a"
    ergebnis = befehle.ausfuehren("/modell gibtsnicht", s, Stift(an=False))
    assert "Kein Modell" in ergebnis.text


def test_denken_laesst_sich_nur_schalten_wo_es_geht():
    s, _ = _befehls_sitzung()
    assert s.denken_an is True
    befehle.ausfuehren("/denken", s, Stift(an=False))
    assert s.denken_an is False
    # Model without a thinking switch: the message stays honest, nothing flips.
    s.modell = {"id": "b", "name": "Beta", "context_tokens": 100, "capabilities": {}}
    vorher = s.denken_an
    ergebnis = befehle.ausfuehren("/denken", s, Stift(an=False))
    assert s.denken_an is vorher and "nicht schalten" in ergebnis.text


def test_chat_wechseln_und_loeschen():
    s, v = _befehls_sitzung()
    befehle.ausfuehren("/chats 2", s, Stift(an=False))
    assert s.chat["id"] == "c2"
    befehle.ausfuehren("/loeschen", s, Stift(an=False))
    assert v.geloescht == ["c2"] and s.chat["id"] == "neu"


def test_beenden_stoppt_die_schleife():
    s, _ = _befehls_sitzung()
    assert befehle.ausfuehren("/beenden", s, Stift(an=False)).weiter is False
    assert befehle.ausfuehren("/hilfe", s, Stift(an=False)).weiter is True


def test_unbekannter_befehl_verweist_auf_die_hilfe():
    s, _ = _befehls_sitzung()
    assert "/hilfe" in befehle.ausfuehren("/quatsch", s, Stift(an=False)).text


def test_eine_webseite_statt_der_schnittstelle_wird_erkannt():
    """An address that answers with a web page is nearly always the wrong
    one — a router, a proxy, another program on the same port. It comes back
    with status 200, so without this check the call would die on a parse
    error and nobody would know why."""
    import httpx
    from cli.verbindung import Verbindung, VerbindungsFehler

    v = Verbindung.__new__(Verbindung)
    seite = httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"},
                           text="<html>Zugangsschlüssel</html>")
    with pytest.raises(VerbindungsFehler) as fehler:
        v._pruefen(seite)
    assert "Exe AI Terminal" in str(fehler.value)

    # A redirect means the same thing.
    with pytest.raises(VerbindungsFehler):
        v._pruefen(httpx.Response(303, headers={"location": "/__tor"}))

    # And an occupied terminal is named as such.
    with pytest.raises(VerbindungsFehler) as belegt:
        v._pruefen(httpx.Response(423, json={"detail": "besetzt"}))
    assert "belegt" in str(belegt.value)


def test_eingabekasten_hat_gleich_lange_kanten(monkeypatch):
    """Top and bottom edges must be exactly the same length — otherwise
    the box looks crooked, and that is exactly what happened on the
    first build."""
    from cli import sitzung as s_modul
    from cli.sitzung import eingabekasten, kastenboden

    monkeypatch.setattr(s_modul, "breite", lambda: 60)
    stift = Stift(an=False)
    for hinweis in ("", "Qwen 3.6 27B", "Qwen 3.6 27B · Denken aus · Bild angehängt"):
        oben = eingabekasten(stift, hinweis)
        unten = kastenboden(stift)
        assert len(oben) == len(unten), f"schief bei Hinweis {hinweis!r}"
        assert oben.startswith("╭") and oben.endswith("╮")
        assert unten.startswith("╰") and unten.endswith("╯")


# --- Tool confirmations ------------------------------------------------------


class FragenStrom(StromAttrappe):
    """Like StromAttrappe, but remembers the answer to the confirmation prompt."""

    def __init__(self, ereignisse):
        super().__init__(ereignisse)
        self.bestaetigt = []

    def bestaetigen(self, generation_id, aufruf_id, erlaubt):
        self.bestaetigt.append((generation_id, aufruf_id, erlaubt))
        return True


def _rueckfrage_sitzung(strom):
    return Sitzung(strom, Stift(an=False), {"id": "c", "title": "t"},
                   {"id": "m", "name": "M", "context_tokens": 1000, "capabilities": {}})


EREIGNISSE = [
    ("start", {"generation_id": "g7"}),
    ("tool_confirm", {"name": "notion_schreiben", "aufruf_id": "a1",
                      "argumente": {"seite": "Bauplan", "text": "Hallo"}}),
    ("tool_call", {"name": "notion_schreiben", "argumente": {"seite": "Bauplan"}}),
    ("tool_result", {"name": "notion_schreiben", "fehlgeschlagen": False, "text": "ok"}),
    ("content", {"text": "Erledigt."}),
    ("done", {"abgebrochen": False}),
]


def test_rueckfrage_zeigt_die_argumente_woertlich(capsys, monkeypatch):
    strom = FragenStrom(EREIGNISSE)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda *_: "j")
    _rueckfrage_sitzung(strom).fragen("mach mal")

    ausgabe = capsys.readouterr().out
    # The user must see WHAT is about to run — not just THAT something wants to.
    assert "notion_schreiben" in ausgabe
    assert "seite" in ausgabe and "Bauplan" in ausgabe
    assert strom.bestaetigt == [("g7", "a1", True)]


def test_enter_allein_lehnt_ab(capsys, monkeypatch):
    """The default is NO: pressing only Enter is not consent."""
    strom = FragenStrom(EREIGNISSE)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda *_: "")
    _rueckfrage_sitzung(strom).fragen("mach mal")
    assert strom.bestaetigt == [("g7", "a1", False)]


def test_abbruch_waehrend_der_rueckfrage_lehnt_ab(monkeypatch):
    strom = FragenStrom(EREIGNISSE)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))

    def bricht_ab(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", bricht_ab)
    _rueckfrage_sitzung(strom).fragen("mach mal")
    assert strom.bestaetigt == [("g7", "a1", False)]


def test_ohne_tastatur_wird_abgelehnt(capsys, monkeypatch):
    """In scripted use nobody can answer — then nothing runs."""
    strom = FragenStrom(EREIGNISSE)
    monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: False))
    _rueckfrage_sitzung(strom).fragen("mach mal")
    assert strom.bestaetigt == [("g7", "a1", False)]
    assert "Keine Tastatur" in capsys.readouterr().out


def test_ja_wird_erkannt_in_beiden_sprachen(monkeypatch):
    for antwort in ("j", "ja", "y", "yes", "JA"):
        strom = FragenStrom(EREIGNISSE)
        monkeypatch.setattr("sys.stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda *_, a=antwort: a)
        _rueckfrage_sitzung(strom).fragen("mach mal")
        assert strom.bestaetigt[0][2] is True, f"„{antwort}“ wurde nicht als Ja verstanden"


# --- Images in the terminal --------------------------------------------------


def test_bilder_nur_wo_das_terminal_es_kann(monkeypatch, tmp_path):
    """A drawing attempt in the wrong terminal spits out a page of
    gibberish — so we first ask what we're dealing with."""
    from cli import bilder

    class Bildschirm:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr("sys.stdout", Bildschirm())
    for name in ("TERM", "TERM_PROGRAM", "KITTY_WINDOW_ID", "KONSOLE_VERSION",
                 "GHOSTTY_RESOURCES_DIR"):
        monkeypatch.delenv(name, raising=False)

    # Unknown terminal: don't even try.
    assert bilder.kann_bilder() == ""
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert bilder.kann_bilder() == ""
    # The two protocols are kept apart.
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    assert bilder.kann_bilder() == "iterm"
    monkeypatch.setenv("TERM", "xterm-kitty")
    assert bilder.kann_bilder() == "kitty"


def test_kein_bild_ohne_bildschirm(monkeypatch, tmp_path):
    from cli import bilder

    monkeypatch.setattr("sys.stdout", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    assert bilder.kann_bilder() == ""
    bild = tmp_path / "punkt.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert bilder.zeigen(bild) is None


def test_bild_wird_kodiert_mitgeschickt(monkeypatch, tmp_path):
    from cli import bilder

    monkeypatch.setattr("sys.stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    bild = tmp_path / "punkt.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\ntestdaten")
    gemalt = bilder.zeigen(bild, hoehe_zeilen=6)
    assert gemalt.startswith("\033]1337;File=")
    assert "height=6" in gemalt and "inline=1" in gemalt


def test_riesige_bilder_werden_nicht_durchgeschoben(monkeypatch, tmp_path):
    """Encoded, an image grows by a third — you don't push that through
    a pipe meant for text."""
    from cli import bilder

    monkeypatch.setattr("sys.stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    riesig = tmp_path / "riesig.png"
    riesig.write_bytes(b"x" * (9 * 1024 * 1024))
    assert bilder.zeigen(riesig) is None


# --- Multi-line input --------------------------------------------------------


def _tippt(monkeypatch, zeilen):
    folge = iter(zeilen)

    def naechste(*_):
        try:
            return next(folge)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", naechste)


def test_rueckstrich_setzt_die_eingabe_fort(monkeypatch):
    from cli.sitzung import mehrzeilig_lesen

    _tippt(monkeypatch, ["Erste Zeile \\", "zweite Zeile \\", "dritte Zeile"])
    assert mehrzeilig_lesen(Stift(an=False)) == "Erste Zeile\nzweite Zeile\ndritte Zeile"


def test_einzelne_zeile_bleibt_einfach(monkeypatch):
    from cli.sitzung import mehrzeilig_lesen

    _tippt(monkeypatch, ["Nur eine Frage"])
    assert mehrzeilig_lesen(Stift(an=False)) == "Nur eine Frage"


def test_strg_d_beendet_und_strg_c_verwirft(monkeypatch, capsys):
    from cli.sitzung import mehrzeilig_lesen

    def wirft_eof(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", wirft_eof)
    assert mehrzeilig_lesen(Stift(an=False)) is None      # Ctrl+D: out

    def wirft_abbruch(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", wirft_abbruch)
    assert mehrzeilig_lesen(Stift(an=False)) == ""        # Ctrl+C: discarded


def test_viele_zeilen_werden_nicht_abgeschnitten(monkeypatch):
    """The box grows only up to three rows — but the text arrives complete."""
    from cli.sitzung import mehrzeilig_lesen

    _tippt(monkeypatch, [f"Zeile {i} \\" for i in range(1, 6)] + ["Schluss"])
    ergebnis = mehrzeilig_lesen(Stift(an=False))
    assert ergebnis.count("\n") == 5
    assert ergebnis.endswith("Schluss")


def test_pfad_geht_vor_befehl(tmp_path):
    """On Unix every path starts with a slash — it must not be mistaken
    for a command. That was exactly the bug."""
    bild = tmp_path / "urlaub.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert befehle._pfad_erkennen(str(bild)) == bild
    assert str(bild).startswith("/")
