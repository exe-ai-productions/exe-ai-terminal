"""The machine memory readout: a plausible number on this machine."""

from app.systemspeicher import gesamt_gb


def test_liefert_plausible_zahl():
    gb = gesamt_gb()
    assert gb is not None
    assert 1 <= gb <= 4096
