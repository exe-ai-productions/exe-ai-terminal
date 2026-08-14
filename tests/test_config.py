"""Configuration: loading, validation, derived paths."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from app.config import Config, config_laden


def test_mitgelieferte_config_ist_gueltig():
    """The config in place must always be loadable.

    The port is checked for being a port, not for being one particular
    number: config.yaml is not versioned, it belongs to whoever runs the
    program, and moving the service to another port is their business. What
    the number should be on a fresh install is asserted one test below, on
    the template — that file IS versioned, so a claim about it holds.
    """
    config = config_laden()
    assert 1 <= config.app.port <= 65535
    assert config.app.language in {"de", "en"}
    # Deliberately NOT "there has to be an endpoint": a fresh installation
    # has none. Providers are added in the cloud window, and a shipped file
    # that already named one would be somebody else's setup.
    assert isinstance(config.endpoints, list)


def test_die_vorlage_liefert_den_hausport():
    """What a fresh installation starts on, checked where it is versioned."""
    vorlage = Path(__file__).resolve().parent.parent / "config.example.yaml"
    daten = yaml.safe_load(vorlage.read_text(encoding="utf-8"))
    assert Config.model_validate(daten).app.port == 8090


def test_die_vorlage_kennt_jeden_schluessel_des_schemas():
    """The template is the target state, like schema.sql is for the database.

    An existing config.yaml is grown from this file (app/configwanderung.py),
    so a setting that only the schema knows about would never reach anybody's
    file: it would work, and nobody could find it. Whoever adds a field to
    the model writes it in here too, with the sentence that explains it.
    """
    vorlage = Path(__file__).resolve().parent.parent / "config.example.yaml"
    daten = yaml.safe_load(vorlage.read_text(encoding="utf-8"))

    fehlend: list[str] = []
    for abschnitt, feld in Config.model_fields.items():
        if abschnitt not in daten:
            fehlend.append(abschnitt)
            continue
        unter = feld.annotation
        if not (isinstance(unter, type) and issubclass(unter, BaseModel)):
            continue
        for name in unter.model_fields:
            if name not in (daten[abschnitt] or {}):
                fehlend.append(f"{abschnitt}.{name}")

    assert not fehlend, (
        "In config.example.yaml fehlen: "
        + ", ".join(fehlend)
        + " — jeder neue Schlüssel gehört mit erklärendem Kommentar in die Vorlage."
    )


def test_endpunkt_kennungen_sind_eindeutig():
    with pytest.raises(ValidationError):
        Config.model_validate(
            {
                "endpoints": [
                    {"id": "doppelt", "name": "A", "base_url": "http://a"},
                    {"id": "doppelt", "name": "B", "base_url": "http://b"},
                ]
            }
        )


def test_ungueltiger_port_wird_abgewiesen():
    with pytest.raises(ValidationError):
        Config.model_validate({"app": {"port": 99999}})


def test_basis_url_ohne_schraegstrich_am_ende():
    config = Config.model_validate(
        {"endpoints": [{"id": "a", "name": "A", "base_url": "http://host:8080/v1/"}]}
    )
    assert config.endpoints[0].base_url == "http://host:8080/v1"


def test_relative_pfade_werden_absolut(config: Config):
    assert config.datenbankpfad.is_absolute()
    assert config.datenverzeichnis.is_absolute()


def test_endpunkt_nachschlagen(config: Config):
    assert config.endpunkt("test") is not None
    assert config.endpunkt("gibtsnicht") is None


def test_fehlende_datei_meldet_klar(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        config_laden(tmp_path / "nicht-vorhanden.yaml")


def test_reasoning_format_wird_geprueft(tmp_path: Path):
    datei = tmp_path / "config.yaml"
    datei.write_text(
        yaml.safe_dump(
            {
                "endpoints": [
                    {
                        "id": "a",
                        "name": "A",
                        "base_url": "http://a",
                        "reasoning_format": "quatsch",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        config_laden(datei)


def test_alle_drei_reasoning_formate_erlaubt():
    for format_name in ("native", "harmony", "think", "none"):
        config = Config.model_validate(
            {
                "endpoints": [
                    {
                        "id": format_name,
                        "name": format_name,
                        "base_url": "http://a",
                        "reasoning_format": format_name,
                    }
                ]
            }
        )
        assert config.endpoints[0].reasoning_format == format_name


def test_host_vorgabe_ist_loopback():
    # A bare schema must bind locally — the network is opt-in, never a
    # fallback.
    from app.config import AppConfig

    assert AppConfig().host == "127.0.0.1"
