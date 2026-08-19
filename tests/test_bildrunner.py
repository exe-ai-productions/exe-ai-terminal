"""The offline image generator: its guards, not its pictures.

What is worth testing here is everything AROUND the drawing — a model name
that is really a path, two runs asking for the machine at once, a request
whose numbers would tie the machine up for an hour. The picture itself is
the generator's business and is proved by running it, not by asserting
about pixels.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from app import bildrunner, bildspeicher, bildwahlen
from app.api.v1.bild import MAX_KANTE, MAX_SCHRITTE, MIN_KANTE, RASTER, _kante
from app.bildrunner import Auftrag, BildFehler, Bildrunner


@pytest.fixture
def daten(tmp_path: Path) -> Path:
    """The image model folder itself — the folder IS the kind now."""
    (tmp_path / "klein.gguf").write_bytes(b"x")
    (tmp_path / "notiz.txt").write_text("kein Modell")
    return tmp_path


def test_nur_dateien_aus_dem_bildmodell_ordner_zaehlen(daten: Path):
    assert bildrunner.modelle(daten) == ["klein.gguf"]


def test_ein_modellname_ist_nie_ein_pfad(daten: Path):
    """The one place where guessing would be dangerous, so it refuses."""
    for versuch in ("../../etc/passwd", "unterordner/klein.gguf", "", "gibtsnicht.gguf"):
        with pytest.raises(BildFehler) as fehler:
            bildrunner.modell_pfad(daten, versuch)
        assert fehler.value.grund == "bild.modell_unbekannt"


def test_ein_bekannter_name_wird_zum_pfad(daten: Path):
    pfad = bildrunner.modell_pfad(daten, "klein.gguf")
    assert pfad == daten / "klein.gguf"


def test_ohne_programm_gibt_es_keinen_befehl(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: None)
    runner = Bildrunner(daten)
    assert runner.programm is None
    with pytest.raises(BildFehler) as fehler:
        runner.befehl(Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "aus.png")
    assert fehler.value.grund == "bild.kein_programm"


def test_der_befehl_traegt_alles_was_gesetzt_wurde(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    runner = Bildrunner(daten)
    befehl = runner.befehl(
        Auftrag(
            modell=daten / "klein.gguf", prompt="ein Leuchtturm", negativ="unscharf",
            breite=512, hoehe=768, schritte=14, cfg=6.5, seed=42,
        ),
        daten / "aus.png",
    )
    assert befehl[0] == "/irgendwo/sd-cli"
    for marke in ("-p", "ein Leuchtturm", "--negative-prompt", "unscharf",
                  "-W", "512", "-H", "768", "--steps", "14", "--seed", "42"):
        assert marke in befehl


def test_ohne_negativ_faellt_die_option_weg(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "aus.png"
    )
    assert "--negative-prompt" not in befehl


def test_zwei_laeufe_gleichzeitig_gibt_es_nicht(daten: Path, monkeypatch):
    """The lock is not about the program — it is about the memory pool."""
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    runner = Bildrunner(daten)
    drin = threading.Event()
    weiter = threading.Event()

    class Strom:
        """An exhausted pipe — the runner's readers stop at once."""

        def read(self, n=-1):
            return ""

    class Prozess:
        """A generator that takes its time and can be asked to stop."""

        returncode = 0
        pid = 4242
        stdout = Strom()
        stderr = Strom()

        def wait(self, timeout=None):
            drin.set()
            weiter.wait(5)
            return 0

        def communicate(self, timeout=None):
            drin.set()
            weiter.wait(5)
            return ("", "")

        def poll(self):
            return None

    monkeypatch.setattr(bildrunner.subprocess, "Popen", lambda *a, **k: Prozess())
    ziel = daten / "aus.png"
    ziel.write_bytes(b"png")
    auftrag = Auftrag(modell=daten / "klein.gguf", prompt="x")

    faden = threading.Thread(target=lambda: runner.erzeugen(auftrag, ziel))
    faden.start()
    assert drin.wait(5)
    with pytest.raises(BildFehler) as fehler:
        runner.erzeugen(auftrag, ziel)
    assert fehler.value.grund == "bild.laeuft_schon"
    weiter.set()
    faden.join(5)
    # And free again afterwards, or one failed picture would block the rest
    # of the evening.
    assert runner.laeuft() is False


def test_sampler_und_scheduler_stehen_im_befehl(daten: Path, monkeypatch):
    """Both come from the shipped binary's own list.

    A name this build does not know is answered with a usage message, which
    reaches the user as "the picture could not be drawn" and explains
    nothing — so anything unknown is brought back to the default instead.
    """
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(
            modell=daten / "klein.gguf", prompt="x",
            sampler="dpm++2m", scheduler="exponential",
        ),
        daten / "aus.png",
    )
    assert "--sampling-method" in befehl and "dpm++2m" in befehl
    assert "--scheduler" in befehl and "exponential" in befehl
    assert bildwahlen.sampler_pruefen("gibtsnicht") == bildwahlen.SAMPLER_VORGABE
    assert bildwahlen.scheduler_pruefen(None) == bildwahlen.SCHEDULER_VORGABE
    assert bildwahlen.sampler_pruefen("heun") == "heun"


def test_der_lora_stapel_wandert_in_den_prompt(daten: Path, monkeypatch):
    """sd.cpp has no LoRA option — it reads them out of the prompt."""
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(
            modell=daten / "klein.gguf",
            prompt="ein Leuchtturm",
            loras=(
                bildrunner.LoRA(name="stil.safetensors", staerke=0.7),
                bildrunner.LoRA(name="licht.safetensors", staerke=0.4),
            ),
            lora_ordner=daten / "lora",
        ),
        daten / "aus.png",
    )
    prompt = befehl[befehl.index("-p") + 1]
    # In the order they were stacked — that order is what applies.
    assert prompt == "ein Leuchtturm <lora:stil:0.7> <lora:licht:0.4>"
    assert "--lora-model-dir" in befehl


def test_eine_lora_ist_nie_ein_pfad(daten: Path):
    (daten / "lora").mkdir()
    (daten / "lora" / "stil.safetensors").write_bytes(b"x")
    assert bildrunner.loras(daten) == ["stil.safetensors"]
    assert bildrunner.lora_pfad(daten, "stil.safetensors").name == "stil.safetensors"
    for versuch in ("../klein.gguf", "unter/stil.safetensors", "", "gibtsnicht.safetensors"):
        with pytest.raises(BildFehler) as fehler:
            bildrunner.lora_pfad(daten, versuch)
        assert fehler.value.grund == "bild.lora_unbekannt"


def test_die_staerke_reist_nur_neben_einem_startbild(daten: Path, monkeypatch):
    """A control that does nothing is worse than no control."""
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    runner = Bildrunner(daten)
    ohne = runner.befehl(Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "a.png")
    assert "--strength" not in ohne and "-i" not in ohne
    mit = runner.befehl(
        Auftrag(
            modell=daten / "klein.gguf", prompt="x",
            startbild=daten / "start.png", staerke=0.6,
        ),
        daten / "a.png",
    )
    assert "-i" in mit and "--strength" in mit and "0.6" in mit


def test_die_maske_reist_nur_neben_einem_startbild(daten: Path, monkeypatch):
    """A mask without a picture to mask has nothing to say.

    Passed anyway it would be an argument the program either ignores or
    stumbles over, and the command line would stop describing what actually
    happens.
    """
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    runner = Bildrunner(daten)
    ohne = runner.befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x", maske=daten / "m.png"),
        daten / "a.png",
    )
    assert "--mask" not in ohne
    mit = runner.befehl(
        Auftrag(
            modell=daten / "klein.gguf", prompt="x",
            startbild=daten / "start.png", staerke=0.7, maske=daten / "m.png",
        ),
        daten / "a.png",
    )
    assert "--mask" in mit and str(daten / "m.png") in mit


def test_die_vorgabe_ist_das_mass_des_erstmodells():
    """512 is what the first model was trained on."""
    auftrag = Auftrag(modell=Path("/m.gguf"), prompt="x")
    assert (auftrag.breite, auftrag.hoehe) == (512, 512)


def test_die_kanten_werden_geklemmt_und_aufs_raster_gelegt():
    assert _kante(99999) == MAX_KANTE
    assert _kante(1) == MIN_KANTE
    assert _kante(769) == 768
    assert _kante(1000) % RASTER == 0
    assert MAX_SCHRITTE == 80


def test_der_speicher_wird_vor_dem_lauf_gefragt():
    # 64 GB machine, 8 GB held by the language model, a 2 GB image model:
    # room enough.
    assert bildspeicher.passt(64, 8, 2) is True
    # 16 GB machine, 12 GB held, a 2 GB image model: it would swap.
    assert bildspeicher.passt(16, 12, 2) is False
    assert bildspeicher.fehlend_gb(16, 12, 2) > 0
    # A machine whose memory cannot be read must not block the feature.
    assert bildspeicher.passt(None, 99, 99) is True
    assert bildspeicher.fehlend_gb(None, 99, 99) == 0.0


class Runner:
    """Something that holds a model and can say how much."""

    def __init__(self, gb):
        self._gb = gb

    def belegt_gb(self):
        return self._gb


class Zustand:
    """Stands in for the application state, which is a bag of attributes."""

    def __init__(self, **dinge):
        self.__dict__.update(dinge)


def test_alle_laufenden_server_zaehlen_mit():
    """Asking one of several is worse than not asking at all.

    Three servers may hold a model at once. Counting only the first turns a
    machine that is already full into a machine that says yes.
    """
    zustand = Zustand(
        modellrunner=Runner(4.0),
        einbettungsrunner=Runner(6.0),
        eewrunner=Runner(2.5),
    )
    assert bildspeicher.gehaltene_gb(zustand) == 12.5
    # 16 GB machine, a 2 GB image model. Asking only the chat model finds
    # 4 + 2 + 2.5 = 8.5 and waves it through; the truth is 12.5 + 2 + 2.5,
    # which is a gigabyte more than the machine has.
    assert bildspeicher.passt(16, 4.0, 2.0) is True
    assert bildspeicher.passt(16, bildspeicher.gehaltene_gb(zustand), 2.0) is False


def test_wer_nichts_haelt_zaehlt_nichts():
    """An idle server answers nothing, and nothing is not a number."""
    zustand = Zustand(modellrunner=Runner(None), einbettungsrunner=Runner(0.0))
    assert bildspeicher.gehaltene_gb(zustand) == 0.0


def test_was_kein_server_ist_wird_uebergangen():
    """The sum is collected by asking, so the bag may hold anything.

    That is what keeps a fifth server from being forgotten: nothing has to
    be added to a list when one appears.
    """
    zustand = Zustand(
        modellrunner=Runner(4.0),
        bildrunner=object(),
        werkzeuge=[1, 2, 3],
        config="irgendwas",
    )
    assert bildspeicher.gehaltene_gb(zustand) == 4.0


def test_ein_neuer_server_wird_von_selbst_mitgezaehlt():
    zustand = Zustand(modellrunner=Runner(4.0))
    assert bildspeicher.gehaltene_gb(zustand) == 4.0
    zustand.nochwas_runner = Runner(3.0)
    assert bildspeicher.gehaltene_gb(zustand) == 7.0


def test_der_zustand_einer_anwendung_wird_gelesen():
    """Starlette keeps its state in an inner dictionary, not in `__dict__`."""
    from starlette.datastructures import State

    zustand = State()
    zustand.modellrunner = Runner(4.0)
    zustand.eewrunner = Runner(2.0)
    assert bildspeicher.gehaltene_gb(zustand) == 6.0


# --- The quality companions (block D) -------------------------------------


def test_flash_attention_ist_an_seit_gemessen(daten: Path, monkeypatch):
    """On by default now that it is measured on the shipped build: the highres
    fix's second pass drops from ~30 s to ~3.5 s per step with it. It can still
    be switched off explicitly for a swapped-in binary that does not know the
    flag."""
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    an = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "a.png"
    )
    assert "--diffusion-fa" in an
    aus = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x", diffusion_fa=False), daten / "a.png"
    )
    assert "--diffusion-fa" not in aus


def test_die_begleiter_fallen_weg_wenn_ungesetzt(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "a.png"
    )
    for weg in ("--clip-skip", "--vae", "--ad-model", "--ad-prompt"):
        assert weg not in befehl


def test_clip_skip_reist_nur_wenn_gesetzt(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    runner = Bildrunner(daten)
    aus = runner.befehl(Auftrag(modell=daten / "klein.gguf", prompt="x", clip_skip=-1), daten / "a.png")
    assert "--clip-skip" not in aus
    an = runner.befehl(Auftrag(modell=daten / "klein.gguf", prompt="x", clip_skip=2), daten / "a.png")
    assert "--clip-skip" in an and "2" in an


def test_vae_und_detektor_stehen_im_befehl(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(
            modell=daten / "klein.gguf", prompt="x",
            vae=daten / "vae" / "besser.safetensors",
            ad_modell=daten / "adetailer" / "face.pt", ad_prompt="detailed face",
        ),
        daten / "a.png",
    )
    assert "--vae" in befehl and str(daten / "vae" / "besser.safetensors") in befehl
    assert "--ad-model" in befehl and str(daten / "adetailer" / "face.pt") in befehl
    assert "--ad-prompt" in befehl and "detailed face" in befehl


def test_ad_prompt_faellt_ohne_detektor_weg(daten: Path, monkeypatch):
    """A face prompt without a detector has nothing to steer."""
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x", ad_prompt="face"),
        daten / "a.png",
    )
    assert "--ad-prompt" not in befehl


def test_vae_und_yolo_liegen_in_eigenen_ordnern(daten: Path):
    (daten / "vae").mkdir()
    (daten / "vae" / "besser.safetensors").write_bytes(b"x")
    (daten / "adetailer").mkdir()
    (daten / "adetailer" / "face.pt").write_bytes(b"x")
    assert bildrunner.vaes(daten) == ["besser.safetensors"]
    assert bildrunner.yolos(daten) == ["face.pt"]
    assert bildrunner.vae_pfad(daten, "besser.safetensors").name == "besser.safetensors"
    assert bildrunner.yolo_pfad(daten, "face.pt").name == "face.pt"


def test_ein_begleiter_ist_nie_ein_pfad(daten: Path):
    (daten / "vae").mkdir()
    (daten / "vae" / "besser.safetensors").write_bytes(b"x")
    for versuch in ("../klein.gguf", "unter/besser.safetensors", "", "gibtsnicht.safetensors"):
        with pytest.raises(BildFehler) as fehler:
            bildrunner.vae_pfad(daten, versuch)
        assert fehler.value.grund == "bild.begleiter_unbekannt"


def test_hires_fix_faellt_ohne_schalter_weg(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "a.png"
    )
    assert "--hires" not in befehl and "--hires-scale" not in befehl


def test_hires_fix_traegt_massstab_und_schritte(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    befehl = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x", hires=True, hires_scale=2.0, hires_steps=10),
        daten / "a.png",
    )
    assert "--hires" in befehl
    assert "--hires-scale" in befehl and "2.0" in befehl
    assert "--hires-steps" in befehl and "10" in befehl


def test_vae_tiling_ist_stilles_plumbing(daten: Path, monkeypatch):
    monkeypatch.setattr(bildrunner.shutil, "which", lambda _: "/irgendwo/sd-cli")
    aus = Bildrunner(daten).befehl(Auftrag(modell=daten / "klein.gguf", prompt="x"), daten / "a.png")
    assert "--vae-tiling" not in aus
    an = Bildrunner(daten).befehl(
        Auftrag(modell=daten / "klein.gguf", prompt="x", vae_tiling=True), daten / "a.png"
    )
    assert "--vae-tiling" in an
