"""Request/response schemas for the Journal resource API. Mirrors
app/schemas/reading_api.py's ReadingCreateRequest exactly (same
blank-content field_validator, same "reject at the request boundary so a
bare model-layer ValueError never has a chance to escape as an
unhandled 500" rationale).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_CONTENT_LENGTH = 10_000
"""An implementation-safety default, not a Product Spec requirement --
generous for a personal reflection while guarding against a pathological
payload, the same rationale as reading_api.py's _MAX_QUESTION_LENGTH.
"""


class _Model(BaseModel):
    """Shared base: immutable once constructed, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class JournalEntryCreateRequest(_Model):
    content: str = Field(max_length=_MAX_CONTENT_LENGTH)

    @field_validator("content")
    @classmethod
    def _reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class JournalEntrySummary(_Model):
    id: UUID
    reading_id: UUID
    sequence: int
    content: str
    created_at: datetime
