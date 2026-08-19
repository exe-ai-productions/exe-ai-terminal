"""Closing the program stops every server it holds.

The model, embedding, guardian and image-turbo servers each run in their own
session, so a service crash does not take them down — which means a clean
shutdown must end them by hand, or they orphan and the next launch cannot
talk to them ("Invalid API-Key"). This guards that the shutdown does.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app_erstellen

SERVER = ("modellrunner", "einbettungsrunner", "eewrunner", "bildturbo")


def test_shutdown_stoppt_jeden_server(config):
    app = app_erstellen(config)
    gestoppt: list[str] = []

    with TestClient(app):
        # Startup has run; each server object is on app.state. Record the stop
        # instead of performing it — nothing is actually running in the test.
        for name in SERVER:
            server = getattr(app.state, name)

            def merker(n, roh):
                def wrapper():
                    gestoppt.append(n)
                    return roh()
                return wrapper

            server.stoppen = merker(name, server.stoppen)
    # Leaving the block ran the lifespan shutdown.

    assert set(gestoppt) == set(SERVER)
