"""Token restore and replacement application.

Restore is deliberately NOT routed through Presidio's DeanonymizeEngine:
tokens have a fixed, self-describing format (see vault.TOKEN_PATTERN), so a
regex scan + vault lookup is faster, dependency-light, and immune to
Presidio API changes.
"""
from __future__ import annotations

from maskingtool.vault import TOKEN_PATTERN, Vault


def restore_text(masked_text: str, vault: Vault) -> tuple[str, list[str]]:
    """Replace every known token with its original value.

    Unknown tokens are left intact and reported (order of first appearance,
    deduplicated).
    """
    unresolved: list[str] = []
    seen: set[str] = set()

    def _sub(match) -> str:
        token = match.group(0)
        original = vault.resolve(token)
        if original is None:
            if token not in seen:
                seen.add(token)
                unresolved.append(token)
            return token
        return original

    return TOKEN_PATTERN.sub(_sub, masked_text), unresolved


def apply_replacements(text: str, replacements: list[tuple[int, int, str]]) -> str:
    """Apply (start, end, replacement) edits to text. Ranges must not overlap."""
    out = []
    cursor = 0
    for start, end, repl in sorted(replacements, key=lambda r: r[0]):
        out.append(text[cursor:start])
        out.append(repl)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)
