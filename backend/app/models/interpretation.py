from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.reading import Reading


class Interpretation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One deterministic Interpretation Engine run against a Reading.

    Related to Reading (not columns added to it) and one-to-many, per
    Documentation/INTERPRETATION_ENGINE_DESIGN.md Section 9, Q1: this
    preserves the evidence-vs-interpretation separation
    (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 17) and supports
    reinterpretation with a newer engine without ever touching CardDraw or
    any other evidence row. The "current" interpretation for a Reading is
    simply the row with the latest created_at -- no is_current flag, so
    there is nothing that can drift out of sync with reality.

    `interpretive_model` stores app.schemas.interpretive_model.InterpretiveModel,
    serialized via `.model_dump(mode="json")`. engine_version and
    reference_data_version are duplicated out of that JSON blob into their
    own columns so a specific run's provenance can be queried/filtered
    without deserializing the JSON payload.

    `sequence` is a globally unique, monotonically increasing integer
    assigned by application code (app/services/interpretation/persistence.py)
    at insert time -- it is the deterministic "current interpretation for
    this reading" ordering key (the row with the highest `sequence` for a
    given `reading_id`), per
    Documentation/READING_INTEGRATION_DESIGN.md Section 7. It exists
    because `created_at` alone is not a reliable tiebreak: SQLite's
    `CURRENT_TIMESTAMP` has only second-level resolution, and the UUID
    primary key is random (uuid4), not time-ordered, so two rows created
    within the same wall-clock second on SQLite would otherwise have no
    deterministic ordering. `unique=True` turns a hypothetical concurrent
    double-assignment (this project has no locking around the sequence
    computation -- acceptable for its current single-writer-per-reading
    usage pattern) into a loud IntegrityError rather than a silent
    ordering ambiguity.
    """

    __tablename__ = "interpretations"

    reading_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("readings.id", ondelete="CASCADE"), nullable=False
    )

    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_data_version: Mapped[str] = mapped_column(String(64), nullable=False)
    interpretive_model: Mapped[dict] = mapped_column(JSON, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    reading: Mapped["Reading"] = relationship(back_populates="interpretations")
