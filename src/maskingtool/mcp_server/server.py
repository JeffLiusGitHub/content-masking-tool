"""MCP stdio server exposing mask_document / restore_text / restore_document.

This module is the PyInstaller freeze entry point — keep it import-light and
stable (packaging/pyinstaller/maskingtool.spec points here).
"""
from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from maskingtool.mcp_server import tools
from maskingtool.mcp_server.schemas import (
    MaskReviewStarted,
    RestoreDocumentResult,
    RestoreTextResult,
    ReviewResult,
    ReviewStatus,
)

mcp = FastMCP(
    "content-masking-tool",
    instructions=(
        "Masks company/people names in local documents with MANDATORY human "
        "review before any content enters the conversation. Flow: "
        "mask_document(file) opens a review window and returns a review_id "
        "immediately -> tell the user to review/confirm in the window, then "
        "IMMEDIATELY call get_review_status(review_id) — it long-polls "
        "server-side (default 25s per call) and returns the moment the user "
        "clicks Confirm; keep calling it until status is no longer "
        "waiting_for_user (do NOT wait for the user to say they are done) -> "
        "if completed, get_review_result(review_id) returns the approved "
        "masked_text and vault_id -> continue processing the masked_text "
        "automatically -> restore via "
        "restore_document (writes locally; preferred) or restore_text (puts "
        "real names into the conversation) using that vault_id. MANDATORY: "
        "never read a .pdf/.docx/.doc/.md document's content directly by any "
        "other means (file tools, shell commands); there is NO way to obtain "
        "document content without the user's review approval."
    ),
)


@mcp.tool()
def mask_document(file_path: str) -> MaskReviewStarted:
    """Start masking a local document (.md/.txt/.docx/.pdf) with MANDATORY
    human review: a review window opens on the user's screen and this call
    returns immediately with a review_id. No masked content is available
    until the user confirms in the window. Tell the user to review and
    confirm, then IMMEDIATELY call get_review_status (it long-polls and
    returns as soon as the user decides) — do not wait for the user to
    report back in chat."""
    return tools.mask_document(file_path)


@mcp.tool()
def get_review_status(review_id: str, wait_seconds: float = 25) -> ReviewStatus:
    """Check a mask review: waiting_for_user, completed, cancelled, or
    failed. Long-polls: blocks up to wait_seconds (default 25, max 55) and
    returns the instant the user clicks Confirm/Cancel in the review window.
    If it returns waiting_for_user, the user has not decided yet — call it
    again to keep waiting. Pass wait_seconds=0 for an instant check."""
    return tools.get_review_status(review_id, wait_seconds)


@mcp.tool()
def get_review_result(review_id: str) -> ReviewResult:
    """Fetch the human-approved masked text (plus vault_id and stats) for a
    completed review. Errors if the review is not completed."""
    return tools.get_review_result(review_id)


@mcp.tool()
def restore_text(vault_id: str, masked_text: str) -> RestoreTextResult:
    """Restore original names into masked text using the vault_id returned by
    mask_document. Unknown tokens are left intact and reported."""
    return tools.restore_text(vault_id, masked_text)


@mcp.tool()
def restore_document(
    vault_id: str,
    masked_file_path: str,
    output_path: str | None = None,
) -> RestoreDocumentResult:
    """Restore original names into a masked file (.md/.html/.txt/.docx) and
    write the result next to it (or to output_path). Returns the output file
    path."""
    return tools.restore_document(vault_id, masked_file_path, output_path)


def main() -> None:
    # One frozen binary: arguments = CLI, piped stdin = MCP, interactive
    # double-click/terminal launch = desktop GUI.
    from maskingtool.runtime import choose_run_mode

    mode = choose_run_mode(sys.argv[1:], sys.stdin)
    if mode == "cli":
        from maskingtool.cli import main as cli_main
        sys.exit(cli_main(sys.argv[1:]))
    if mode == "gui":
        from maskingtool.gui import main as gui_main
        gui_main()
        return
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
