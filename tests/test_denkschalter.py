"""The thinking switch (interface milestone A): detection and pass-through."""

from __future__ import annotations

from types import SimpleNamespace

from app.denkschalter import zusatz
from app.discovery import denkschalter_im_template


def _zustand(config_thinking=None, erkannt=False):
    caps = SimpleNamespace(thinking=config_thinking)
    endpunkt = SimpleNamespace(capabilities=caps)
    return SimpleNamespace(endpunkt=endpunkt, thinking_erkannt=erkannt)


def test_template_erkennung():
    assert denkschalter_im_template("{% if enable_thinking %}…{% endif %}") is True
    assert denkschalter_im_template("nichts dergleichen") is False
    assert denkschalter_im_template("") is False


def test_zusatz_nur_wenn_geschaltet_und_schaltbar():
    # Not toggled -> send nothing along, no matter what the endpoint can do.
    assert zusatz(None, _zustand(erkannt=True)) == {}
    # Toggled, but the endpoint can't -> don't guess.
    assert zusatz(False, _zustand(erkannt=False)) == {}
    # Toggled and natively detected -> a real shutdown.
    assert zusatz(False, _zustand(erkannt=True)) == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_config_gewinnt_immer():
    # An explicit no in the config beats the detection (safety rule).
    assert zusatz(True, _zustand(config_thinking=False, erkannt=True)) == {}
    # An explicit yes applies even without detection.
    assert zusatz(True, _zustand(config_thinking=True, erkannt=False)) == {
        "chat_template_kwargs": {"enable_thinking": True}
    }
