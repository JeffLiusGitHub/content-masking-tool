"""Offline HTML-to-semantic-Markdown conversion, with rectangular tables."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


def _escape(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*\[\]_])", r"\\\1", text)


def parse_html(path: Path) -> tuple[str, list[str]]:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    warnings = []
    for node in soup.find_all(["script", "style", "template", "iframe", "object", "embed"]):
        node.decompose()
    for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
        node.extract()

    def children(node):
        return "".join(render(child) for child in node.children)

    def table(node, nested=False):
        if nested:
            warnings.append("Nested table simplified to lines inside its parent cell.")
        grid = {}
        rows = [row for row in node.find_all("tr") if row.find_parent("table") is node]
        for row_index, row in enumerate(rows):
            col = 0
            for cell in row.find_all(["td", "th"], recursive=False):
                while (row_index, col) in grid:
                    col += 1
                value = children(cell).strip().replace("\n", "<br>").replace("|", "\\|")
                def span(name, cell=cell):
                    try:
                        n = int(cell.get(name, 1))
                    except (ValueError, TypeError):
                        n = 1
                    if n > 1000:
                        raise ValueError("HTML table span exceeds 1000 cells.")
                    return max(1, n)
                rowspan, colspan = span("rowspan"), span("colspan")
                if len(grid) + rowspan * colspan > 100000:
                    raise ValueError("Expanded HTML table exceeds 100000 cells.")
                for y in range(row_index, row_index + rowspan):
                    for x in range(col, col + colspan):
                        grid[y, x] = value
                col += colspan
        if not grid:
            return ""
        height = max(y for y, _ in grid) + 1
        width = max(x for _, x in grid) + 1
        if height * width > 100000:
            raise ValueError("Expanded HTML table exceeds 100000 cells.")
        values = [[grid.get((y, x), "") for x in range(width)] for y in range(height)]
        if nested:
            return "<br>".join(" / ".join(row) for row in values)
        lines = ["| " + " | ".join(row) + " |" for row in values]
        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
        caption = node.find("caption", recursive=False)
        return "\n\n" + (children(caption).strip() + "\n\n" if caption else "") + "\n".join(lines) + "\n\n"

    def render(node):
        if isinstance(node, NavigableString):
            return _escape(re.sub(r"\s+", " ", str(node)))
        if not isinstance(node, Tag):
            return ""
        name = node.name.lower()
        if name == "head":
            return ""
        if name == "table":
            return table(node, nested=node.find_parent("table") is not None)
        if name == "br":
            return "<br>" if node.find_parent(["td", "th"]) else "\n"
        if name == "img":
            return _escape(node.get("alt", ""))
        if name == "a":
            label = children(node)
            href = node.get("href", "").strip()
            # Preserve inert local/HTTP/mail links only; never execute or fetch.
            try:
                safe = urlsplit(href).scheme.lower() in {"", "http", "https", "mailto"}
            except ValueError:
                safe = False
            if href and safe:
                href = href.replace("<", "%3C").replace(">", "%3E").replace("\n", "%0A").replace("\r", "%0D")
                return f"[{label}](<{_escape(href)}>)"
            return label
        if name == "pre":
            raw = node.get_text()
            fence = "`" * max(3, max((len(m.group()) + 1 for m in re.finditer(r"`+", raw)), default=3))
            return f"\n\n{fence}\n{raw}\n{fence}\n\n"
        body = children(node)
        if re.fullmatch(r"h[1-6]", name):
            return "\n\n" + "#" * int(name[1]) + " " + body.strip() + "\n\n"
        if name == "li":
            prefix = "1. " if node.parent.name == "ol" else "- "
            return "\n" + prefix + body.strip() + "\n"
        if name in {"p", "div", "section", "article", "ul", "ol", "header", "footer", "blockquote"}:
            return "\n\n" + body.strip() + "\n\n"
        if name == "hr":
            return "\n\n---\n\n"
        # Inline styling is intentionally flattened so names remain contiguous.
        return body

    source = children(soup.body or soup)
    source = re.sub(r"\n[ \t]+", "\n", source)
    source = re.sub(r"\n{3,}", "\n\n", source).strip() + "\n"
    return source, list(dict.fromkeys(warnings))
