"""The memory-at-a-glance endpoint the header pill polls."""

from __future__ import annotations


def test_speicherblick_liefert_das_zahlenpaar(client):
    antwort = client.get("/api/v1/system/speicher")
    assert antwort.status_code == 200
    daten = antwort.json()
    # None is a legal answer on a platform that cannot say — the window
    # then shows nothing. What must hold is the shape.
    assert set(daten) == {"belegt_gb", "gesamt_gb", "anteil"}
    if daten["belegt_gb"] is not None and daten["gesamt_gb"]:
        assert 0 < daten["belegt_gb"] <= daten["gesamt_gb"] * 1.0
        assert 0 < daten["anteil"] <= 1.0
