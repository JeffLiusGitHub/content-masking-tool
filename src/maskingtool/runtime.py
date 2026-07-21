"""Select CLI, MCP, or desktop GUI without importing the heavy UI stack."""
from __future__ import annotations

import os
import stat
import sys
from typing import Sequence, TextIO


def _stdin_is_pipe(stdin: TextIO | None) -> bool:
    if stdin is None:
        return False
    try:
        fd = stdin.fileno()
    except (AttributeError, OSError, ValueError):
        try:
            return not stdin.isatty()
        except (AttributeError, OSError):
            return False

    if os.name == "nt":
        try:
            import ctypes
            import msvcrt

            handle = msvcrt.get_osfhandle(fd)
            return ctypes.windll.kernel32.GetFileType(handle) == 3  # FILE_TYPE_PIPE
        except (OSError, ValueError):
            return False
    try:
        return stat.S_ISFIFO(os.fstat(fd).st_mode)
    except OSError:
        return False


def choose_run_mode(argv: Sequence[str], stdin: TextIO | None) -> str:
    if argv:
        return "cli"
    return "mcp" if _stdin_is_pipe(stdin) else "gui"
