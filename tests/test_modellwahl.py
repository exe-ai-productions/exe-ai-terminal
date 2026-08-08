"""What the user picked among the models — and that it actually gets stored.

The switch in the model window looked like it worked and stored nothing: the
settings route only vouched for `parameter`, so every write came back 400, and
the interface quietly put its own state back. These tests are there so that
cannot happen again silently.
"""

from __future__ import annotations

from app.modellwahl import aus_pruefen, wahl_pruefen


# --- What gets through ------------------------------------------------------


def test_aus_liste_nimmt_nur_saubere_kennungen():
    assert aus_pruefen(["a", " b ", "", None, 7, "a"]) == ["a", "b"]


def test_aus_liste_haelt_die_reihenfolge():
    assert aus_pruefen(["z", "a", "m"]) == ["z", "a", "m"]


def test_aus_liste_lehnt_alles_ab_was_keine_liste_ist():
    assert aus_pruefen({"a": 1}) == []
    assert aus_pruefen("a") == []
    assert aus_pruefen(None) == []


def test_wahl_nimmt_je_anbieter_die_modelle():
    assert wahl_pruefen({"openai": ["gpt-5.5", "gpt-5.5"], "anthropic": ["claude-opus-5"]}) == {
        "openai": ["gpt-5.5"],
        "anthropic": ["claude-opus-5"],
    }


def test_ein_anbieter_ohne_wahl_faellt_weg():
    """An empty entry says nothing its absence does not."""
    assert wahl_pruefen({"openai": [], "anthropic": ["x"]}) == {"anthropic": ["x"]}


def test_wahl_lehnt_alles_ab_was_kein_objekt_ist():
    assert wahl_pruefen(["openai"]) == {}
    assert wahl_pruefen(None) == {}


# --- And that the route really stores them ----------------------------------


def test_die_schnellwahl_laesst_sich_wirklich_abschalten(client):
    antwort = client.put(
        "/api/v1/settings/global/modelle_aus", json={"wert": ["qwen-mac"]}
    )
    assert antwort.status_code == 200
    assert antwort.json()["wert"] == ["qwen-mac"]

    # And it comes back — a list travels whole, there is nothing to merge.
    gelesen = client.get("/api/v1/settings/resolved/modelle_aus").json()
    assert gelesen["wert"] == ["qwen-mac"]


def test_die_katalogwahl_laesst_sich_wirklich_sichern(client):
    antwort = client.put(
        "/api/v1/settings/global/katalog_wahl",
        json={"wert": {"openai": ["gpt-5.5", "gpt-4o-mini"]}},
    )
    assert antwort.status_code == 200

    gelesen = client.get("/api/v1/settings/resolved/katalog_wahl").json()
    assert gelesen["wert"] == {"openai": ["gpt-5.5", "gpt-4o-mini"]}


def test_leere_wahl_loescht_den_eintrag(client):
    client.put("/api/v1/settings/global/modelle_aus", json={"wert": ["a"]})
    client.put("/api/v1/settings/global/modelle_aus", json={"wert": []})
    # Nothing set means the scope above applies — here there is none, so {}.
    assert client.get("/api/v1/settings/resolved/modelle_aus").json()["wert"] == {}


def test_eine_unbekannte_einstellung_kommt_nicht_durch(client):
    """The JSON column cannot check anything itself — whoever is not vouched
    for does not get in."""
    antwort = client.put("/api/v1/settings/global/irgendwas", json={"wert": [1]})
    assert antwort.status_code == 400
