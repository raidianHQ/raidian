"""Focused unit tests for each individual pipeline stage module (stages
1-2, 3-4, 5, 7, 8, 9, 10-11). Stage 6 (compounds) has its own dedicated
file, test_compound_rules.py.
"""

from app.models import Orientation, SemanticRole
from app.services.interpretation.compounds import match_compounds
from app.services.interpretation.context import build_reading_context
from app.services.interpretation.contradictions import detect_contradictions
from app.services.interpretation.evidence import identify_uncertainty, score_evidence_strength
from app.services.interpretation.meanings import resolve_meanings, score_theme_strength
from app.services.interpretation.relationships import evaluate_relationships
from app.services.interpretation.relevance import apply_position_relevance, apply_question_relevance
from app.services.interpretation.structure import evaluate_structure
from app.services.interpretation.trajectory import derive_trajectory
from tests.interpretation_helpers import build_reading


def _three_card_context(session, *, domain=None):
    reading = build_reading(
        session, spread_name="Three Card",
        draws=[
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Present Situation", "Ace of Swords", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.REVERSED),
        ],
        question_domain=domain,
    )
    return build_reading_context(reading)


# --- Stage 1-2: meanings ---------------------------------------------


def test_resolve_meanings_keys_by_card_draw_id(seeded_session):
    ctx = _three_card_context(seeded_session)
    meanings = resolve_meanings(ctx)

    assert set(meanings.keys()) == {d.card_draw_id for d in ctx.draws}
    for draw in ctx.draws:
        assert meanings[draw.card_draw_id] == draw.meaning_text


def test_score_theme_strength_orders_by_count_desc_then_name_asc(seeded_session):
    # Three cards each contribute several themes; no tag should repeat
    # often enough here to test a tie deterministically without relying on
    # exact content, so just assert the ordering invariant holds.
    ctx = _three_card_context(seeded_session)
    scores = score_theme_strength(ctx)

    counts = [s.count for s in scores]
    assert counts == sorted(counts, reverse=True)

    # within equal counts, alphabetical
    for i in range(len(scores) - 1):
        if scores[i].count == scores[i + 1].count:
            assert scores[i].theme < scores[i + 1].theme


def test_score_theme_strength_is_deterministic(seeded_session):
    ctx = _three_card_context(seeded_session)
    assert score_theme_strength(ctx) == score_theme_strength(ctx)


def test_every_theme_score_has_at_least_one_citation(seeded_session):
    ctx = _three_card_context(seeded_session)
    for score in score_theme_strength(ctx):
        assert len(score.citations) == score.count


# --- Stage 3-4: relevance (explicit no-ops) ---------------------------


def test_question_relevance_is_a_no_op_regardless_of_domain(seeded_session):
    ctx_with_domain = _three_card_context(seeded_session, domain="career")
    scores = score_theme_strength(ctx_with_domain)
    assert apply_question_relevance(scores, ctx_with_domain) == scores


def test_question_relevance_is_a_no_op_when_domain_is_none(seeded_session):
    ctx = _three_card_context(seeded_session, domain=None)
    scores = score_theme_strength(ctx)
    assert apply_question_relevance(scores, ctx) == scores


def test_position_relevance_is_a_no_op(seeded_session):
    ctx = _three_card_context(seeded_session)
    scores = score_theme_strength(ctx)
    assert apply_position_relevance(scores, ctx) == scores


# --- Stage 5: relationships --------------------------------------------


def test_relationships_detects_same_suit_cluster(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),
            ("Present Situation", "Two of Swords", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    relationships = evaluate_relationships(ctx)

    assert len(relationships.same_suit_clusters) == 1
    cluster = relationships.same_suit_clusters[0]
    assert cluster.suit.value == "swords"
    assert len(cluster.draws) == 2


def test_relationships_no_cluster_when_suits_dont_repeat(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Three Card",
        draws=[
            ("Recent Past", "Ace of Swords", Orientation.UPRIGHT),
            ("Present Situation", "Ace of Cups", Orientation.UPRIGHT),
            ("Near Future", "Ace of Wands", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    relationships = evaluate_relationships(ctx)
    assert relationships.same_suit_clusters == ()


def test_relationships_counts_major_arcana_density(seeded_session):
    ctx = _three_card_context(seeded_session)  # Fool + Ace of Swords + Moon = 2 majors
    relationships = evaluate_relationships(ctx)
    assert relationships.major_arcana_count == 2


# --- Stage 7: structure --------------------------------------------------


def test_structure_finds_advice_and_clarifier_in_celtic_cross(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Celtic Cross",
        draws=[
            ("Situation", "Ace of Swords", Orientation.UPRIGHT),
            ("Challenge", "The Tower", Orientation.UPRIGHT),
            ("Foundation", "The Hermit", Orientation.UPRIGHT),
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Crown", "The Star", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
            ("Approach", "The Chariot", Orientation.UPRIGHT),
            ("External Influences", "The Empress", Orientation.UPRIGHT),
            ("Advice", "The High Priestess", Orientation.UPRIGHT),
            ("Outcome", "Strength", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    structure = evaluate_structure(ctx)

    assert structure.advice.card_name == "The High Priestess"
    assert structure.advice_clarifier.card_name == "Strength"
    assert structure.has_advice_clarifier_pairing is True
    assert structure.situation.card_name == "Ace of Swords"
    assert structure.blocker.card_name == "The Tower"
    assert structure.has_situation_blocker_adjacency is True


def test_structure_fields_are_none_when_spread_lacks_the_role(seeded_session):
    ctx = _three_card_context(seeded_session)  # no advice/advice_clarifier/blocker positions
    structure = evaluate_structure(ctx)

    assert structure.advice is None
    assert structure.advice_clarifier is None
    assert structure.blocker is None
    assert structure.has_advice_clarifier_pairing is False
    assert structure.has_situation_blocker_adjacency is False


# --- Stage 8: trajectory --------------------------------------------------


def test_trajectory_populated_for_three_card_spread(seeded_session):
    ctx = _three_card_context(seeded_session)
    trajectory = derive_trajectory(ctx)

    assert trajectory is not None
    assert [step.card_name for step in trajectory.value.arc] == ["The Fool", "Ace of Swords", "The Moon"]
    assert [step.semantic_role for step in trajectory.value.arc] == ["recent_past", "situation", "near_future"]


def test_trajectory_is_none_for_single_card_spread(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "The Fool", Orientation.UPRIGHT)],
    )
    ctx = build_reading_context(reading)
    assert derive_trajectory(ctx) is None


def test_trajectory_uses_semantic_role_order_not_position_order(seeded_session):
    """Celtic Cross: Recent Past is position_order 4, Situation is order 1,
    Near Future is order 6 -- the trajectory must read
    recent_past -> situation -> near_future regardless.
    """
    reading = build_reading(
        seeded_session, spread_name="Celtic Cross",
        draws=[
            ("Situation", "Ace of Swords", Orientation.UPRIGHT),
            ("Challenge", "The Tower", Orientation.UPRIGHT),
            ("Foundation", "The Hermit", Orientation.UPRIGHT),
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Crown", "The Star", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
            ("Approach", "The Chariot", Orientation.UPRIGHT),
            ("External Influences", "The Empress", Orientation.UPRIGHT),
            ("Advice", "The High Priestess", Orientation.UPRIGHT),
            ("Outcome", "Strength", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    trajectory = derive_trajectory(ctx)

    assert [step.card_name for step in trajectory.value.arc] == ["The Fool", "Ace of Swords", "The Moon"]


# --- Stage 9: contradictions (conservative, foundation-stage) -----------


def test_contradictions_is_always_empty_in_this_foundation_phase(seeded_session):
    ctx = _three_card_context(seeded_session)
    matches = match_compounds(ctx)
    assert detect_contradictions(ctx, matches) == ()


# --- Stage 10-11: uncertainty + evidence strength -----------------------


def test_uncertainty_and_evidence_strength_for_a_thin_spread(seeded_session):
    """Single Card spread: no trajectory, no advice, no blocker, likely no
    compound match -- should read as unresolved with several uncertainty
    statements.
    """
    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "Four of Wands", Orientation.UPRIGHT)],
    )
    ctx = build_reading_context(reading)
    structure = evaluate_structure(ctx)
    trajectory = derive_trajectory(ctx)
    matches = match_compounds(ctx)

    uncertainty = identify_uncertainty(structure, trajectory, matches)
    strength = score_evidence_strength(structure, trajectory, matches)

    assert len(uncertainty) >= 3  # no trajectory, no advice, no blocker, (likely) no compound match
    assert strength == "unresolved"


def test_uncertainty_and_evidence_strength_for_a_rich_spread(seeded_session):
    reading = build_reading(
        seeded_session, spread_name="Celtic Cross",
        draws=[
            ("Situation", "Ace of Swords", Orientation.UPRIGHT),
            ("Challenge", "The Tower", Orientation.UPRIGHT),
            ("Foundation", "The Hermit", Orientation.UPRIGHT),
            ("Recent Past", "The Fool", Orientation.UPRIGHT),
            ("Crown", "The Star", Orientation.UPRIGHT),
            ("Near Future", "The Moon", Orientation.UPRIGHT),
            ("Approach", "The Chariot", Orientation.UPRIGHT),
            ("External Influences", "The Empress", Orientation.UPRIGHT),
            ("Advice", "The High Priestess", Orientation.UPRIGHT),
            ("Outcome", "Strength", Orientation.UPRIGHT),
        ],
    )
    ctx = build_reading_context(reading)
    structure = evaluate_structure(ctx)
    trajectory = derive_trajectory(ctx)
    matches = match_compounds(ctx)

    uncertainty = identify_uncertainty(structure, trajectory, matches)
    strength = score_evidence_strength(structure, trajectory, matches)

    assert uncertainty == ()  # trajectory + advice/clarifier + blocker + 2 compound matches, all present
    assert strength == "strong"


def test_evidence_strength_is_deterministic(seeded_session):
    ctx = _three_card_context(seeded_session)
    structure = evaluate_structure(ctx)
    trajectory = derive_trajectory(ctx)
    matches = match_compounds(ctx)

    assert score_evidence_strength(structure, trajectory, matches) == score_evidence_strength(
        structure, trajectory, matches
    )
