"""Reasoning detection — the core of the streaming proxy.

Three formats, and each one has to work even when streaming tears the
marker apart right between two packets.
"""

from __future__ import annotations

import pytest

from app.reasoning import ReasoningParser, trennen


def _durchlaufen(parser: ReasoningParser, haeppchen: list[str]) -> tuple[str, str]:
    stuecke = []
    for teil in haeppchen:
        stuecke.extend(parser.feed(teil))
    stuecke.extend(parser.finish())
    antwort = "".join(t for sorte, t in stuecke if sorte == "content")
    gedanke = "".join(t for sorte, t in stuecke if sorte == "reasoning")
    return antwort, gedanke


# --- think tags (Magistral, Qwen, DeepSeek-R1) ---------------------------


def test_think_am_stueck():
    antwort, gedanke = trennen("<think>Überlege kurz</think>Die Antwort", "think")
    assert gedanke == "Überlege kurz"
    assert antwort == "Die Antwort"


def test_think_zeichenweise_gestreamt():
    """The worst case: every character its own packet."""
    text = "<think>abc</think>xyz"
    antwort, gedanke = _durchlaufen(ReasoningParser("think"), list(text))
    assert gedanke == "abc"
    assert antwort == "xyz"


def test_think_marker_zerrissen():
    antwort, gedanke = _durchlaufen(
        ReasoningParser("think"), ["<thi", "nk>Gedanke</thi", "nk>Antwort"]
    )
    assert gedanke == "Gedanke"
    assert antwort == "Antwort"


def test_think_ohne_marker_ist_alles_antwort():
    antwort, gedanke = trennen("Einfach nur Text", "think")
    assert antwort == "Einfach nur Text"
    assert gedanke == ""


def test_think_unabgeschlossen_bleibt_gedanke():
    """Response cancelled mid-reasoning — nothing may be lost."""
    antwort, gedanke = _durchlaufen(ReasoningParser("think"), ["<think>Halb fert"])
    assert gedanke == "Halb fert"
    assert antwort == ""


def test_think_text_davor_bleibt_antwort():
    antwort, gedanke = trennen("Vorwort <think>Gedanke</think> Nachwort", "think")
    assert antwort == "Vorwort  Nachwort"
    assert gedanke == "Gedanke"


# --- Harmony (GPT-OSS) ---------------------------------------------------


def test_harmony_analyse_und_final():
    text = (
        "<|start|>assistant<|channel|>analysis<|message|>Ich überlege<|end|>"
        "<|start|>assistant<|channel|>final<|message|>Fertige Antwort<|return|>"
    )
    antwort, gedanke = trennen(text, "harmony")
    assert gedanke == "Ich überlege"
    assert antwort == "Fertige Antwort"


def test_harmony_gestreamt_in_kleinen_haeppchen():
    text = (
        "<|channel|>analysis<|message|>Denken<|end|>"
        "<|channel|>final<|message|>Antwort<|return|>"
    )
    haeppchen = [text[i : i + 3] for i in range(0, len(text), 3)]
    antwort, gedanke = _durchlaufen(ReasoningParser("harmony"), haeppchen)
    assert gedanke == "Denken"
    assert antwort == "Antwort"


def test_harmony_commentary_gilt_als_gedanke():
    text = "<|channel|>commentary<|message|>Nebenbei<|end|><|channel|>final<|message|>Da"
    antwort, gedanke = trennen(text, "harmony")
    assert gedanke == "Nebenbei"
    assert antwort == "Da"


def test_harmony_steuerzeichen_landen_nirgends():
    antwort, gedanke = trennen(
        "<|channel|>final<|message|>Sauber<|return|>", "harmony"
    )
    assert antwort == "Sauber"
    assert "<|" not in antwort and "<|" not in gedanke


# --- native (Gemma 4) and none -------------------------------------------


def test_native_wird_nicht_im_text_gesucht():
    """With 'native' the server supplies its own field — the text stays untouched."""
    parser = ReasoningParser("native")
    stuecke = parser.feed("<think>das ist hier kein Marker</think>")
    assert stuecke == [("content", "<think>das ist hier kein Marker</think>")]


def test_none_reicht_text_unveraendert_durch():
    antwort, gedanke = trennen("Roher Text", "none")
    assert antwort == "Roher Text"
    assert gedanke == ""


def test_unbekanntes_format_faellt_auf_none_zurueck():
    parser = ReasoningParser("quatsch")
    assert parser.format == "none"


@pytest.mark.parametrize("format_name", ["think", "harmony", "none", "native"])
def test_leere_eingabe_ist_harmlos(format_name):
    parser = ReasoningParser(format_name)
    assert parser.feed("") == []
    assert parser.finish() == []
