"""Writing one key into the user's .env file.

Line by line rather than through a parser: the file belongs to the user,
and their comments and order are worth more than a tidy rewrite. The file
serves the next start; whoever needs the value now sets it into the
process environment as well.
"""

from __future__ import annotations

import re
from pathlib import Path


def env_schreiben(datei: Path, name: str, wert: str) -> None:
    zeilen = datei.read_text(encoding="utf-8").splitlines() if datei.exists() else []
    neu, gesetzt = [], False
    for zeile in zeilen:
        if re.match(rf"^\s*#?\s*{re.escape(name)}\s*=", zeile):
            if not gesetzt:
                neu.append(f"{name}={wert}")
                gesetzt = True
            continue
        neu.append(zeile)
    if not gesetzt:
        neu.append(f"{name}={wert}")
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("\n".join(neu).rstrip() + "\n", encoding="utf-8")
    datei.chmod(0o600)
