"""Tool implementations: thin wrappers over the tested pipeline.

All state lives on disk (vaults, deny-lists), so every call is independent —
the server process may restart between conversation turns without losing
the ability to restore.
"""
from __future__ import annotations

from pathlib import Path

from maskingtool import audit, review
from maskingtool.mcp_server.schemas import (
    MaskReviewStarted,
    RestoreDocumentResult,
    RestoreTextResult,
    ReviewResult,
    ReviewStatus,
)
from maskingtool.operators import restore_text as _restore_text
from maskingtool.pipeline import restore_file
from maskingtool.textio import read_text_exact
from maskingtool.vault import Vault


def _existing_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def mask_document(file_path: str) -> MaskReviewStarted:
    """MANDATORY human review: opens the local review GUI and returns
    immediately. Masked text reaches the conversation only via
    get_review_result after the user confirms in the window."""
    path = _existing_path(file_path)
    supported = {".md", ".markdown", ".txt", ".docx", ".pdf"}
    if path.suffix.lower() not in supported:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. Supported: "
            + ", ".join(sorted(supported))
        )
    job = review.create_review(path)
    review.launch_review_gui(job["review_id"], path)
    out = MaskReviewStarted(
        review_id=job["review_id"],
        status="waiting_for_user",
        file_path=str(path),
        message=(
            "A review window has opened on the user's screen. Tell the user to "
            "check the masking preview, add any missed names, and confirm — "
            "then IMMEDIATELY call get_review_status with this review_id (it "
            "waits server-side and returns as soon as the user decides). Keep "
            "calling it until the status is no longer waiting_for_user; do not "
            "wait for the user to say they are done."
        ),
    )
    audit.record_call(
        "mask_document",
        {"file_path": str(path), "mandatory_review": True},
        out.model_dump(),  # no document content — only the review handle
    )
    return out


MAX_STATUS_WAIT_S = 55  # stay under typical MCP client request timeouts (~60s)


def get_review_status(review_id: str, wait_seconds: float = 0) -> ReviewStatus:
    wait = min(max(float(wait_seconds), 0.0), MAX_STATUS_WAIT_S)
    if wait > 0:
        data = review.wait_for_decision(review_id, timeout_s=wait)
    else:
        data = review.get_status(review_id)
    out = ReviewStatus(
        review_id=review_id, status=data["status"], reason=data.get("reason")
    )
    audit.record_call(
        "get_review_status",
        {"review_id": review_id, "wait_seconds": wait},
        out.model_dump(),
    )
    return out


def get_review_result(review_id: str) -> ReviewResult:
    data = review.get_result(review_id)  # raises unless completed
    masked_path = Path(data["masked_file_path"])
    out = ReviewResult(
        review_id=review_id,
        masked_file_path=str(masked_path),
        masked_text=read_text_exact(masked_path),
        vault_id=data["vault_id"],
        output_format=data.get("output_format", "markdown"),
        entity_counts=data.get("entity_counts", {}),
        manual_terms_added=data.get("manual_terms_added", []),
        warnings=data.get("warnings", []),
    )
    audit.record_call(
        "get_review_result",
        {"review_id": review_id},
        out.model_dump(),  # exactly what Claude receives — approved masked text
    )
    return out


def restore_text(vault_id: str, masked_text: str) -> RestoreTextResult:
    vault = Vault.load(vault_id)
    restored, unresolved = _restore_text(masked_text, vault)
    out = RestoreTextResult(restored_text=restored, unresolved_tokens=unresolved)
    # restore_text DOES return originals into the conversation by design; the
    # audit log makes that visible so reviewers can see the trade-off explicitly
    audit.record_call(
        "restore_text",
        {"vault_id": vault_id, "returns_originals_to_conversation": True},
        out.model_dump(),
    )
    return out


def restore_document(
    vault_id: str,
    masked_file_path: str,
    output_path: str | None = None,
) -> RestoreDocumentResult:
    path = _existing_path(masked_file_path)
    vault = Vault.load(vault_id)
    out = (
        Path(output_path)
        if output_path
        else path.with_name(path.stem + ".restored" + path.suffix)
    )
    unresolved = restore_file(path, vault, out)
    result = RestoreDocumentResult(
        output_file_path=str(out), unresolved_tokens=unresolved
    )
    # restore_document writes originals to a LOCAL file only; the payload
    # returned to Claude is just the path — no originals cross the boundary
    audit.record_call(
        "restore_document",
        {"vault_id": vault_id, "masked_file_path": str(path)},
        result.model_dump(),
    )
    return result
