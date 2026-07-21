"""Structured results returned by the MCP tools."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MaskDocumentResult(BaseModel):
    vault_id: str = Field(description="Handle for restoring later; keep it")
    masked_text: str = Field(description="The masked document content")
    output_format: str
    entity_counts: dict[str, int] = Field(
        description="How many distinct values were masked, per entity type"
    )
    warnings: list[str] = Field(default_factory=list)


class MaskReviewStarted(BaseModel):
    review_id: str = Field(description="Poll get_review_status with this id")
    status: str = Field(description="Always 'waiting_for_user' at start")
    file_path: str
    message: str = Field(
        description="Instruction to relay to the user about the review window"
    )


class ReviewStatus(BaseModel):
    review_id: str
    status: str = Field(
        description="waiting_for_user | completed | cancelled | failed"
    )
    reason: str | None = None


class ReviewResult(BaseModel):
    review_id: str
    masked_file_path: str
    masked_text: str
    vault_id: str
    output_format: str
    entity_counts: dict[str, int] = Field(default_factory=dict)
    manual_terms_added: list[str] = Field(
        default_factory=list,
        description="Terms the reviewer added by hand during this review",
    )
    warnings: list[str] = Field(default_factory=list)


class RestoreTextResult(BaseModel):
    restored_text: str
    unresolved_tokens: list[str] = Field(
        default_factory=list,
        description="Tokens not found in the vault (left intact in the text)",
    )


class RestoreDocumentResult(BaseModel):
    output_file_path: str
    unresolved_tokens: list[str] = Field(default_factory=list)
