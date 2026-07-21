"""Async mask-review jobs: every MCP mask request opens the GUI for human
approval; Claude polls status instead of blocking on the user.

State lives in %APPDATA%\\ContentMaskingTool\\reviews\\review_<id>.json
(atomic writes), so jobs survive MCP server restarts between conversation
turns. States: waiting_for_user -> completed | cancelled | failed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from maskingtool import config

_STILL_ACTIVE = 259


class ReviewNotFoundError(Exception):
    def __init__(self, review_id: str):
        super().__init__(f"Review '{review_id}' was not found.")
        self.review_id = review_id


def reviews_dir() -> Path:
    d = config.get_app_dir() / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(review_id: str) -> Path:
    return reviews_dir() / f"review_{review_id}.json"


def _write(review_id: str, data: dict) -> None:
    directory = reviews_dir()
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".review_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path(review_id))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read(review_id: str) -> dict:
    path = _path(review_id)
    if not path.exists():
        raise ReviewNotFoundError(review_id)
    return json.loads(path.read_text(encoding="utf-8"))


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def create_review(file_path: Path) -> dict:
    review_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    data = {
        "review_id": review_id,
        "status": "waiting_for_user",
        "file_path": str(file_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gui_pid": None,
        "result": None,
        "reason": None,
    }
    _write(review_id, data)
    return data


def set_gui_pid(review_id: str, pid: int) -> None:
    data = _read(review_id)
    data["gui_pid"] = int(pid)
    _write(review_id, data)


def complete_review(review_id: str, result: dict) -> None:
    data = _read(review_id)
    data["status"] = "completed"
    data["result"] = result
    _write(review_id, data)


def cancel_review(review_id: str) -> None:
    data = _read(review_id)
    if data["status"] == "waiting_for_user":
        data["status"] = "cancelled"
        _write(review_id, data)


def fail_review(review_id: str, reason: str) -> None:
    data = _read(review_id)
    if data["status"] == "waiting_for_user":
        data["status"] = "failed"
        data["reason"] = reason
        _write(review_id, data)


def get_status(review_id: str) -> dict:
    """Current status; detects a GUI that died without deciding."""
    data = _read(review_id)
    if (
        data["status"] == "waiting_for_user"
        and data.get("gui_pid")
        and not pid_alive(data["gui_pid"])
    ):
        data["status"] = "failed"
        data["reason"] = "review window was closed without a decision"
        _write(review_id, data)
    return data


def wait_for_decision(
    review_id: str, timeout_s: float, poll_interval: float = 0.25
) -> dict:
    """Long-poll: block until the review leaves waiting_for_user (user clicked
    Confirm/Cancel, or the GUI died) or timeout_s elapses. Returns the latest
    status data either way — on timeout it is still waiting_for_user."""
    deadline = time.monotonic() + max(0.0, timeout_s)
    while True:
        data = get_status(review_id)
        if data["status"] != "waiting_for_user" or time.monotonic() >= deadline:
            return data
        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))


def get_result(review_id: str) -> dict:
    data = get_status(review_id)
    if data["status"] != "completed":
        raise ValueError(
            f"Review {review_id} is '{data['status']}', not completed"
            + (f" ({data['reason']})" if data.get("reason") else "")
        )
    return data["result"]


def launch_review_gui(review_id: str, file_path: Path) -> None:
    """Spawn the GUI as a DETACHED process so it survives MCP restarts.
    Set MASKINGTOOL_NO_GUI_SPAWN=1 to suppress (tests / headless)."""
    if os.environ.get("MASKINGTOOL_NO_GUI_SPAWN"):
        return
    if getattr(sys, "frozen", False):
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, "-m", "maskingtool"]
    cmd += ["gui", "--review-id", review_id, "--file", str(file_path)]
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        cmd, creationflags=flags, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
