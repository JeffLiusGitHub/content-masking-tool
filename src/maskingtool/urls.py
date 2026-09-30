"""Offline, deterministic URL detection; never join physical lines."""
import re
from urllib.parse import urlsplit

from presidio_analyzer import RecognizerResult


_START = re.compile(r"(?<![\w@])(?:https?://|www\.)[^\s<>\"'`|，。；！？]+", re.IGNORECASE)


def find_urls(text):
    results = []
    for match in _START.finditer(text):
        value = match.group()
        while value:
            if value[-1] in ".,;:!?，。；：！？":
                value = value[:-1]
                continue
            pairs = {")": "(", "]": "[", "}": "{"}
            if value[-1] in pairs and value.count(value[-1]) > value.count(pairs[value[-1]]):
                value = value[:-1]
                continue
            break
        try:
            parts = urlsplit("http://" + value if value.lower().startswith("www.") else value)
            if not parts.hostname or parts.hostname.lower() == "www":
                continue
        except ValueError:
            continue
        results.append(RecognizerResult("URL", match.start(), match.start() + len(value), 1.0))
    return results
