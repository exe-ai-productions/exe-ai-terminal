"""The starting values of the picture window.

The panel writes them and the window reads them, and between the two sits the
settings route, which only lets through what a checker vouches for. This key
had no checker: the panel showed the new numbers, the write came back 400,
and reopening the window brought back the old ones — silently, because the
panel swallowed the error.

So the first test here is not about clamping at all. It is about the key
being allowed through the route in the first place.
"""

from __future__ import annotations

import pytest

from app import bildvorgabenwahl
from app.api.v1.einstellungen import PRUEFER
from app.bildwahlen import MAX_KANTE, MAX_SCHRITTE, MIN_KANTE, RASTER


# --- The route lets it through --------------------------------------------


def test_die_bildvorgaben_stehen_im_pruefer():
    """The regression: without this entry the route answers 400."""
    assert bildvorgabenwahl.SCHLUESSEL in PRUEFER
    assert PRUEFER[bildvorgabenwahl.SCHLUESSEL] is bildvorgabenwahl.wahl_pruefen


def test_was_die_tafel_schickt_kommt_auch_an():
    """Exactly the shape Bildserver.svelte sends."""
    geschickt = {
        "breite": 768,
        "hoehe": 768,
        "schritte": 30,
        "sampler": "euler",
        "scheduler": "karras",
    }
    assert bildvorgabenwahl.wahl_pruefen(geschickt) == geschickt


# --- What comes back out --------------------------------------------------


def test_eine_kante_kommt_aufs_raster():
    geprueft = bildvorgabenwahl.wahl_pruefen({"breite": 700})
    assert geprueft["breite"] % RASTER == 0
    assert geprueft["breite"] <= 700


@pytest.mark.parametrize("wert,erwartet", [(99999, MAX_KANTE), (-5, MIN_KANTE), (0, MIN_KANTE)])
def test_eine_kante_ausserhalb_wird_geklemmt(wert, erwartet):
    assert bildvorgabenwahl.wahl_pruefen({"breite": wert})["breite"] == erwartet


def test_schritte_ausserhalb_werden_geklemmt():
    assert bildvorgabenwahl.wahl_pruefen({"schritte": 9999})["schritte"] == MAX_SCHRITTE
    assert bildvorgabenwahl.wahl_pruefen({"schritte": 0})["schritte"] == 1


def test_ein_sampler_den_der_bau_nicht_kennt_faellt_weg():
    assert "sampler" not in bildvorgabenwahl.wahl_pruefen({"sampler": "erfunden"})


def test_leer_heisst_was_das_modell_mitbringt():
    """Not the same as the house default, and a real answer."""
    assert bildvorgabenwahl.wahl_pruefen({"sampler": ""})["sampler"] == ""


def test_fremde_schluessel_kommen_nicht_durch():
    geprueft = bildvorgabenwahl.wahl_pruefen({"breite": 512, "eingeschmuggelt": "x"})
    assert geprueft == {"breite": 512}


@pytest.mark.parametrize("wert", [None, "nein", 5, [], ["breite"]])
def test_was_kein_satz_von_werten_ist_kommt_leer_zurueck(wert):
    assert bildvorgabenwahl.wahl_pruefen(wert) == {}


def test_worte_statt_zahlen_fallen_weg_statt_umzufallen():
    assert bildvorgabenwahl.wahl_pruefen({"breite": "gross", "hoehe": 512}) == {"hoehe": 512}


# --- The defaults themselves ----------------------------------------------


def test_die_vorgabe_haelt_ihre_eigenen_grenzen_ein():
    """A default the route would refuse fails at drawing time, not here."""
    assert bildvorgabenwahl.wahl_pruefen(dict(bildvorgabenwahl.VORGABE)) == {
        k: v for k, v in bildvorgabenwahl.VORGABE.items()
    }


# --- Class-aware defaults -------------------------------------------------


@pytest.mark.parametrize("name,klasse", [
    ("CyberRealisticXL_v5.safetensors", "sdxl"),
    ("Juggernaut-XL.gguf", "sdxl"),
    ("sd_xl_base_1.0.safetensors", "sdxl"),
    ("cyberrealistic_v9.safetensors", "sd15"),
    ("dreamshaper_8.gguf", "sd15"),
    ("", "sd15"),
])
def test_die_klasse_kommt_aus_dem_namen(name, klasse):
    from app.bildwahlen import klasse_aus_name
    assert klasse_aus_name(name) == klasse


def test_sdxl_oeffnet_gross_sd15_klein():
    from app.bildwahlen import vorgabe_fuer_klasse
    assert vorgabe_fuer_klasse("sdxl") == {"breite": 1024, "hoehe": 1024, "schritte": 28}
    assert vorgabe_fuer_klasse("sd15") == {"breite": 512, "hoehe": 512, "schritte": 22}


class _FalscheEinstellungen:
    """A single stored value in the GLOBAL scope, or none."""
    def __init__(self, gespeichert=None):
        self._gespeichert = gespeichert

    def kette(self, schluessel, *, modell=None, chat=None):
        aus = ["global"]
        if modell:
            aus.append(f"m:{modell}")
        if chat:
            aus.append(f"c:{chat}")
        return aus

    def holen(self, bereich, schluessel):
        return self._gespeichert if bereich == "global" else None

    def zusammengefuehrt(self, schluessel, *, vorgabe, modell=None, chat=None):
        if self._gespeichert is None:
            return vorgabe
        return {**vorgabe, **self._gespeichert}


class _FalscheRepos:
    def __init__(self, gespeichert=None):
        self.einstellungen = _FalscheEinstellungen(gespeichert)


def test_ein_sdxl_modell_bekommt_die_grosse_vorgabe():
    v = bildvorgabenwahl.vorgaben(_FalscheRepos(), modell="CyberRealisticXL.safetensors")
    assert (v["breite"], v["hoehe"], v["schritte"]) == (1024, 1024, 28)


def test_ein_sd15_modell_bekommt_die_kleine_vorgabe():
    v = bildvorgabenwahl.vorgaben(_FalscheRepos(), modell="dreamshaper_8.gguf")
    assert (v["breite"], v["hoehe"], v["schritte"]) == (512, 512, 22)


def test_ohne_modell_gilt_die_klassenfreie_basis():
    v = bildvorgabenwahl.vorgaben(_FalscheRepos(), modell=None)
    assert (v["breite"], v["hoehe"], v["schritte"]) == (512, 512, 22)


def test_eine_globale_breite_wird_fuer_die_klasse_ignoriert():
    """A global resolution cannot be right for both classes, so the class base
    holds — the per-model case that DOES win is tested further down."""
    v = bildvorgabenwahl.vorgaben(
        _FalscheRepos(gespeichert={"breite": 768}), modell="CyberRealisticXL.safetensors"
    )
    assert v["breite"] == 1024
    assert v["hoehe"] == 1024


class _GeschichteteEinstellungen:
    """Layers by scope, so global and per-model can differ — the real cascade."""
    def __init__(self, je_bereich):
        self._je_bereich = je_bereich  # {bereich: dict}

    def kette(self, schluessel, *, modell=None, chat=None):
        aus = ["global"]
        if modell:
            aus.append(f"modell:{modell}")
        if chat:
            aus.append(f"chat:{chat}")
        return aus

    def holen(self, bereich, schluessel):
        return self._je_bereich.get(bereich)

    def zusammengefuehrt(self, schluessel, *, vorgabe, modell=None, chat=None):
        zusammen = dict(vorgabe)
        for bereich in self.kette(schluessel, modell=modell, chat=chat):
            g = self._je_bereich.get(bereich)
            if isinstance(g, dict):
                zusammen.update(g)
        return zusammen


class _GeschichteteRepos:
    def __init__(self, je_bereich):
        self.einstellungen = _GeschichteteEinstellungen(je_bereich)


def test_die_globale_altlast_schlaegt_die_klasse_NICHT():
    """The regression this fix exists for: a leftover global 512/12 from the
    single-default era must not defeat the class-aware SDXL default."""
    repos = _GeschichteteRepos({"global": {"breite": 512, "hoehe": 512, "schritte": 12}})
    v = bildvorgabenwahl.vorgaben(repos, modell="CyberRealisticXL.safetensors")
    assert (v["breite"], v["hoehe"], v["schritte"]) == (1024, 1024, 28)


def test_ein_globaler_sampler_gilt_weiterhin():
    """Sampler is class-independent — a global choice still applies."""
    repos = _GeschichteteRepos({"global": {"sampler": "dpm++2m", "breite": 512}})
    v = bildvorgabenwahl.vorgaben(repos, modell="CyberRealisticXL.safetensors")
    assert v["sampler"] == "dpm++2m"
    assert v["breite"] == 1024  # but the global resolution is ignored


def test_ein_pro_modell_wert_darf_die_klasse_setzen():
    """A per-model resolution IS intentional and wins over the class base."""
    repos = _GeschichteteRepos({
        "global": {"breite": 512},
        "modell:CyberRealisticXL.safetensors": {"breite": 768},
    })
    v = bildvorgabenwahl.vorgaben(repos, modell="CyberRealisticXL.safetensors")
    assert v["breite"] == 768


@pytest.mark.parametrize("name", ["ponyDiffusionV6.safetensors", "Illustrious-XL.gguf",
                                   "noobaiXL.safetensors", "animagine_v3.safetensors"])
def test_sdxl_ableger_ohne_xl_werden_erkannt(name):
    from app.bildwahlen import klasse_aus_name
    assert klasse_aus_name(name) == "sdxl"
