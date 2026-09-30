"""Decode canonical HTML-derived Markdown with an exact source-offset map."""
import html
import re


_ESCAPE = re.compile(r"\\([\\`*\[\]_|])|&(?:#[xX][0-9a-fA-F]+|#\d+|[A-Za-z][A-Za-z0-9]+);|<br>")


def semantic_view(source):
    text, offsets = [], []
    cursor = 0
    for match in _ESCAPE.finditer(source):
        text.append(source[cursor:match.start()])
        offsets.extend((i, i + 1) for i in range(cursor, match.start()))
        decoded = match.group(1) if match.group(1) is not None else (
            "\n" if match.group() == "<br>" else html.unescape(match.group()))
        text.append(decoded)
        offsets.extend([(match.start(), match.end())] * len(decoded))
        cursor = match.end()
    text.append(source[cursor:])
    offsets.extend((i, i + 1) for i in range(cursor, len(source)))
    return "".join(text), offsets
