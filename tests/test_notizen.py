"""Notes and the document dock.

The interesting half is the markup. A note carries four kinds of emphasis;
everything else is rebuilt away before it is stored. That is checked here in
its unpleasant variants — a script tag, an event attribute, a tag hidden
inside a comment — because a note is written by a person but can be pasted
from anywhere.

The dock's own rule: it holds four places and copies what it is given, so
the original may vanish afterwards.
"""

from __future__ import annotations

from app.dock import Dock
from app.notizen import Notizen, saeubern


# --- The whitelist ----------------------------------------------------------


def test_die_vier_auszeichnungen_bleiben():
    roh = "<b>fett</b> <i>kursiv</i> <u>unter</u> <mark data-farbe=\"gelb\">markiert</mark>"
    assert saeubern(roh) == roh


def test_ein_skript_kommt_nicht_durch():
    sauber = saeubern("<script>alert(1)</script>Text")
    assert "<script" not in sauber
    assert "alert(1)" in sauber  # the text survives, the tag does not


def test_ereignisse_und_fremde_attribute_fallen_weg():
    sauber = saeubern('<b onclick="boese()">fett</b>')
    assert sauber == "<b>fett</b>"


def test_ein_bild_mit_fehlerbehandlung_kommt_nicht_durch():
    """The classic: no script tag anywhere, and it still runs."""
    sauber = saeubern('<img src=x onerror="alert(1)">')
    assert "<img" not in sauber
    assert "onerror" not in sauber


def test_eine_unbekannte_farbe_wird_zur_schlichten_markierung():
    assert saeubern('<mark data-farbe="rot">x</mark>') == "<mark>x</mark>"


def test_ein_kommentar_versteckt_nichts():
    sauber = saeubern("<!-- <script>alert(1)</script> -->Text")
    assert "script" not in sauber


def test_offene_tags_werden_geschlossen():
    """A stray open tag would otherwise swallow everything after the note."""
    assert saeubern("<b>fett") == "<b>fett</b>"


def test_spitze_klammern_im_text_bleiben_text():
    assert saeubern("a < b und c > d") == "a &lt; b und c &gt; d"


# --- Storage ----------------------------------------------------------------


def test_eine_notiz_ueberlebt_den_neustart(tmp_path):
    notizen = Notizen(tmp_path)
    angelegt = notizen.anlegen("Besprechung", "<b>wichtig</b>")
    assert Notizen(tmp_path).alle() == [angelegt]


def test_aendern_und_loeschen(tmp_path):
    notizen = Notizen(tmp_path)
    notiz = notizen.anlegen("Alt", "Text")
    geaendert = notizen.aendern(notiz["id"], "Neu", "<i>Text</i>")
    assert geaendert["ueberschrift"] == "Neu"
    assert geaendert["inhalt"] == "<i>Text</i>"
    assert notizen.loeschen(notiz["id"]) is True
    assert notizen.alle() == []
    assert notizen.loeschen(notiz["id"]) is False


# --- The routes -------------------------------------------------------------


def test_die_runde_durch_die_route(client):
    angelegt = client.post(
        "/api/v1/notizen", json={"ueberschrift": "Notiz", "inhalt": "<b>x</b><script>y</script>"}
    )
    assert angelegt.status_code == 201
    kennung = angelegt.json()["id"]
    assert angelegt.json()["inhalt"] == "<b>x</b>y"

    assert [n["id"] for n in client.get("/api/v1/notizen").json()] == [kennung]

    geaendert = client.put(
        f"/api/v1/notizen/{kennung}", json={"ueberschrift": "Neu", "inhalt": "y"}
    )
    assert geaendert.json()["ueberschrift"] == "Neu"

    assert client.delete(f"/api/v1/notizen/{kennung}").status_code == 204
    assert client.get("/api/v1/notizen").json() == []
    assert client.delete(f"/api/v1/notizen/{kennung}").status_code == 404


# --- The dock ---------------------------------------------------------------


def test_das_dock_haelt_eine_eigene_kopie(tmp_path):
    """The original may vanish afterwards — that is the point of copying."""
    dock = Dock(tmp_path)
    eintrag = dock.ablegen("Rechnung.pdf", b"%PDF-1.4 ...", "application/pdf")
    gefunden = dock.holen(eintrag["id"])
    assert gefunden is not None
    assert gefunden[1].read_bytes() == b"%PDF-1.4 ..."
    assert eintrag["name"] == "Rechnung.pdf"


def test_das_dock_hat_genau_vier_plaetze(tmp_path):
    dock = Dock(tmp_path)
    for nummer in range(4):
        dock.ablegen(f"datei{nummer}.txt", b"x")
    assert dock.voll() is True
    try:
        dock.ablegen("zuviel.txt", b"x")
    except ValueError:
        pass
    else:
        raise AssertionError("Der fünfte Platz darf es nicht geben")


def test_ein_name_wird_nie_zum_pfad(tmp_path):
    dock = Dock(tmp_path)
    eintrag = dock.ablegen("../../boese.txt", b"x")
    _, pfad = dock.holen(eintrag["id"])
    assert pfad.parent == dock.ordner


def test_ein_geraeumter_platz_nimmt_die_datei_mit(tmp_path):
    dock = Dock(tmp_path)
    eintrag = dock.ablegen("weg.txt", b"x")
    _, pfad = dock.holen(eintrag["id"])
    assert dock.entfernen(eintrag["id"]) is True
    assert not pfad.exists()
    assert dock.alle() == []


def test_die_dock_route_nimmt_rohe_bytes(client):
    antwort = client.post(
        "/api/v1/notizen/dock?name=notiz.txt",
        content=b"hallo",
        headers={"Content-Type": "text/plain"},
    )
    assert antwort.status_code == 201
    kennung = antwort.json()["id"]

    assert [e["name"] for e in client.get("/api/v1/notizen/dock/alle").json()] == ["notiz.txt"]
    assert client.get(f"/api/v1/notizen/dock/{kennung}").content == b"hallo"
    assert client.delete(f"/api/v1/notizen/dock/{kennung}").status_code == 204
