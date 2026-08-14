"""The handful of engine levers for "the graphics memory is not enough".

llama.cpp has well over a hundred switches. Almost all of them are for
somebody building an engine, not for somebody running a model, and putting
them on a page would bury the five that actually change whether a model fits
on a machine. These five are those, and nothing else goes in here without a
reason a user could state.

Each one is passed only when it differs from what the engine already does.
An explicit flag that repeats the default is a flag that can go wrong later,
when the default moves and the program keeps insisting on the old one.

The names are read off the shipped binary, not remembered: `--mlock` is
deprecated in the build we ship and `--load-mode mlock` is what replaced it.
"""

from __future__ import annotations

from dataclasses import dataclass

# What the KV cache may be stored as. The order is the order they are offered
# in: the engine's own default first, then the two that trade a little
# quality for a lot of room at a large context.
KV_TYPEN = ("f16", "q8_0", "q4_0")
KV_VORGABE = "f16"

# Flash attention is a three-way switch in the engine, and "auto" is what it
# does when nobody says otherwise — so that is our default too.
FA_WERTE = ("auto", "on", "off")
FA_VORGABE = "auto"

# A thread count nobody would type on purpose. Above this the engine is being
# asked to fight itself for cores.
MAX_FAEDEN = 256


@dataclass
class Feineinstellungen:
    """What the advanced section can set. Every field defaults to "leave it"."""

    kv_cache: str = KV_VORGABE
    flash_attention: str = FA_VORGABE
    # None means: let the engine decide, which is what it does best.
    faeden: int | None = None
    # How many layers' worth of Mixture-of-Experts weights stay on the CPU.
    # 0 means none; None means all of them. THE lever for a MoE model on a
    # card that cannot hold it.
    moe_auf_cpu: bool = False
    moe_schichten: int | None = None
    # Keep the model in RAM instead of letting the system swap it out.
    festnageln: bool = False

    @classmethod
    def aus_daten(cls, daten: dict | None) -> "Feineinstellungen":
        """Builds from whatever the window sent, clamped into range.

        A value out of range is not an error to report but a value to bring
        into range — the same rule the picture generator follows. The one
        exception is a name that is not a name: an unknown cache type falls
        back to the default rather than reaching the command line, where the
        engine would refuse to start at all.
        """
        d = daten or {}
        kv = str(d.get("kv_cache") or KV_VORGABE)
        fa = str(d.get("flash_attention") or FA_VORGABE)
        faeden = d.get("faeden")
        try:
            faeden = None if faeden in (None, "", 0) else max(1, min(MAX_FAEDEN, int(faeden)))
        except (TypeError, ValueError):
            faeden = None
        schichten = d.get("moe_schichten")
        try:
            schichten = None if schichten in (None, "") else max(0, int(schichten))
        except (TypeError, ValueError):
            schichten = None
        return cls(
            kv_cache=kv if kv in KV_TYPEN else KV_VORGABE,
            flash_attention=fa if fa in FA_WERTE else FA_VORGABE,
            faeden=faeden,
            moe_auf_cpu=bool(d.get("moe_auf_cpu")),
            moe_schichten=schichten,
            festnageln=bool(d.get("festnageln")),
        )

    def als_daten(self) -> dict:
        return {
            "kv_cache": self.kv_cache,
            "flash_attention": self.flash_attention,
            "faeden": self.faeden,
            "moe_auf_cpu": self.moe_auf_cpu,
            "moe_schichten": self.moe_schichten,
            "festnageln": self.festnageln,
        }


def flags(einstellungen: Feineinstellungen | None) -> list[str]:
    """The command-line words for these settings, defaults left unsaid."""
    if einstellungen is None:
        return []
    zeile: list[str] = []

    # Both halves of the cache together: storing K small and V large saves
    # half of what was asked for and confuses anybody reading the command.
    if einstellungen.kv_cache != KV_VORGABE:
        zeile += ["--cache-type-k", einstellungen.kv_cache,
                  "--cache-type-v", einstellungen.kv_cache]

    if einstellungen.flash_attention != FA_VORGABE:
        zeile += ["--flash-attn", einstellungen.flash_attention]

    if einstellungen.faeden:
        zeile += ["--threads", str(einstellungen.faeden)]

    if einstellungen.moe_auf_cpu:
        # A number means "the first N layers", no number means all of them.
        if einstellungen.moe_schichten:
            zeile += ["--n-cpu-moe", str(einstellungen.moe_schichten)]
        else:
            zeile += ["--cpu-moe"]

    if einstellungen.festnageln:
        # `--mlock` still works but is deprecated in the shipped build; this
        # is the form that build documents.
        zeile += ["--load-mode", "mmap+mlock"]

    return zeile
