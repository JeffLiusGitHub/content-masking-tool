"""Deny-list recognizer construction and (optional) NER assembly.

The deny-list is the PRIMARY mechanism: matches always score 1.0 and are
resolved before any NER result. NER (off by default) can only ADD matches
for spans the deny-list didn't claim.

Presidio's own deny_list mode uses \\b word boundaries, which never match
between two CJK characters (both are \\w), so Chinese names inside Chinese
sentences would be missed. We therefore build the regex per term: ASCII
terms get word-boundary guards, CJK-containing terms match anywhere.
"""
from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer

DENYLIST_SCORE = 1.0
MIN_PART_LEN = 2  # never expand single-letter parts (the "K" in "Dana K")

_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")


def expand_person_name_parts(terms: list[str]) -> list[str]:
    """Full names plus their individual parts, so a bare first name or
    surname ("Owen", "Bradley") is masked too. Each part restores to exactly
    itself — a bare "Sam" is never guessed into a specific full name.

    CJK names are not split (no whitespace parts); single-letter parts are
    skipped as too destructive. Case-sensitive matching limits collisions
    with common words ("Field", "Summer"), but a capitalized collision at
    sentence start is an accepted trade-off of recall-first masking.
    """
    expanded = list(terms)
    seen = set(terms)
    for term in terms:
        if _CJK.search(term):
            continue
        for part in term.split():
            if len(part) >= MIN_PART_LEN and part not in seen:
                seen.add(part)
                expanded.append(part)
    return expanded


def _term_regex(term: str) -> str:
    escaped = re.escape(term)
    if _CJK.search(term):
        return escaped
    return rf"(?<!\w){escaped}(?!\w)"


def build_denylist_recognizers(
    deny_lists: dict[str, list[str]],
) -> list[PatternRecognizer]:
    """One PatternRecognizer per entity type (e.g. ORG, PERSON).

    Terms are sorted longest-first inside the alternation so that at the
    same start position the regex prefers "Acme Corp" over "Acme".
    """
    recognizers = []
    for entity_type, terms in deny_lists.items():
        terms = [t.strip() for t in terms if t and t.strip()]
        if not terms:
            continue
        alternation = "|".join(
            _term_regex(t) for t in sorted(set(terms), key=len, reverse=True)
        )
        pattern = Pattern(
            name=f"denylist_{entity_type}",
            regex=alternation,
            score=DENYLIST_SCORE,
        )
        recognizers.append(
            PatternRecognizer(
                supported_entity=entity_type,
                name=f"denylist_{entity_type}",
                patterns=[pattern],
                # Presidio defaults include re.IGNORECASE; Stage 1 semantics
                # are exact case-sensitive matching
                global_regex_flags=re.DOTALL | re.MULTILINE,
            )
        )
    return recognizers
