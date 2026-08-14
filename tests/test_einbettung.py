"""Cutting documents up, and finding the right piece again.

The chunking is tested for being DETERMINISTIC above all else: a stored
vector belongs to the exact text it was computed from, and a chunking that
shifts by a word between two runs would quietly pair every section with its
neighbour's vector — a bug that produces plausible nonsense rather than an
error.
"""

from __future__ import annotations

import math

import pytest

from app import einbettung, einbettungwahl


def test_kurzer_text_bleibt_ein_abschnitt():
    assert einbettung.zerlegen("drei kleine Worte") == ["drei kleine Worte"]
    assert einbettung.zerlegen("") == []
    assert einbettung.zerlegen("   ") == []


def test_die_zerlegung_ist_wiederholbar():
    text = " ".join(f"wort{i}" for i in range(2500))
    assert einbettung.zerlegen(text) == einbettung.zerlegen(text)


def test_abschnitte_ueberlappen_sich_und_verlieren_nichts():
    """The overlap is what keeps a sentence on a boundary from being lost."""
    text = " ".join(str(i) for i in range(1000))
    abschnitte = einbettung.zerlegen(text, woerter=100, ueberlappung=20)
    assert len(abschnitte) > 1
    # Every word of the document appears somewhere.
    gesehen = set()
    for abschnitt in abschnitte:
        gesehen.update(abschnitt.split())
    assert gesehen == {str(i) for i in range(1000)}
    # And consecutive sections really do share their edge.
    erstes_ende = abschnitte[0].split()[-20:]
    zweiter_anfang = abschnitte[1].split()[:20]
    assert erstes_ende == zweiter_anfang


def test_der_letzte_abschnitt_ist_kein_reiner_ueberlapp():
    """Off by one here would append a section made only of repeat."""
    text = " ".join(str(i) for i in range(110))
    abschnitte = einbettung.zerlegen(text, woerter=100, ueberlappung=20)
    assert len(abschnitte) == 2
    assert abschnitte[1].split()[-1] == "109"


def test_eine_ueberlappung_die_nicht_kleiner_ist_wird_abgewiesen():
    with pytest.raises(ValueError):
        einbettung.zerlegen("a b c", woerter=10, ueberlappung=10)


def test_abschnitte_tragen_keine_zeilenumbrueche():
    """One section is one line — the program reads its inputs line by line."""
    text = "\n".join(f"zeile {i}" for i in range(400))
    for abschnitt in einbettung.zerlegen(text):
        assert "\n" not in abschnitt


def test_kosinus_misst_die_richtung():
    assert einbettung.kosinus([1, 0], [1, 0]) == pytest.approx(1.0)
    assert einbettung.kosinus([1, 0], [0, 1]) == pytest.approx(0.0)
    assert einbettung.kosinus([1, 0], [-1, 0]) == pytest.approx(-1.0)
    # Length must not matter — only direction.
    assert einbettung.kosinus([2, 2], [7, 7]) == pytest.approx(1.0)
    # Nothing to compare is not an error, it is no similarity.
    assert einbettung.kosinus([], [1]) == 0.0
    assert einbettung.kosinus([0, 0], [1, 1]) == 0.0


def test_ein_vektor_uebersteht_die_ablage():
    vektor = [0.5, -0.25, 1.0, 0.0]
    zurueck = einbettung.entpacken(einbettung.packen(vektor))
    assert len(zurueck) == len(vektor)
    for a, b in zip(vektor, zurueck):
        assert math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)


def test_die_suche_findet_den_passenden_abschnitt():
    gespeichert = [
        (1, "über Katzen", [1.0, 0.0, 0.0]),
        (2, "über Leuchttürme", [0.0, 1.0, 0.0]),
        (3, "auch über Leuchttürme", [0.3, 0.9, 0.0]),
    ]
    treffer = einbettung.naechste([0.0, 1.0, 0.0], gespeichert, anzahl=2)
    assert [t.nummer for t in treffer] == [2, 3]
    assert treffer[0].text == "über Leuchttürme"
    assert treffer[0].naehe == pytest.approx(1.0)


def test_ein_abschnitt_der_nichts_damit_zu_tun_hat_bleibt_liegen():
    """Not a weak match — no match. Filling the slot would be a lie."""
    gespeichert = [
        (1, "über Katzen", [1.0, 0.0, 0.0]),
        (2, "über Leuchttürme", [0.0, 1.0, 0.0]),
    ]
    treffer = einbettung.naechste([0.0, 1.0, 0.0], gespeichert, anzahl=6)
    assert [t.nummer for t in treffer] == [2]


def test_vektoren_anderer_laenge_liefern_nichts_statt_der_ersten_sechs():
    """The regression.

    Two embedding models, two vector lengths. Every similarity comes out
    0.0, and a list of zeros still sorts — stably, into the order the rows
    were inserted, which is document order. The search would have handed
    back the first sections of the file as though they were the answer.

    Nothing found is the honest outcome: the caller reads it as "no
    selection" and sends the whole document.
    """
    gespeichert = [
        (1, "erster Abschnitt", [1.0, 0.0, 0.0]),
        (2, "zweiter Abschnitt", [0.0, 1.0, 0.0]),
        (3, "dritter Abschnitt", [0.0, 0.0, 1.0]),
    ]
    # A question embedded by a model with four dimensions instead of three.
    treffer = einbettung.naechste([0.0, 1.0, 0.0, 0.0], gespeichert, anzahl=6)
    assert treffer == []


def test_eine_leere_frage_findet_nichts():
    gespeichert = [(1, "irgendwas", [1.0, 0.0])]
    assert einbettung.naechste([], gespeichert) == []


def test_der_kontext_nennt_herkunft_und_abschnitt():
    """A model that can name where it read something can be checked."""
    treffer = [einbettung.Treffer(nummer=12, text="der Satz", naehe=0.9)]
    text = einbettung.als_kontext("bericht.pdf", treffer)
    assert "bericht.pdf" in text
    assert "section 12" in text
    assert "der Satz" in text
    assert einbettung.als_kontext("bericht.pdf", []) == ""


def test_der_ordner_sagt_was_ein_einbettungsmodell_ist(tmp_path):
    """Not the file name.

    Reading the name and looking for "embed" in it put an embedding model
    into the language model's picker, sent its start against a port that was
    already taken, and pointed "open model folder" at the wrong folder. A
    file lying in the embedding folder is an embedding model, whatever it is
    called.
    """
    (tmp_path / "irgendwas.gguf").write_bytes(b"x")
    (tmp_path / "notiz.txt").write_text("kein Modell")
    assert einbettung.modelle(tmp_path) == ["irgendwas.gguf"]
    assert einbettung.modell_finden(tmp_path).name == "irgendwas.gguf"
    assert einbettung.modell_finden(tmp_path / "gibtsnicht") is None
    assert einbettung.modelle(tmp_path / "gibtsnicht") == []


def test_die_schwelle_und_der_schalter_stehen_fest():
    assert einbettung.SCHWELLE == 15000
    assert einbettung.MITREISENDE == 6
    assert einbettungwahl.VORGABE == {"an": True}
    assert einbettungwahl.schalter_pruefen({"an": False}) == {"an": False}
    assert einbettungwahl.schalter_pruefen("ja") == {}
