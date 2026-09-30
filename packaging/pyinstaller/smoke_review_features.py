"""Exercise HTML/URL/rules in a frozen binary, plus hidden GUI construction.

Usage: python smoke_review_features.py <unsigned-test-only executable>
All fixtures and app data are synthetic and isolated in a temporary directory.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from bs4 import BeautifulSoup


def main(executable):
    executable = str(Path(executable).resolve())
    with tempfile.TemporaryDirectory(prefix="mask_features_") as directory:
        root = Path(directory)
        app = root / "app"
        lists = app / "denylists"
        lists.mkdir(parents=True)
        (app / "settings.json").write_text(json.dumps({"enable_ner": False, "gui_tutorial_seen": True}), encoding="utf-8")
        (lists / "companies.csv").write_text("name\nA[B]*Lab\n", encoding="utf-8")
        (lists / "people.csv").write_text("name\n", encoding="utf-8")
        (lists / "manual_terms.json").write_text(json.dumps({"terms": [{"term": "first\nsecond", "entity_type": "TEXT"}]}), encoding="utf-8")
        (lists / "allow_terms.json").write_text(json.dumps({"terms": ["www.allowed.test"]}), encoding="utf-8")
        env = {**os.environ, "MASKINGTOOL_DATA_DIR": str(app), "MASKINGTOOL_MASKED_DIR": str(root / "masked"), "MASKINGTOOL_NO_GUI_SPAWN": "1"}
        startup = None
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE

        def run(*args):
            result = subprocess.run([executable, *map(str, args)], env=env, capture_output=True, timeout=90, startupinfo=startup)
            if result.returncode:
                raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
            return json.loads(result.stdout.decode("utf-8"))

        source = root / "source.html"
        source.write_text('<h1>Schedule</h1><table><tr><th>Client</th><th>URL</th></tr><tr><td>A[B]*Lab</td><td><a href="https://example.test/a_b?x=1&amp;y=2">Details</a></td></tr></table><p>www.allowed.test</p>', encoding="utf-8")
        masked = root / "result.html"
        info = run("mask", source, "--no-ner", "--format", "html", "-o", masked)
        content = masked.read_text(encoding="utf-8")
        assert "⟦URL_001⟧" in content and "⟦ORG_001⟧" in content
        assert "www.allowed.test" in content and "<table>" in content
        restored = root / "restored.html"
        run("restore", masked, "--vault-id", info["vault_id"], "-o", restored)
        parsed = BeautifulSoup(restored.read_text(encoding="utf-8"), "html.parser")
        assert "A[B]*Lab" in parsed.text
        assert parsed.a["href"] == "https://example.test/a_b?x=1&y=2"
        multiline = root / "multiline.md"
        multiline.write_bytes(b"first\nsecond")
        result = root / "multiline.masked.md"
        info = run("mask", multiline, "--no-ner", "-o", result)
        assert result.read_text(encoding="utf-8") == "⟦TEXT_001⟧"
        restored = root / "multiline.restored.md"
        run("restore", result, "--vault-id", info["vault_id"], "-o", restored)
        assert restored.read_bytes() == multiline.read_bytes()
        print("PASS: frozen HTML parser, semantic table, URL/TEXT, persistent allows and cold-process restore", flush=True)

        # Registering a GUI PID occurs only after the real widgets are built.
        reviews = app / "reviews"
        reviews.mkdir(exist_ok=True)
        review_id = "rvw_20260928T000000_smoke"
        record = reviews / f"review_{review_id}.json"
        record.write_text(json.dumps({"review_id": review_id, "status": "waiting_for_user", "file_path": str(source), "gui_pid": None}), encoding="utf-8")
        with (root / "gui.log").open("wb") as log:
            proc = subprocess.Popen([executable, "gui", "--review-id", review_id, "--file", str(source)], env=env, stdout=log, stderr=log, startupinfo=startup)
            try:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("Frozen GUI exited before startup completed")
                    if json.loads(record.read_text(encoding="utf-8")).get("gui_pid"):
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Frozen GUI did not register its PID")
                time.sleep(3)
                assert proc.poll() is None
                assert json.loads(record.read_text(encoding="utf-8"))["status"] == "waiting_for_user"
                assert not list((root / "masked").glob("*.md"))
            finally:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=15)
        assert "Traceback" not in (root / "gui.log").read_text(encoding="utf-8", errors="replace")
        print("PASS: frozen review GUI startup, review remains unapproved and no output created", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
