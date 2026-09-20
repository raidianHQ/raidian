"""Persists an already-generated, already-validated AINarrativeResponse.
Deliberately separate from generation.generate_ai_narrative() (which makes
the network call) -- mirrors interpretation/persistence.py's own
compute-vs-persist split exactly, applied one layer over.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_narrative import AINarrative
from app.models.interpretation import Interpretation
from app.schemas.ai_narrative import AINarrativeResponse


def _next_sequence(session: Session) -> int:
    """Mirrors interpretation/persistence.py::_next_sequence -- a global,
    not per-interpretation, monotonic counter. See AINarrative.sequence's
    own docstring for why.
    """
    current_max = session.execute(select(func.max(AINarrative.sequence))).scalar()
    return (current_max or 0) + 1


def save_ai_narrative(
    session: Session, interpretation: Interpretation, response: AINarrativeResponse
) -> AINarrative:
    """Creates a new AINarrative row for `interpretation`. Never modifies
    or removes a prior AINarrative row -- regenerating preserves history,
    exactly like reinterpreting a Reading preserves Interpretation history.

    Does not commit -- the caller controls the transaction boundary
    (mirrors save_interpretation's own contract).
    """
    ai_narrative = AINarrative(
        interpretation=interpretation,
        provider=response.provider,
        model=response.model,
        ai_narrative=response.model_dump(mode="json"),
        sequence=_next_sequence(session),
    )
    session.add(ai_narrative)
    session.flush()
    return ai_narrative
