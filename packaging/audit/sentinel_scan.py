"""mitmproxy addon: scan every request body leaving the machine for sentinel
strings, and log a verdict per request to Anthropic hosts.

Usage:
    mitmdump -s sentinel_scan.py --set sentinels="Nadella,Mojang,LinkedIn"

For each request it records: host, path, whether the body is present, and for
each sentinel whether it appears in the raw body in ANY common encoding
(plain / gzip-decompressed / base64 / url-encoded). Verdicts go to
audit-network-<date>.jsonl next to this script's working dir and to the
mitmproxy event log so they show on screen for screenshots.

This answers Q2: what does the Claude app actually put on the wire.
"""
import base64
import gzip
import json
import urllib.parse
import zlib
from datetime import datetime, timezone

from mitmproxy import ctx, http

ANTHROPIC_HINTS = ("anthropic", "claude")


def _decompress(body: bytes) -> bytes:
    out = body
    for name, fn in (("gzip", lambda b: gzip.decompress(b)),
                     ("zlib", lambda b: zlib.decompress(b))):
        try:
            out += b"\n" + fn(body)
        except (OSError, zlib.error, ValueError):
            pass
    return out


def _forms(sentinel: str) -> list[bytes]:
    return [
        sentinel.encode("utf-8"),
        json.dumps(sentinel).strip('"').encode("utf-8"),
        urllib.parse.quote(sentinel).encode("ascii"),
        base64.b64encode(sentinel.encode("utf-8")),
    ]


class SentinelScan:
    def __init__(self):
        self.sentinels: list[str] = []
        self.outfile = None

    def load(self, loader):
        loader.add_option("sentinels", str, "", "comma-separated sentinel strings")
        loader.add_option("auditout", str, "audit-network.jsonl", "verdict jsonl path")

    def configure(self, updated):
        if "sentinels" in updated:
            self.sentinels = [s.strip() for s in ctx.options.sentinels.split(",") if s.strip()]
            ctx.log.warn(f"[sentinel-scan] watching {len(self.sentinels)} sentinels: {self.sentinels}")

    def request(self, flow: http.HTTPFlow):
        host = flow.request.pretty_host.lower()
        if not any(h in host for h in ANTHROPIC_HINTS):
            return
        body = flow.request.raw_content or b""
        haystack = _decompress(body).lower()
        found = {}
        for s in self.sentinels:
            hit = any(f.lower() in haystack for f in _forms(s))
            found[s] = hit
        leaked = [s for s, hit in found.items() if hit]
        verdict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": flow.request.pretty_host,
            "path": flow.request.path.split("?")[0],
            "method": flow.request.method,
            "body_bytes": len(body),
            "leaked_sentinels": leaked,
            "clean": not leaked,
        }
        with open(ctx.options.auditout, "a", encoding="utf-8") as f:
            f.write(json.dumps(verdict, ensure_ascii=False) + "\n")
        tag = "LEAK!" if leaked else "clean"
        ctx.log.warn(
            f"[sentinel-scan] {tag} {flow.request.method} {host}"
            f"{verdict['path']} ({len(body)}B)"
            + (f"  LEAKED: {leaked}" if leaked else "")
        )


addons = [SentinelScan()]
