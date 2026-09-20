"""Pure schema tests for app.schemas.interpretive_model -- no database, no
engine. Verifies the output contract's own invariants
(INTERPRETATION_ENGINE_DESIGN.md Section 4).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.interpretive_model import (
    CardInterpretation,
    Citation,
    Contradiction,
    Explained,
    InterpretiveModel,
    Relationships,
    SuitClusterSummary,
    Tension,
    ThemeStrength,
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


def _card_interpretation(**overrides) -> CardInterpretation:
    defaults = dict(
        position_name="Situation",
        semantic_role="situation",
        position_order=1,
        card_name="The Fool",
        orientation="upright",
        meaning_text="New beginnings, a leap of faith.",
        themes=("new_beginnings",),
        citation=_citation(),
    )
    defaults.update(overrides)
    return CardInterpretation(**defaults)


def _minimal_model(**overrides) -> InterpretiveModel:
    defaults = dict(
        schema_version="1.0",
        engine_version="0.1.0-foundation",
        reference_data_version="deadbeef",
        generated_at=datetime.now(timezone.utc),
        central_question="What should I focus on?",
        spread_name="Single Card",
        card_interpretations=(_card_interpretation(),),
        relationships=Relationships(major_arcana_count=1, minor_arcana_count=0),
        central_issue=Explained(value="new_beginnings", citations=(_citation(),)),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(
            value="Together, the drawn cards center on new_beginnings.", citations=(_citation(),)
        ),
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
    assert model.spread_description is None
    assert model.theme_strength == ()
    assert model.relationships.same_suit_clusters == ()


def test_citation_accepts_a_rule_source():
    citation = Citation(source_type="compound_rule", rule_id="clarity_vs_uncertainty", rule_tier="conditional")
    assert citation.card_draw_id is None


# --- New synthesis fields (card_interpretations, relationships, theme_strength, ---
# --- deterministic_synthesis) ------------------------------------------------------


def test_card_interpretations_requires_at_least_one_entry():
    with pytest.raises(ValidationError):
        _minimal_model(card_interpretations=())


def test_card_interpretation_carries_position_and_card_fields():
    entry = _card_interpretation(card_name="The Magician", orientation="reversed", position_order=2)
    assert entry.card_name == "The Magician"
    assert entry.orientation == "reversed"
    assert entry.position_order == 2
    assert entry.citation.source_type == "card_draw"


def test_suit_cluster_summary_requires_at_least_two_cards():
    with pytest.raises(ValidationError):
        SuitClusterSummary(suit="swords", card_names=("Ace of Swords",), citations=(_citation(),))

    # two is fine
    SuitClusterSummary(
        suit="swords",
        card_names=("Ace of Swords", "Two of Swords"),
        citations=(_citation(), _citation(card_name="Two of Swords")),
    )


def test_suit_cluster_summary_rejects_an_unknown_suit():
    with pytest.raises(ValidationError):
        SuitClusterSummary(
            suit="chalices",
            card_names=("A", "B"),
            citations=(_citation(), _citation()),
        )


def test_relationships_defaults_to_no_clusters():
    relationships = Relationships(major_arcana_count=0, minor_arcana_count=3)
    assert relationships.same_suit_clusters == ()


def test_theme_strength_requires_at_least_one_citation():
    with pytest.raises(ValidationError):
        ThemeStrength(theme="clarity", count=1, citations=())


def test_deterministic_synthesis_requires_at_least_one_citation():
    with pytest.raises(ValidationError):
        _minimal_model(deterministic_synthesis=Explained(value="x", citations=()))


def test_interpretive_model_round_trips_new_fields_through_json():
    model = _minimal_model(
        card_interpretations=(
            _card_interpretation(),
            _card_interpretation(
                position_name="Near Future", semantic_role="near_future", position_order=2,
                card_name="Two of Swords", themes=("difficult_choices", "stalemate"),
            ),
        ),
        relationships=Relationships(
            same_suit_clusters=(
                SuitClusterSummary(
                    suit="swords",
                    card_names=("The Fool", "Two of Swords"),
                    citations=(_citation(), _citation(card_name="Two of Swords")),
                ),
            ),
            major_arcana_count=1,
            minor_arcana_count=1,
        ),
        theme_strength=(
            ThemeStrength(theme="new_beginnings", count=1, citations=(_citation(),)),
            ThemeStrength(theme="difficult_choices", count=1, citations=(_citation(card_name="Two of Swords"),)),
        ),
    )
    dumped = model.model_dump(mode="json")
    restored = InterpretiveModel.model_validate(dumped)
    assert restored == model
    assert len(restored.relationships.same_suit_clusters[0].card_names) == 2
