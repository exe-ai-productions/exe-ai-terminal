"""Small text utilities for model ids that look like file paths.

Servers without a HuggingFace cache (e.g. ``mlx_vlm.server`` with a locally
loaded model) sometimes report their model only under the full file path,
not under a meaningful name. Two separate questions arise from this:

* Is the id a path? (``ist_pfad``, used by discovery when sorting things in
  and by the OpenAI-compatible provider when parsing ``/v1/models``.)
* How do you show a path to a person without revealing the local user name
  and the folder structure? (``pfad_zu_anzeigename``, UI only — the server
  itself always gets the full, unchanged id, see
  ``EndpunktZustand.gemeldeter_name`` in ``discovery.py``.)
"""

from __future__ import annotations

import re


def ist_pfad(kennung: str) -> bool:
    """Does this look like a file path rather than a model name?

    A leading slash, a drive letter, or a piece of HuggingFace cache in the
    text. A mere slash is NOT enough: "zecanard/gemma-4-26B" is a perfectly
    normal model name.
    """
    if kennung.startswith(("/", "~", "\\")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", kennung):
        return True
    return "/snapshots/" in kennung or "huggingface/hub" in kennung


def pfad_zu_anzeigename(pfad: str) -> str:
    """Last path segment as display name — hides the private folder trail.

    ``/Users/you/models/Qwen3.6-27B-MLX-8bit`` becomes
    ``Qwen3.6-27B-MLX-8bit``. Important for the beta UI: the full path
    reveals the local user name and the folder structure, the last segment
    is just the model name.
    """
    bereinigt = pfad.replace("\\", "/").rstrip("/")
    return bereinigt.rsplit("/", 1)[-1] or pfad
