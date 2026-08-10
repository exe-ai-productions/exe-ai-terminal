"""The live memory readout, measured against our own process."""

import os

from app.prozessspeicher import rss_gb


def test_eigener_prozess_hat_speicher():
    gb = rss_gb(os.getpid())
    assert gb is not None
    assert 0 <= gb <= 512


def test_toter_prozess_liefert_none():
    # PIDs cycle, but this one is reserved-ish nowhere and long gone.
    assert rss_gb(99999999) is None
