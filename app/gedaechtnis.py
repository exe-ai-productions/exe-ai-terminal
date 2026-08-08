"""The persistent memory — what the program keeps knowing about its user.

A second prompt file next to ``prompts/system.md``, read fresh on every
request and prepended to the history. Deliberately a file and not a table:
the thing that permanently shapes how the model behaves should be openable in
any editor and readable at a glance. Whoever cannot see what a memory knows
cannot correct it.

Two kinds live in it, under two headings:

    ## Rules
    - Comments and commit messages are English.

    ## Facts
    - Works on a desktop machine, sometimes from a laptop.

The distinction is the only one that does something. A **rule** changes
behaviour and therefore always applies — it must never depend on some
similarity measure deciding it is relevant. A **fact** is knowledge and
applies when it fits; that half is the one that can later be fetched on
demand, once the file outgrows what is worth sending every time.

Whether it travels is TWO switches, ``{"lokal": bool, "cloud": bool}``, and
that is the whole granularity: on the machine, and off it. Per-provider or
per-chat would be finer than anyone wants to operate.

The default is on locally and off in the cloud, because a memory in a system
prompt is sent with EVERY request — on this machine that costs nothing, to a
provider it means a personal profile living on a foreign server permanently.
The switch is there for whoever wants it otherwise; the quiet default is the
careful one.

Not stored as bare booleans on purpose: the settings route treats a falsy
value as "nothing set" and lets the scope above take over, so a plain
``False`` could never switch anything OFF. A two-key object is truthy either
way.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

SCHLUESSEL = "gedaechtnis"

# On here, off out there — until somebody decides otherwise.
VORGABE: dict[str, bool] = {"lokal": True, "cloud": False}

# The headings the file is split by. English like everything in a prompt —
# the entries themselves are written in whatever language the user speaks.
UEBERSCHRIFT_REGELN = "## Rules"
UEBERSCHRIFT_FAKTEN = "## Facts"

# What the model is told before the memory. Without a sentence like this the
# entries read as part of the conversation instead of as standing knowledge.
EINLEITUNG = (
    "What you know about this user from earlier sessions. The rules always "
    "apply; the facts apply where they fit. Do not repeat this back unless "
    "asked."
)


def schalter_pruefen(wert: Any) -> dict[str, bool]:
    """``gedaechtnis``: the two switches, checked before they are stored.

    Only the two known keys survive, and both as real booleans. Whatever else
    somebody sends is dropped rather than stored — a settings column holds
    JSON and cannot check anything by itself.
    """
    if not isinstance(wert, dict):
        return {}
    sauber = {name: bool(wert[name]) for name in VORGABE if name in wert}
    return sauber


def mitschicken(repositories, zustand) -> bool:
    """Whether the memory travels with a request to THIS endpoint."""
    stand = repositories.einstellungen.zusammengefuehrt(
        SCHLUESSEL, vorgabe=dict(VORGABE)
    )
    if not isinstance(stand, dict):
        stand = dict(VORGABE)
    endpunkt = getattr(zustand, "endpunkt", None)
    seite = "lokal" if getattr(endpunkt, "group", None) == "local" else "cloud"
    return bool(stand.get(seite, VORGABE[seite]))


def anhaengen(system_prompt: str, gedaechtnis: str) -> str:
    """Puts prompt and memory into ONE system message.

    One and not two: Anthropic takes a single system field, and providers
    disagree about what a second system message means. Assembling here keeps
    that difference out of everything downstream.

    The file is used as it stands, including its headings — they are what
    tells the model which half always applies.
    """
    gedaechtnis = (gedaechtnis or "").strip()
    if not gedaechtnis:
        return system_prompt
    block = f"{EINLEITUNG}\n\n{gedaechtnis}"
    system_prompt = (system_prompt or "").strip()
    return f"{system_prompt}\n\n{block}" if system_prompt else block
