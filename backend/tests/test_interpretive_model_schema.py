"""Pure schema tests for app.schemas.interpretive_model -- no database, no
engine. Verifies the output contract's own invariants
(INTERPRETATION_ENGINE_DESIGN.md Section 4).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.interpretive_model import (
    Citation,
    Contradiction,
    Explained,
    InterpretiveModel,
    Tension,
)


def _citation(**overrides) -> Citation:
    defaults = dict(
        source_type="card_draw",
        card_draw_id=uuid4(),
        card_name="The Fool",
        position_name="Situation",
        position_semantic_role="situation",
        contributing_theme="new_beginnings",
    )
    defaults.update(overrides)
    return Citation(**defaults)


def _minimal_model(**overrides) -> InterpretiveModel:
    defaults = dict(
        schema_version="1.0",
        engine_version="0.1.0-foundation",
        reference_data_version="deadbeef",
        generated_at=datetime.now(timezone.utc),
        central_question="What should I focus on?",
        central_issue=Explained(value="new_beginnings", citations=(_citation(),)),
        evidence_strength="unresolved",
    )
    defaults.update(overrides)
    return InterpretiveModel(**defaults)


def test_explained_rejects_empty_citations():
    with pytest.raises(ValidationError):
        Explained(value="x", citations=())


def test_contradiction_requires_at_least_two_sources():
    with pytest.raises(ValidationError):
        Contradiction(description="x", sources=(_citation(),))

    # two is fine
    Contradiction(description="x", sources=(_citation(), _citation(card_name="The Magician")))


def test_interpretive_model_round_trips_through_json():
    model = _minimal_model(
        primary_tension=Explained(
            value=Tension(pole_a="clarity", pole_b="uncertainty", label="Clarity vs. Uncertainty"),
            citations=(_citation(),),
        ),
        supporting_themes=(Explained(value="intuition", citations=(_citation(),)),),
        uncertainty=("nothing about the future is established",),
    )
    dumped = model.model_dump(mode="json")
    restored = InterpretiveModel.model_validate(dumped)
    assert restored == model


def test_interpretive_model_is_frozen():
    model = _minimal_model()
    with pytest.raises(ValidationError):
        model.evidence_strength = "strong"


def test_interpretive_model_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        _minimal_model(unexpected_field="surprise")


def test_evidence_strength_only_accepts_the_four_defined_values():
    with pytest.raises(ValidationError):
        _minimal_model(evidence_strength="very likely")

    for value in ("strong", "moderate", "weak", "unresolved"):
        _minimal_model(evidence_strength=value)  # must not raise


def test_optional_fields_default_to_absent():
    model = _minimal_model()
    assert model.primary_tension is None
    assert model.trajectory is None
    assert model.blocker is None
    assert model.advice is None
    assert model.clarification is None
    assert model.supporting_themes == ()
    assert model.uncertainty == ()
    assert model.contradictions == ()


def test_citation_accepts_a_rule_source():
    citation = Citation(source_type="compound_rule", rule_id="clarity_vs_uncertainty", rule_tier="conditional")
    assert citation.card_draw_id is None
