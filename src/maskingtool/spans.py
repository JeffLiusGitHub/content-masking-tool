"""TextSpan: the unit shared by all format parsers.

Every input format (MD/DOCX/PDF) is flattened into a list of TextSpans.
`start`/`end` are offsets into the combined plain-text string that the
Presidio analyzer runs over once; `source_ref` is whatever the parser
needs to find its way back into the original document structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextSpan:
    text: str
    start: int
    end: int
    source_ref: Any = None

    def __post_init__(self) -> None:
        if self.end - self.start != len(self.text):
            raise ValueError(
                f"span length mismatch: [{self.start},{self.end}) vs {len(self.text)} chars"
            )


@dataclass
class SpannedText:
    """A combined plain-text string plus the spans it was built from."""

    text: str
    spans: list[TextSpan] = field(default_factory=list)

    @classmethod
    def from_spans(cls, spans: list[TextSpan]) -> "SpannedText":
        return cls(text="".join(s.text for s in spans), spans=spans)
