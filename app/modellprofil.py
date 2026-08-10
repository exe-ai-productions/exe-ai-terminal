"""Start flags a model family needs to do its best work.

llama-server takes its chat template from the model, but only with
``--jinja`` does it speak the template's tool-call language — without the
flag, tool results reach the model in a shape it was never trained on, and
the usual symptom is a model that talks about calling tools in circles
instead of calling them. The flag is therefore not optional here.

The sampling defaults are family lore published by the model makers. They
are load-bearing: the wrong sampler changes a model's behaviour more than a
quantization step does.
"""

from __future__ import annotations

# Family fingerprint -> the flags its maker recommends for tool work.
# Matched case-insensitively against the model file name; first hit wins.
_PROFILE: list[tuple[str, list[str]]] = [
    ("gemma-4", ["--temp", "1.0", "--top-p", "0.95", "--top-k", "64"]),
    # The default repeat penalty makes this family loop on tool calls.
    (
        "glm-4.7",
        ["--temp", "0.7", "--top-p", "1.0", "--repeat-penalty", "1.0", "--min-p", "0.01"],
    ),
]


def startflags(dateiname: str) -> list[str]:
    """The extra flags for this model file: always ``--jinja``, plus family lore."""
    flags = ["--jinja"]
    klein = dateiname.lower()
    for muster, familie in _PROFILE:
        if muster in klein:
            flags += familie
            break
    return flags
