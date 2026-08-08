"""Shared test fixtures.

Every test gets a fresh in-memory database — no test data ever ends up
in the real file. The model is the dummy (``MockProvider``) so the whole
chain can be checked without a running model server.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.db import Database, repositories_erstellen
from app.events import bus
from app.providers import MockProvider


@pytest.fixture(autouse=True)
def sauberer_eventbus():
    """Subscribers from one test must not leak into the next."""
    bus.alles_loeschen()
    yield
    bus.alles_loeschen()


@pytest.fixture
def db() -> Database:
    datenbank = Database(":memory:")
    datenbank.schema_einrichten()
    yield datenbank
    datenbank.schliessen()


@pytest.fixture
def repos(db: Database):
    return repositories_erstellen(db)


@pytest.fixture
def config(tmp_path) -> Config:
    return Config.model_validate(
        {
            "app": {
                "host": "127.0.0.1",
                "port": 8090,
                "language": "de",
                "data_dir": str(tmp_path / "data"),
                "log_dir": str(tmp_path / "logs"),
                # Must point into the test directory. Otherwise tests that
                # save the system prompt write to the project's real file.
                "system_prompt_file": str(tmp_path / "prompts" / "system.md"),
                # Same story for the memory: a test that saves one must not
                # write into the project's real prompts folder.
                "memory_file": str(tmp_path / "prompts" / "memory.md"),
                # Same story for the agents (6.3): never the real folder.
                "agenten_verzeichnis": str(tmp_path / "prompts" / "agenten"),
                # And the skills, both places. The shipped folder is
                # redirected as well: a test that reads it must not depend on
                # what happens to be shipped at the time.
                "skills_mitgeliefert": str(tmp_path / "skills"),
                "skills_verzeichnis": str(tmp_path / "prompts" / "skills"),
            },
            "database": {"backend": "sqlite", "path": str(tmp_path / "test.db")},
            # Both MCP files point into the test directory. Otherwise a
            # test that registers servers or stores credentials writes to
            # the project's real files (the paths are relative to the
            # project root!).
            "mcp": {
                "servers_file": str(tmp_path / "mcp_servers.json"),
                "auth_file": str(tmp_path / "mcp_auth.json"),
            },
            "features": {"mcp": False, "image_generation": True, "document_upload": True},
            "discovery": {"interval_seconds": 3600, "timeout_seconds": 1},
            "endpoints": [
                {
                    "id": "test",
                    "name": "Testendpunkt",
                    "provider": "mock",
                    "base_url": "http://127.0.0.1:9/v1/",
                    "reasoning_format": "think",
                },
                {
                    "id": "abwesend",
                    "name": "Nicht erreichbar",
                    "provider": "openai_compatible",
                    # Port 9 (discard) accepts no HTTP connections.
                    "base_url": "http://127.0.0.1:9/v1",
                },
            ],
        }
    )


@pytest.fixture
def client(config: Config) -> TestClient:
    from app.main import app_erstellen

    with TestClient(app_erstellen(config)) as testclient:
        yield testclient


@pytest.fixture
async def laufender_server(config: Config):
    """A real uvicorn on a free port.

    Needed for anything where the response really has to arrive in
    chunks — the ASGI test transport collects it all up front.
    """
    import asyncio
    import socket

    import uvicorn

    from app.main import app_erstellen

    lauscher = socket.socket()
    lauscher.bind(("127.0.0.1", 0))
    port = lauscher.getsockname()[1]
    lauscher.close()

    app = app_erstellen(config)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    aufgabe = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)

    try:
        yield app, f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await aufgabe


@pytest.fixture
def chat_id(client: TestClient) -> str:
    antwort = client.post("/api/v1/chats", json={"title": "Testchat"})
    assert antwort.status_code == 201
    return antwort.json()["id"]


def provider_setzen(client: TestClient, provider: MockProvider, endpoint_id: str = "test"):
    """Swaps out the dummy behind an endpoint and reports it as reachable."""
    zustand = client.app.state.discovery.zustaende[endpoint_id]
    zustand.provider = provider
    zustand.erreichbar = True
    return provider
