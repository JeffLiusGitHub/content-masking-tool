"""Self-test the sentinel scanner harness end-to-end WITHOUT needing Claude or
a trusted system CA: start mitmdump with the addon, send two HTTPS requests
through it (one containing a sentinel, one clean) to a host that looks like
Anthropic, then assert the verdict file flagged exactly the leaking one.

Proves the capture tooling works, so a later "clean" verdict against real
Claude traffic is trustworthy.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
VENV = Path(sys.executable).parent
CERT = Path(os.path.expanduser("~")) / ".mitmproxy" / "mitmproxy-ca-cert.pem"
VERDICTS = HERE / "selftest-verdicts.jsonl"
PORT = "8899"

VERDICTS.unlink(missing_ok=True)

proc = subprocess.Popen(
    [str(VENV / "mitmdump.exe"), "--listen-port", PORT, "-q",
     "-s", str(HERE / "sentinel_scan.py"),
     "--set", "sentinels=Zorbix,Vantalio",
     "--set", f"auditout={VERDICTS}"],
)
try:
    time.sleep(6)
    import requests

    proxies = {"https": f"http://127.0.0.1:{PORT}", "http": f"http://127.0.0.1:{PORT}"}
    # host contains "anthropic" so the scanner inspects it; example.com resolves
    # via mitmproxy. We use httpbin-like echo? Simplest: hit a real anthropic
    # host path (no auth needed to be captured — request is scanned before send).
    for label, body in [("leaky", "deal memo about Zorbix Quenndale"),
                        ("clean", "deal memo about PERSON_001 token only")]:
        try:
            requests.post("https://api.anthropic.com/v1/messages",
                          data=body.encode(), proxies=proxies,
                          verify=str(CERT), timeout=15)
        except requests.RequestException:
            pass  # we only care that the request body was scanned on the way out
    time.sleep(2)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

rows = [json.loads(l) for l in VERDICTS.read_text(encoding="utf-8").splitlines() if l.strip()] if VERDICTS.exists() else []
anthropic = [r for r in rows if "anthropic" in r["host"]]
leaks = [r for r in anthropic if not r["clean"]]

print(f"captured anthropic requests: {len(anthropic)}")
print(f"flagged as leaking        : {len(leaks)}")
for r in anthropic:
    print(f"  {'LEAK' if not r['clean'] else 'clean'}: {r['leaked_sentinels']} ({r['body_bytes']}B)")

ok = len(anthropic) >= 2 and len(leaks) == 1 and "Zorbix" in leaks[0]["leaked_sentinels"]
print("SELFTEST", "OK: scanner correctly flags leaks and passes clean bodies" if ok else "FAILED")
sys.exit(0 if ok else 1)
