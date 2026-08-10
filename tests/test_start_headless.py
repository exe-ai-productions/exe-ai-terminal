"""The sidecar service must not open its own window — the shell is one."""

import start


def test_headless_laesst_kein_fenster_oeffnen(monkeypatch):
    monkeypatch.setenv("EXE_AI_TERMINAL_HEADLESS", "1")
    beruehrt = []
    monkeypatch.setattr(start, "_antwortet", lambda port: beruehrt.append(port) or True)
    # Returns before ever probing the port — the probe list stays empty.
    start._browser_oeffnen(8090)
    assert beruehrt == []
