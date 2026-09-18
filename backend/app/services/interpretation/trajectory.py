"""Stage 8: trajectory derivation.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 9, stage 8 and Section 10.5: "The
arc across ordered, time-relevant positions (e.g. Past -> Influence ->
Near Future)... Only populated when the Layout has positions with a
temporal/progressive semantic_role; not every Layout implies a trajectory."

Ordering is by fixed semantic meaning (recent_past -> situation ->
near_future), NOT by SpreadPosition.position_order -- the two are not the
same thing. The Celtic Cross is the clearest example: its Recent Past
position is position_order 4, listed *after* its Situation position
(order 1), even though recent_past semantically precedes the present
situation in time. Using position_order for trajectory would put Celtic
Cross's steps in the wrong temporal order; using the fixed role order does
not depend on how any particular Spread happened to lay its positions out.
"""

from __future__ import annotations

from app.models.enums import SemanticRole
from app.schemas.interpretive_model import Explained, Trajectory, TrajectoryStep
from app.services.interpretation.citations import citation_for_draw
from app.services.interpretation.context import ReadingContext

# Fixed, content-derived order -- a literal tuple, never a dict/set.
_TRAJECTORY_ROLE_ORDER: tuple[SemanticRole, ...] = (
    SemanticRole.RECENT_PAST,
    SemanticRole.SITUATION,
    SemanticRole.NEAR_FUTURE,
)

# At least two temporal points are required to call it an "arc" -- a
# single point has no direction and isn't a trajectory.
_MIN_STEPS_FOR_TRAJECTORY = 2


def derive_trajectory(reading_context: ReadingContext) -> Explained[Trajectory] | None:
    steps = []
    citations = []

    for role in _TRAJECTORY_ROLE_ORDER:
        matches = reading_context.draws_with_role(role)
        if not matches:
            continue
        draw = matches[0]
        steps.append(
            TrajectoryStep(
                position_name=draw.position_name,
                semantic_role=draw.semantic_role.value,
                card_name=draw.card_name,
                orientation=draw.orientation.value,
            )
        )
        citations.append(citation_for_draw(draw))

    if len(steps) < _MIN_STEPS_FOR_TRAJECTORY:
        return None

    return Explained(value=Trajectory(arc=tuple(steps)), citations=tuple(citations))
