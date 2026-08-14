"""The configuration grows with the program without losing what is in it."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from app.config import AppConfig, Config, config_laden
from app.configwanderung import NEBEN_ENDUNG, SICHERUNG_ENDUNG, wandern

VORLAGE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def _wandern(datei: Path) -> list[str]:
    return wandern(datei, VORLAGE, Config)


def _schreiben(datei: Path, text: str) -> Path:
    datei.write_text(text, encoding="utf-8")
    return datei


def _untermodelle() -> dict[str, type[BaseModel]]:
    """The sections of the configuration that are models of their own."""
    gefunden: dict[str, type[BaseModel]] = {}
    for name, feld in Config.model_fields.items():
        annotation = feld.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            gefunden[name] = annotation
    return gefunden


# --- growing ------------------------------------------------------------


def test_fehlender_schluessel_wird_nachgetragen(tmp_path: Path):
    datei = _schreiben(
        tmp_path / "config.yaml",
        "app:\n  host: \"127.0.0.1\"\n  port: 8090\n",
    )
    nachgetragen = _wandern(datei)

    assert "app.einbettung_port" in nachgetragen
    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert daten["app"]["einbettung_port"] == AppConfig().einbettung_port
    assert daten["app"]["bildmodelle_verzeichnis"] == AppConfig().bildmodelle_verzeichnis


def test_jeder_bekannte_schluessel_steht_danach_in_der_datei(tmp_path: Path):
    """After the migration the file names everything the schema knows.

    That is the whole point: a setting nobody can see in their own file is a
    setting nobody can change.
    """
    datei = _schreiben(tmp_path / "config.yaml", "app:\n  port: 8090\n")
    _wandern(datei)
    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))

    assert set(Config.model_fields) <= set(daten)
    for abschnitt, unter in _untermodelle().items():
        assert set(unter.model_fields) <= set(daten[abschnitt] or {}), abschnitt


def test_nachgetragen_wird_der_schemawert_nicht_der_vorlagenwert(tmp_path: Path):
    """A migration must not change what the program does.

    The template says "en" because that is how a fresh installation starts.
    Somebody who has been running without the key has been running on the
    schema default all along, and writing the key down must not switch their
    interface language on them.
    """
    vorlage_daten = yaml.safe_load(VORLAGE.read_text(encoding="utf-8"))
    assert vorlage_daten["app"]["language"] != AppConfig().language

    datei = _schreiben(tmp_path / "config.yaml", "app:\n  port: 8090\n")
    _wandern(datei)

    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert daten["app"]["language"] == AppConfig().language


# --- keeping ------------------------------------------------------------


def test_benutzerwert_ueberlebt(tmp_path: Path):
    datei = _schreiben(
        tmp_path / "config.yaml",
        'app:\n  port: 9999\n  language: "en"\n  data_dir: "/eigene/daten"\n'
        "features:\n  mcp: true\n  shell_tool: false\n",
    )
    _wandern(datei)

    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert daten["app"]["port"] == 9999
    assert daten["app"]["language"] == "en"
    assert daten["app"]["data_dir"] == "/eigene/daten"
    assert daten["features"]["mcp"] is True
    # False is a value somebody set, not an absence. A migration that reads
    # it as "nothing there" would switch the shell tool back on.
    assert daten["features"]["shell_tool"] is False


def test_kommentare_und_reihenfolge_bleiben(tmp_path: Path):
    text = (
        "# My own header\n"
        "app:\n"
        "  # my own note about the port\n"
        "  port: 9999\n"
        "  host: \"0.0.0.0\"\n"
    )
    datei = _schreiben(tmp_path / "config.yaml", text)
    _wandern(datei)

    zeilen = datei.read_text(encoding="utf-8").splitlines()
    assert zeilen[0] == "# My own header"
    assert zeilen[1] == "app:"
    assert zeilen[2] == "  # my own note about the port"
    assert zeilen[3] == "  port: 9999"
    assert zeilen[4] == '  host: "0.0.0.0"'


def test_ein_zweiter_lauf_aendert_nichts(tmp_path: Path):
    datei = _schreiben(tmp_path / "config.yaml", "app:\n  port: 8090\n")
    _wandern(datei)
    danach = datei.read_text(encoding="utf-8")

    assert _wandern(datei) == []
    assert datei.read_text(encoding="utf-8") == danach


def test_vollstaendige_datei_wird_nicht_angefasst(tmp_path: Path):
    datei = tmp_path / "config.yaml"
    datei.write_text(VORLAGE.read_text(encoding="utf-8"), encoding="utf-8")
    vorher = datei.read_text(encoding="utf-8")

    assert _wandern(datei) == []
    assert datei.read_text(encoding="utf-8") == vorher
    assert not (tmp_path / f"config.yaml{SICHERUNG_ENDUNG}").exists()


# --- edge cases ---------------------------------------------------------


def test_leere_datei(tmp_path: Path):
    datei = _schreiben(tmp_path / "config.yaml", "")
    nachgetragen = _wandern(datei)

    assert nachgetragen
    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert Config.model_validate(daten).app.port == AppConfig().port


def test_datei_nur_aus_kommentaren(tmp_path: Path):
    datei = _schreiben(tmp_path / "config.yaml", "# nothing here yet\n")
    _wandern(datei)

    text = datei.read_text(encoding="utf-8")
    assert text.startswith("# nothing here yet")
    assert Config.model_validate(yaml.safe_load(text)) is not None


def test_leerer_abschnitt_wird_gefuellt(tmp_path: Path):
    datei = _schreiben(tmp_path / "config.yaml", "app:\nfeatures:\n  mcp: true\n")
    _wandern(datei)

    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert daten["app"]["port"] == AppConfig().port
    assert daten["features"]["mcp"] is True


def test_zeilenenden_bleiben_wie_sie_waren(tmp_path: Path):
    datei = tmp_path / "config.yaml"
    with datei.open("w", encoding="utf-8", newline="") as offen:
        offen.write("app:\r\n  port: 9999\r\n")
    _wandern(datei)

    with datei.open(encoding="utf-8", newline="") as offen:
        text = offen.read()
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")
    assert yaml.safe_load(text)["app"]["port"] == 9999


def test_kaputtes_yaml_bleibt_unangetastet(tmp_path: Path):
    kaputt = "app:\n  port: 8090\n   host: schief\n  - liste\n"
    datei = _schreiben(tmp_path / "config.yaml", kaputt)

    assert _wandern(datei) == []
    assert datei.read_text(encoding="utf-8") == kaputt
    assert not (tmp_path / f"config.yaml{SICHERUNG_ENDUNG}").exists()


def test_datei_die_keine_zuordnung_ist_bleibt_unangetastet(tmp_path: Path):
    text = "- eins\n- zwei\n"
    datei = _schreiben(tmp_path / "config.yaml", text)

    assert _wandern(datei) == []
    assert datei.read_text(encoding="utf-8") == text


def test_einzeiliger_abschnitt_wird_uebergangen(tmp_path: Path):
    """A section written in flow style is left alone.

    Pushing indented lines under `app: {port: 9999}` would produce a file
    that no longer parses — and a configuration nobody can read is worse
    than one that is merely incomplete.
    """
    text = "app: {port: 9999}\n"
    datei = _schreiben(tmp_path / "config.yaml", text)
    _wandern(datei)

    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert daten["app"] == {"port": 9999}
    assert "logging" in daten


def test_fehlende_datei_und_fehlende_vorlage(tmp_path: Path):
    assert wandern(tmp_path / "gibtsnicht.yaml", VORLAGE, Config) == []
    datei = _schreiben(tmp_path / "config.yaml", "app:\n  port: 8090\n")
    assert wandern(datei, tmp_path / "keine-vorlage.yaml", Config) == []


# --- writing ------------------------------------------------------------


def test_sicherung_wird_angelegt(tmp_path: Path):
    vorher = "app:\n  port: 9999\n"
    datei = _schreiben(tmp_path / "config.yaml", vorher)
    _wandern(datei)

    sicherung = tmp_path / f"config.yaml{SICHERUNG_ENDUNG}"
    assert sicherung.read_text(encoding="utf-8") == vorher
    assert not (tmp_path / f"config.yaml{NEBEN_ENDUNG}").exists()


@pytest.mark.skipif(os.name != "posix", reason="Rechte werden hier über POSIX-Bits gesetzt")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root umgeht Dateirechte")
def test_nicht_schreibbarer_ordner_verhindert_den_start_nicht(tmp_path: Path):
    ordner = tmp_path / "abgeschlossen"
    ordner.mkdir()
    datei = _schreiben(ordner / "config.yaml", "app:\n  port: 8090\n")
    vorher = datei.read_text(encoding="utf-8")
    ordner.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        assert _wandern(datei) == []
        assert datei.read_text(encoding="utf-8") == vorher
    finally:
        ordner.chmod(stat.S_IRWXU)


# --- hooked into the loader ---------------------------------------------


def test_config_laden_ergaenzt_und_laedt(tmp_path: Path):
    datei = _schreiben(tmp_path / "config.yaml", "app:\n  port: 9999\n")
    config = config_laden(datei)

    assert config.app.port == 9999
    daten = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert "einbettung_port" in daten["app"]
    assert "shell_tool" in daten["features"]


def test_config_laden_stolpert_nicht_ueber_kaputtes_yaml(tmp_path: Path):
    """A broken file still stops the program — but it stops on the file.

    The migration must not turn a typo into a rewritten file; the error the
    user gets has to be about the line they mistyped.
    """
    kaputt = "app:\n  port: 8090\n   host: schief\n  - liste\n"
    datei = _schreiben(tmp_path / "config.yaml", kaputt)

    with pytest.raises(yaml.YAMLError):
        config_laden(datei)
    assert datei.read_text(encoding="utf-8") == kaputt
