"""Model parameters — uniformly named, translated per backend.

The backends cannot do the same things and call the same thing by different
names. The repetition penalty is ``repeat_penalty`` in llama.cpp,
``repetition_penalty`` in MLX; ``typical_p`` exists only in llama.cpp,
``logit_bias`` only in MLX.

Hence our own fixed set of names here. Each dialect says which of them it
knows and what it calls them. The frontend queries the list and shows only
knobs that actually do something — a knob that silently grasps at nothing is
worse than no knob at all.

The lists are not guessed: llama.cpp was queried via ``/props``, MLX was
looked up in the source of ``mlx_lm/server.py``.

Deliberately not included: mirostat, DRY, XTC, dynatemp and top_n_sigma. They
are rare, partly work against top_p/top_k, and would clutter the menu.
Whoever needs them adds them here — nothing more is required.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

Gruppe = Literal["sichtbar", "mehr"]


@dataclass(frozen=True)
class Parameter:
    name: str
    label: str
    label_en: str
    hinweis: str
    hinweis_en: str
    minimum: float
    maximum: float
    schritt: float
    gruppe: Gruppe = "mehr"
    ganzzahl: bool = False

    def als_dict(self, sprache: str = "de") -> dict[str, Any]:
        englisch = sprache.startswith("en")
        return {
            "name": self.name,
            "label": self.label_en if englisch else self.label,
            "hinweis": self.hinweis_en if englisch else self.hinweis,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "schritt": self.schritt,
            "gruppe": self.gruppe,
            "ganzzahl": self.ganzzahl,
        }


PARAMETER: list[Parameter] = [
    Parameter("temperature", "Temperatur", "Temperature",
              "Wie frei formuliert wird", "How freely it phrases things",
              0, 2, 0.05, "sichtbar"),
    Parameter("top_p", "Top-P", "Top-P",
              "Wie viel Wortauswahl zugelassen wird", "How much word choice is allowed",
              0, 1, 0.01, "sichtbar"),
    Parameter("max_tokens", "Antwortlänge", "Response length",
              "Höchstzahl an Token", "Maximum number of tokens",
              256, 32768, 256, "sichtbar", ganzzahl=True),

    Parameter("top_k", "Top-K", "Top-K",
              "Nur die besten K Wörter, 0 schaltet es ab", "Only the top K words, 0 disables it",
              0, 200, 1, ganzzahl=True),
    Parameter("min_p", "Min-P", "Min-P",
              "Wirft unwahrscheinliche Wörter weg", "Discards unlikely words",
              0, 1, 0.01),
    Parameter("repeat_penalty", "Wiederholungsbremse", "Repetition penalty",
              "1,0 heißt aus", "1.0 means off",
              1, 2, 0.01),
    Parameter("repeat_last_n", "Bremse wirkt auf", "Penalty window",
              "Wie viele Token zurück geschaut wird", "How many tokens back it looks",
              0, 2048, 16, ganzzahl=True),
    Parameter("presence_penalty", "Themenwechsel", "Presence penalty",
              "Höher heißt: eher etwas Neues ansprechen", "Higher means: bring up new things",
              -2, 2, 0.05),
    Parameter("frequency_penalty", "Wortwiederholung", "Frequency penalty",
              "Höher heißt: seltener dasselbe Wort", "Higher means: repeat words less",
              -2, 2, 0.05),
    Parameter("typical_p", "Typical-P", "Typical-P",
              "Bevorzugt erwartbare Formulierungen", "Prefers expected phrasing",
              0, 1, 0.01),
    Parameter("seed", "Startwert", "Seed",
              "Gleicher Wert, gleiche Antwort. -1 heißt zufällig", "Same value, same answer. -1 is random",
              -1, 2147483647, 1, ganzzahl=True),
]

NACH_NAME: dict[str, Parameter] = {p.name: p for p in PARAMETER}


# Which dialect knows which parameter — and under what name.
# If an entry is missing, the parameter is neither offered nor sent along
# for that backend.
DIALEKTE: dict[str, dict[str, str]] = {
    # llama.cpp (llama-server), queried via /props
    "llama_cpp": {
        "temperature": "temperature",
        "top_p": "top_p",
        "max_tokens": "max_tokens",
        "top_k": "top_k",
        "min_p": "min_p",
        "repeat_penalty": "repeat_penalty",
        "repeat_last_n": "repeat_last_n",
        "presence_penalty": "presence_penalty",
        "frequency_penalty": "frequency_penalty",
        "typical_p": "typical_p",
        "seed": "seed",
    },
    # mlx_lm.server, looked up in mlx_lm/server.py
    "mlx": {
        "temperature": "temperature",
        "top_p": "top_p",
        "max_tokens": "max_tokens",
        "top_k": "top_k",
        "min_p": "min_p",
        "repeat_penalty": "repetition_penalty",
        "repeat_last_n": "repetition_context_size",
        "presence_penalty": "presence_penalty",
        "frequency_penalty": "frequency_penalty",
        "seed": "seed",
    },
    # Lowest common denominator of the cloud providers.
    "openai": {
        "temperature": "temperature",
        "top_p": "top_p",
        "max_tokens": "max_tokens",
        "presence_penalty": "presence_penalty",
        "frequency_penalty": "frequency_penalty",
        "seed": "seed",
    },
    # Anthropic's Messages API. Deliberately short: it knows neither the two
    # penalties nor a seed, so those knobs are not offered — a knob that
    # silently grasps at nothing is worse than no knob at all.
    "anthropic": {
        "temperature": "temperature",
        "top_p": "top_p",
        "top_k": "top_k",
        "max_tokens": "max_tokens",
    },
}


# Where a dialect's range differs from the general one. Anthropic caps the
# temperature at 1.0 and rejects anything above with an error — a slider
# running to 2 would offer a setting that cannot be sent.
GRENZEN: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {"temperature": (0, 1)},
}


def unterstuetzte(dialekt: str) -> list[Parameter]:
    """All parameters this dialect knows — in the order from above.

    With the dialect's own range where it has one, so the control offers
    exactly what the backend accepts.
    """
    bekannt = DIALEKTE.get(dialekt) or DIALEKTE["openai"]
    grenzen = GRENZEN.get(dialekt) or {}
    raus: list[Parameter] = []
    for p in PARAMETER:
        if p.name not in bekannt:
            continue
        if p.name in grenzen:
            minimum, maximum = grenzen[p.name]
            p = replace(p, minimum=minimum, maximum=maximum)
        raus.append(p)
    return raus


def uebersetzen(dialekt: str, werte: dict[str, Any]) -> dict[str, Any]:
    """Converts our names into the backend's.

    What the dialect does not know is dropped — better to leave a parameter
    out than to send one the server rejects as an error.
    """
    bekannt = DIALEKTE.get(dialekt) or DIALEKTE["openai"]
    ergebnis: dict[str, Any] = {}
    for name, wert in werte.items():
        if wert is None or name not in bekannt:
            continue
        eintrag = NACH_NAME.get(name)
        if eintrag and eintrag.ganzzahl:
            wert = int(wert)
        ergebnis[bekannt[name]] = wert
    return ergebnis


def pruefen(werte: dict[str, Any]) -> dict[str, Any]:
    """Clamps values to their allowed range, discards anything unknown."""
    sauber: dict[str, Any] = {}
    for name, wert in (werte or {}).items():
        eintrag = NACH_NAME.get(name)
        if eintrag is None or wert is None:
            continue
        try:
            zahl = float(wert)
        except (TypeError, ValueError):
            continue
        zahl = max(eintrag.minimum, min(eintrag.maximum, zahl))
        sauber[name] = int(zahl) if eintrag.ganzzahl else zahl
    return sauber
