"""Smoke test for the frozen server exe under the mandatory-review contract.

Verifies, against the real frozen binary over raw stdio JSON-RPC:
1. tool discovery — exactly the 5-tool surface;
2. mask_document returns a review handle and NO content;
3. after an (out-of-band) approval, get_review_result returns the approved
   masked text in a fresh process — state on disk, not in memory;
4. CLI mode with the bundled NER model masks random unlisted names
   (mask analysis now runs in the GUI/CLI process, so NER is exercised there);
5. cross-process restore via restore_text.

Usage: python smoke_frozen.py <path-to-maskingtool-server.exe>
"""
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def rpc_session(exe, env, requests, expect_ids, timeout=300):
    proc = subprocess.Popen(
        [exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, env=env,
    )
    lines: "queue.Queue[bytes]" = queue.Queue()

    def _reader():
        for line in proc.stdout:
            lines.put(line)

    threading.Thread(target=_reader, daemon=True).start()
    for r in requests:
        proc.stdin.write((json.dumps(r) + "\n").encode("utf-8"))
    proc.stdin.flush()

    responses = {}
    deadline = time.time() + timeout
    while set(expect_ids) - set(responses) and time.time() < deadline:
        try:
            line = lines.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(msg, dict) and msg.get("id") in expect_ids:
            responses[msg["id"]] = msg
    proc.stdin.close()
    proc.wait(timeout=30)
    return responses


def payload_of(response):
    result = response.get("result", {})
    sc = result.get("structuredContent")
    if sc:
        return sc.get("result", sc)
    return json.loads(result["content"][0]["text"])


exe = sys.argv[1]
tmp = Path(tempfile.mkdtemp(prefix="mask_smoke_"))
data_dir = tmp / "appdata"
(data_dir / "denylists").mkdir(parents=True)
(data_dir / "denylists" / "people.csv").write_text(
    "name\nZebulon Quarkfield\n", encoding="utf-8"
)
(data_dir / "denylists" / "companies.csv").write_text("name\n", encoding="utf-8")

doc = tmp / "doc.md"
doc.write_text(
    "Zebulon Quarkfield met Robert Downey of Vertex Solutions Pty Ltd.\n",
    encoding="utf-8",
)

env = dict(os.environ)
env["MASKINGTOOL_DATA_DIR"] = str(data_dir)
env["MASKINGTOOL_NO_GUI_SPAWN"] = "1"

HANDSHAKE = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
]
failures = []

# 1+2: discovery + review start
responses = rpc_session(exe, env, HANDSHAKE + [
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "mask_document", "arguments": {"file_path": str(doc)}}},
], expect_ids={1, 2, 3})

tool_names = {t["name"] for t in responses.get(2, {}).get("result", {}).get("tools", [])}
expected = {"mask_document", "get_review_status", "get_review_result",
            "restore_text", "restore_document"}
if tool_names != expected:
    failures.append(f"unexpected tool list: {tool_names}")

review_id = ""
if 3 in responses:
    data = payload_of(responses[3])
    review_id = data.get("review_id", "")
    if data.get("status") != "waiting_for_user":
        failures.append(f"unexpected start status: {data.get('status')}")
    if "masked_text" in data or "Zebulon" in json.dumps(data):
        failures.append("mask_document leaked content before approval")
else:
    failures.append("no response to mask_document")

# 4: CLI mode of the SAME frozen exe does the masking (exercises bundled NER)
masked_out = tmp / "doc.masked.md"
cli = subprocess.run(
    [exe, "mask", str(doc), "-o", str(masked_out), "--result-json",
     str(tmp / "info.json")],
    capture_output=True, env=env, timeout=300,
)
if cli.returncode != 0:
    failures.append(f"CLI mask failed: {cli.stderr[-300:]}")
masked_text = masked_out.read_text(encoding="utf-8") if masked_out.exists() else ""
if "Zebulon Quarkfield" in masked_text:
    failures.append("deny-list name leaked (CLI)")
if "Robert Downey" in masked_text or "Vertex Solutions" in masked_text:
    failures.append("NER (bundled model) failed to mask random names")
info = json.loads((tmp / "info.json").read_text(encoding="utf-8")) if (tmp / "info.json").exists() else {}
vault_id = info.get("vault_id", "")

# 3: approve out-of-band (as the GUI would), then fetch via a COLD process
if review_id and vault_id:
    review_file = data_dir / "reviews" / f"review_{review_id}.json"
    review_data = json.loads(review_file.read_text(encoding="utf-8"))
    review_data["status"] = "completed"
    review_data["result"] = {
        "masked_file_path": str(masked_out), "vault_id": vault_id,
        "output_format": "markdown",
        "entity_counts": info.get("entity_counts", {}),
        "manual_terms_added": [], "warnings": [],
    }
    review_file.write_text(json.dumps(review_data), encoding="utf-8")

    r2 = rpc_session(exe, env, HANDSHAKE + [
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "get_review_result",
                    "arguments": {"review_id": review_id}}},
    ], expect_ids={1, 4})
    got = payload_of(r2.get(4, {})) if 4 in r2 else {}
    if "⟦PERSON_" not in got.get("masked_text", ""):
        failures.append("get_review_result did not return approved masked text")

    # 5: cross-process restore
    r3 = rpc_session(exe, env, HANDSHAKE + [
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "restore_text",
                    "arguments": {"vault_id": vault_id,
                                  "masked_text": masked_text}}},
    ], expect_ids={1, 5})
    restored = payload_of(r3.get(5, {})).get("restored_text", "") if 5 in r3 else ""
    if "Zebulon Quarkfield" not in restored or "Robert Downey" not in restored:
        failures.append("cross-process restore failed")
else:
    failures.append("missing review_id or vault_id for approval step")

if failures:
    print("SMOKE FAILED:")
    for f in failures:
        print(" -", f)
    sys.exit(1)

print("SMOKE OK: 5 tools, review-gated masking, bundled NER via CLI, "
      "cross-process restore")
