"""Configuration: loading, validation, derived paths."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.config import Config, config_laden


def test_mitgelieferte_config_ist_gueltig():
    """The versioned config.yaml must always be loadable."""
    config = config_laden()
    assert config.app.port == 8090
    assert config.app.language in {"de", "en"}
    # Deliberately NOT "there has to be an endpoint": a fresh installation
    # has none. Providers are added in the cloud window, and a shipped file
    # that already named one would be somebody else's setup.
    assert isinstance(config.endpoints, list)


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
