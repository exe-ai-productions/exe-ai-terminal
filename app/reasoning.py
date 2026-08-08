"""Separate the chain of thought from the actual answer text.

Models deliver their chain of thought in three different formats. The
frontend should not have to know about any of this — here every stream is
split into the same two kinds: ``content`` and ``reasoning``.

    native   The server delivers its own field ``delta.reasoning``
             (Gemma 4). Then there is nothing to do here, the provider
             already separates it.
    harmony  Markers in the text: <|channel|>analysis<|message|> … <|end|>
             (GPT-OSS).
    think    <think> … </think> (Magistral, Qwen, DeepSeek-R1).

The parser works chunk by chunk, because during streaming a marker can be
torn apart between two packets. A text ending that could be the start of a
marker is therefore held back until it is clear what it becomes.
"""

from __future__ import annotations

from typing import Iterable, Literal

Sorte = Literal["content", "reasoning"]

# Marker -> state afterwards. "drop" means: discard the text (control
# plumbing of the format that is neither answer nor chain of thought).
_MARKER: dict[str, list[tuple[str, str]]] = {
    "think": [
        ("<think>", "reasoning"),
        ("</think>", "content"),
    ],
    "harmony": [
        ("<|channel|>analysis<|message|>", "reasoning"),
        ("<|channel|>commentary<|message|>", "reasoning"),
        ("<|channel|>final<|message|>", "content"),
        ("<|end|>", "drop"),
        ("<|return|>", "drop"),
        ("<|start|>", "drop"),
    ],
}


class ReasoningParser:
    """Splits a text stream into answer and chain of thought."""

    def __init__(self, format: str = "none") -> None:
        self.format = format if format in _MARKER else "none"
        self._marker = _MARKER.get(self.format, [])
        self._max_marker = max((len(m) for m, _ in self._marker), default=0)
        self._zustand: str = "content"
        self._rest = ""

    # --- public interface ------------------------------------------------

    def feed(self, text: str) -> list[tuple[Sorte, str]]:
        """Accepts one chunk and returns finished pieces."""
        if not text:
            return []
        if self.format == "none":
            return [("content", text)]

        self._rest += text
        return self._verarbeiten(halte_rest_zurueck=True)

    def finish(self) -> list[tuple[Sorte, str]]:
        """At the end of the stream: emit everything held back."""
        if self.format == "none" or not self._rest:
            rest, self._rest = self._rest, ""
            return [("content", rest)] if rest and self.format == "none" else []
        return self._verarbeiten(halte_rest_zurueck=False)

    # --- Internals -------------------------------------------------------

    def _verarbeiten(self, *, halte_rest_zurueck: bool) -> list[tuple[Sorte, str]]:
        stuecke: list[tuple[Sorte, str]] = []

        while True:
            treffer_position = -1
            treffer_marker = ""
            treffer_zustand = ""
            for marker, zustand in self._marker:
                position = self._rest.find(marker)
                if position != -1 and (treffer_position == -1 or position < treffer_position):
                    treffer_position, treffer_marker, treffer_zustand = position, marker, zustand

            if treffer_position == -1:
                break

            self._ausgeben(stuecke, self._rest[:treffer_position])
            self._rest = self._rest[treffer_position + len(treffer_marker) :]
            self._zustand = treffer_zustand

        if halte_rest_zurueck:
            behalten = self._zurueckzuhalten(self._rest)
            if behalten:
                self._ausgeben(stuecke, self._rest[:-behalten])
                self._rest = self._rest[-behalten:]
            else:
                self._ausgeben(stuecke, self._rest)
                self._rest = ""
        else:
            self._ausgeben(stuecke, self._rest)
            self._rest = ""

        return _zusammenfassen(stuecke)

    def _ausgeben(self, stuecke: list[tuple[Sorte, str]], text: str) -> None:
        if text and self._zustand in ("content", "reasoning"):
            stuecke.append((self._zustand, text))  # type: ignore[arg-type]

    def _zurueckzuhalten(self, text: str) -> int:
        """How many characters at the end could be the start of a marker?"""
        grenze = min(len(text), self._max_marker - 1)
        for laenge in range(grenze, 0, -1):
            schwanz = text[-laenge:]
            if any(marker.startswith(schwanz) for marker, _ in self._marker):
                return laenge
        return 0


def _zusammenfassen(stuecke: Iterable[tuple[Sorte, str]]) -> list[tuple[Sorte, str]]:
    """Merge consecutive pieces of the same kind."""
    ergebnis: list[tuple[Sorte, str]] = []
    for sorte, text in stuecke:
        if ergebnis and ergebnis[-1][0] == sorte:
            ergebnis[-1] = (sorte, ergebnis[-1][1] + text)
        else:
            ergebnis.append((sorte, text))
    return ergebnis


def trennen(text: str, format: str) -> tuple[str, str]:
    """Convenient route for complete text: returns (answer, chain of thought)."""
    parser = ReasoningParser(format)
    stuecke = parser.feed(text) + parser.finish()
    antwort = "".join(t for sorte, t in stuecke if sorte == "content")
    gedanke = "".join(t for sorte, t in stuecke if sorte == "reasoning")
    return antwort, gedanke
