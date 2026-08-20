"""What the shipped generator can be told to do.

Two lists and two defaults, copied from ``sd-cli --help`` of the binary that
actually ships — not from memory and not from another project's
documentation. A sampler this build does not know is refused by the program
with a usage message, which reaches the user as "the picture could not be
drawn" and explains nothing.

They live here rather than in the API module because they are a fact about
the generator, not about the route: the window offers them, the route checks
against them, and both read the same list.

Kept as plain tuples so the order is the order the window shows. It follows
the program's own help text, which puts the ones people reach for first.
"""

from __future__ import annotations

# --sampling-method
SAMPLER = (
    "euler_a",
    "euler",
    "heun",
    "dpm2",
    "dpm++2s_a",
    "dpm++2m",
    "dpm++2mv2",
    "dpm++2m_sde",
    "dpm++2m_sde_bt",
    "ipndm",
    "ipndm_v",
    "lcm",
    "ddim_trailing",
    "tcd",
    "res_multistep",
    "res_2s",
    "er_sde",
    "euler_cfg_pp",
    "euler_a_cfg_pp",
    "lms",
)
# What the program itself falls back to for models of the SD-1.5 class.
SAMPLER_VORGABE = "euler_a"

# --scheduler. "normal" is the program's alias for discrete; only the real
# name is offered, so what the window shows is what the command line gets.
SCHEDULER = (
    "karras",
    "discrete",
    "exponential",
    "ays",
    "gits",
    "smoothstep",
    "sgm_uniform",
    "simple",
    "kl_optimal",
    "lcm",
    "bong_tangent",
    "ltx2",
    "logit_normal",
    "flux2",
    "flux",
    "beta",
)
SCHEDULER_VORGABE = "karras"

# How much of the init image is painted over. 1.0 means: ignore it entirely,
# which is what a picture made from nothing does — so it is also the value
# that applies when no init image was chosen at all.
STAERKE_VORGABE = 1.0

# What a LoRA is applied with when no strength was set.
LORA_VORGABE = 0.70

# The folder the LoRA files live in, below the image models.
LORA_ORDNER = "lora"

# The folder the textual-inversion embeddings live in, below the image
# models. An embedding is called by its file name inside the prompt.
EMBEDDING_ORDNER = "embedding"

# How large a picture may be asked for, and in what step. The generator works
# on a grid; an edge between the steps is rounded down rather than refused,
# because a number typed into a field passes through every value on its way
# to the intended one.
#
# They live beside the sampler lists for the same reason those do: the window
# offers them, the route checks against them, and the stored defaults are
# checked against them too — one fact, read from one place.
MIN_KANTE = 256
MAX_KANTE = 1536
RASTER = 64
MIN_SCHRITTE = 1
MAX_SCHRITTE = 80

# The two model classes this build draws with, and what each is BUILT for.
# An SDXL model asked to draw at 512×512 gives a muddy, half-formed picture —
# it was trained at 1024 and only makes sense there; an SD-1.5 model pushed to
# 1024 doubles faces and limbs. One default for both is what made every SDXL
# picture here look worse than the same model in another program: it was drawn
# at a third of the resolution it needs.
KLASSE_SD15 = "sd15"
KLASSE_SDXL = "sdxl"

# The starting values per class — resolution the class was trained at, and
# enough steps that the picture is finished rather than still noisy. These are
# STARTING points a control opens on, never a limit: the window can move them.
VORGABE_JE_KLASSE = {
    KLASSE_SD15: {"breite": 512, "hoehe": 512, "schritte": 22},
    KLASSE_SDXL: {"breite": 1024, "hoehe": 1024, "schritte": 28},
}


# Names that mean SDXL without carrying "xl" — the big SDXL-derived families
# people download most. A catalogue card states the class outright and is the
# real authority; this list only helps a file dropped in by hand.
SDXL_NAMEN = ("xl", "pony", "illustrious", "noob", "animagine")


def klasse_aus_name(name: str) -> str:
    """Guess a model's class from its file name — SDXL or SD 1.5.

    A heuristic, and named as one: the file itself does not say its class
    without being loaded, so the name is what we have for a hand-placed file.
    Most SDXL builds carry "xl" (CyberRealisticXL, Juggernaut-XL, sd_xl_base),
    and the big SDXL-derived families that do not (Pony, Illustrious, NoobAI,
    Animagine) are named here; anything else is treated as SD 1.5, the smaller
    and safer default. A catalogue card states the class outright and overrides
    this — this is only the fallback for a file dropped in by hand.
    """
    klein = (name or "").lower()
    return KLASSE_SDXL if any(wort in klein for wort in SDXL_NAMEN) else KLASSE_SD15


def vorgabe_fuer_klasse(klasse: str) -> dict[str, int]:
    """The starting resolution and steps a class opens on."""
    return dict(VORGABE_JE_KLASSE.get(klasse, VORGABE_JE_KLASSE[KLASSE_SD15]))


def kante_pruefen(wert: object) -> int | None:
    """One edge of the picture, clamped onto the grid, or None if it is not a number."""
    try:
        zahl = int(wert)
    except (TypeError, ValueError):
        return None
    geklemmt = max(MIN_KANTE, min(MAX_KANTE, zahl))
    return geklemmt - (geklemmt % RASTER)


def schritte_pruefen(wert: object) -> int | None:
    """How many steps are drawn, clamped, or None if it is not a number."""
    try:
        zahl = int(wert)
    except (TypeError, ValueError):
        return None
    return max(MIN_SCHRITTE, min(MAX_SCHRITTE, zahl))


def sampler_pruefen(wert: str | None) -> str:
    return wert if wert in SAMPLER else SAMPLER_VORGABE


def scheduler_pruefen(wert: str | None) -> str:
    return wert if wert in SCHEDULER else SCHEDULER_VORGABE
