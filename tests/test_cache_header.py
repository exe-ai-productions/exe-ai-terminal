"""HTML must never come blindly from the browser cache.

index.html carries the reference to the current bundle — if it comes
from the cache, the app keeps running on an old version after an update
("the app doesn't update"). no-cache forces a check with the server;
everything non-HTML stays untouched, the bundles cache via their
changing file names.
"""

from __future__ import annotations


def test_html_traegt_no_cache(client):
    antwort = client.get("/app/")
    assert antwort.status_code == 200
    assert antwort.headers["cache-control"] == "no-cache"


def test_nicht_html_bleibt_unangetastet(client):
    antwort = client.get("/health")
    assert antwort.status_code == 200
    assert "cache-control" not in antwort.headers
