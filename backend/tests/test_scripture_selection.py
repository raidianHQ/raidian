"""Unit tests for the deterministic theme -> Scripture selection service
(app/services/scripture/selection.py), against hand-constructed
InterpretiveModel fixtures and directly-inserted ScriptureReference rows
-- independent of the real seeded reference-data content (except for the
explicit integration tests at the bottom), so most of these tests remain
stable even if that seed content changes.

Scripture Theme-Selection Design Audit, Option 2, as amended to allow a
ranked fallback, and further amended to allow every candidate with an
approved mapping to contribute (not just the first): Scripture selection
tries the reading's primary theme -- a Single Card reading's own
first-listed authored theme, or a multi-card reading's already-computed
central_issue -- then, in order, the InterpretiveModel's own
already-ranked `supporting_themes`, then `clarification`, `blocker`, and
`advice` (each an already-computed, structurally-selected single theme,
used only when present). Every candidate in that whole order that has an
approved mapping contributes its own references (capped per candidate by
_MAX_REFLECTIONS, deduplicated across candidates), not merely the first
one found -- so a reading touching several Scripture-mapped themes
returns all of them, grouped candidate-by-candidate in priority order.
`theme_strength` alone (a theme that is merely present in the reading,
not promoted to any of the fields above) is never consulted as a
candidate source. `_model()` below builds a two-card fixture by default
so most tests exercise the central_issue path (mirroring their
pre-existing intent); `_single_card_model()` builds a genuine one-card
fixture for the Single Card-specific tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.models import Orientation, ScriptureReference
from app.schemas.interpretive_model import (
    CardInterpretation,
    Citation,
    Explained,
    InterpretiveModel,
    Relationships,
    ThemeStrength,
)
from app.services.scripture.selection import _MAX_REFLECTIONS, _theme_candidates, select_scripture_reflections
from tests.interpretation_helpers import build_reading


def _citation(theme: str = "clarity", card_name: str = "Ace of Swords") -> Citation:
    return Citation(
        source_type="card_draw", card_draw_id=uuid4(), card_name=card_name,
        position_name="Situation", position_semantic_role="situation", contributing_theme=theme,
    )


def _model(theme_strength: tuple[ThemeStrength, ...] = (), **overrides) -> InterpretiveModel:
    """A two-card fixture: `card_interpretations` has 2 entries, so
    _theme_for_scripture() takes the central_issue path (never the
    Single Card path) -- central_issue.value tracks `theme_strength[0]`
    exactly as it did before this theme's selection became single-theme
    only, so every test below that only cares about the
    lookup/limit/no-fallback mechanics (not about which of the two paths
    is chosen) needs no further change.
    """
    central_theme = theme_strength[0].theme if theme_strength else "clarity"
    defaults: dict = dict(
        schema_version="1.0",
        engine_version="0.1.0-foundation",
        reference_data_version="a" * 64,
        generated_at=datetime.now(timezone.utc),
        central_question="What should I focus on?",
        spread_name="Three Card",
        card_interpretations=(
            CardInterpretation(
                position_name="Card One", semantic_role="general", position_order=1,
                card_name="Ace of Swords", orientation="upright",
                meaning_text="A breakthrough moment of mental clarity.",
                themes=(central_theme,), citation=_citation(central_theme),
            ),
            CardInterpretation(
                position_name="Card Two", semantic_role="general", position_order=2,
                card_name="Two of Cups", orientation="upright",
                meaning_text="A meeting of hearts and mutual regard.",
                themes=("connection",), citation=_citation("connection", card_name="Two of Cups"),
            ),
        ),
        relationships=Relationships(major_arcana_count=0, minor_arcana_count=2),
        theme_strength=theme_strength,
        central_issue=Explained(value=central_theme, citations=(_citation(central_theme),)),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(
            value=f"Together, the drawn cards center on {central_theme}.", citations=(_citation(central_theme),)
        ),
    )
    defaults.update(overrides)
    return InterpretiveModel(**defaults)


def _single_card_model(
    themes: tuple[str, ...] = ("hope", "renewal", "healing"), card_name: str = "The Star", **overrides
) -> InterpretiveModel:
    """A genuine one-card fixture -- `card_interpretations` has exactly 1
    entry, so _theme_for_scripture() takes the Single Card path
    (`themes[0]`), never central_issue.

    `central_issue` here mirrors the real engine's own behavior for a
    Single Card reading: every theme ties at count=1, so central_issue
    resolves to whichever theme sorts alphabetically first -- NOT
    `themes[0]`. Deliberately kept different from `themes[0]` by default
    (`themes` defaults to The Star's own real authored order, where
    "healing" sorts before "hope") so a test using this fixture actually
    proves Scripture follows `themes[0]`, not central_issue.
    """
    alphabetical_first = sorted(themes)[0]
    defaults: dict = dict(
        schema_version="1.0",
        engine_version="0.1.0-foundation",
        reference_data_version="a" * 64,
        generated_at=datetime.now(timezone.utc),
        central_question="What should I focus on?",
        spread_name="Single Card",
        card_interpretations=(
            CardInterpretation(
                position_name="The Card", semantic_role="general", position_order=1,
                card_name=card_name, orientation="upright",
                meaning_text="A quiet renewal after difficulty.",
                themes=themes, citation=_citation(themes[0], card_name=card_name),
            ),
        ),
        relationships=Relationships(major_arcana_count=1, minor_arcana_count=0),
        theme_strength=tuple(
            ThemeStrength(theme=t, count=1, citations=(_citation(t, card_name=card_name),))
            for t in sorted(themes)
        ),
        central_issue=Explained(
            value=alphabetical_first, citations=(_citation(alphabetical_first, card_name=card_name),)
        ),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(
            value=f"Together, the drawn cards center on {alphabetical_first}.",
            citations=(_citation(alphabetical_first, card_name=card_name),),
        ),
    )
    defaults.update(overrides)
    return InterpretiveModel(**defaults)


def _reference(session, theme: str, **overrides) -> ScriptureReference:
    defaults = dict(
        theme=theme, book="Philippians", chapter=4, verse_start=6, verse_end=7,
        reference_display="Philippians 4:6-7", translation="KJV",
        context_note="A note about the passage.", reflection_connection="A connection to the theme.",
    )
    defaults.update(overrides)
    reference = ScriptureReference(**defaults)
    session.add(reference)
    session.flush()
    return reference


# --- Scripture enabled / deterministic mapping ----------------------------------


def test_returns_a_reflection_for_a_theme_with_an_approved_mapping(db_session):
    _reference(db_session, "anxiety")
    citations = (_citation("anxiety"),)
    model = _model(
        theme_strength=(ThemeStrength(theme="anxiety", count=2, citations=citations),),
        central_issue=Explained(value="anxiety", citations=citations),
    )

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 1
    reflection = perspective.reflections[0]
    assert reflection.theme == "anxiety"
    assert reflection.reference_display == "Philippians 4:6-7"
    assert reflection.book == "Philippians"
    assert reflection.translation == "KJV"
    assert reflection.theme_citations == citations


def test_selection_is_deterministic_for_identical_input(db_session):
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=3, citations=(_citation("hope"),)),))

    first = select_scripture_reflections(db_session, model)
    second = select_scripture_reflections(db_session, model)

    assert first.model_dump(mode="json", exclude={"generated_at"}) == second.model_dump(
        mode="json", exclude={"generated_at"}
    )


def test_a_theme_can_have_more_than_one_approved_reference(db_session):
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    _reference(
        db_session, "hope", book="Jeremiah", chapter=29, verse_start=11, verse_end=None,
        reference_display="Jeremiah 29:11",
    )
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),))

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 2
    assert {r.reference_display for r in perspective.reflections} == {"Romans 15:13", "Jeremiah 29:11"}


def test_the_reflections_limit_still_applies_within_a_single_theme(db_session):
    """_MAX_REFLECTIONS bounds one candidate theme's own approved
    references -- a theme with more than this many approved rows still
    only contributes this many. This fixture has no other mapped
    candidate to also contribute (supporting_themes/clarification/
    blocker/advice are all unset), so the total here is also 3; see the
    "multiple candidates contribute" tests elsewhere in this file for
    proof that the cap is per-candidate, not an overall ceiling.
    """
    for book, chapter, verse in [("Psalms", 1, 1), ("Psalms", 23, 1), ("Proverbs", 3, 5), ("Isaiah", 41, 10)]:
        _reference(
            db_session, "hope", book=book, chapter=chapter, verse_start=verse, verse_end=None,
            reference_display=f"{book} {chapter}:{verse}",
        )
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=4, citations=(_citation("hope"),)),))
    assert _MAX_REFLECTIONS == 3  # this test's own assumption, made explicit

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 3
    assert {r.theme for r in perspective.reflections} == {"hope"}


# --- Ranked fallback through supporting_themes ------------------------------------


def test_a_theme_merely_present_in_theme_strength_is_not_a_fallback_source(db_session):
    """theme_strength lists every theme the reading touches at all;
    supporting_themes is the narrower, already-ranked subset Scripture
    actually falls back through. central theme "ambition" has no
    mapping, and "hope" is mapped and present in theme_strength -- but
    this fixture never promotes "hope" into supporting_themes (the
    default, matching _model()'s own un-overridden `supporting_themes`),
    so the result must still be empty.
    """
    _reference(db_session, "hope")  # mapped, but not the central theme, and not in supporting_themes
    theme_strength = (
        ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),  # central theme, unmapped
        ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),  # present, but not promoted
    )
    model = _model(theme_strength=theme_strength)
    assert model.central_issue.value == "ambition"
    assert model.supporting_themes == ()

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


def test_every_mapped_candidate_contributes_in_priority_order_when_all_are_mapped(db_session):
    """Proves priority order is preserved while every mapped candidate now
    contributes: when central_issue, supporting_themes, clarification,
    blocker, and advice are *all* individually mapped, every one of them
    shows up -- grouped candidate-by-candidate, in that same priority
    order -- rather than only the first (central_issue) winning outright
    and the rest being discarded.
    """
    _reference(db_session, "anxiety", reference_display="Philippians 4:6-7")
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    _reference(db_session, "grief", book="Psalms", chapter=34, verse_start=18, verse_end=None, reference_display="Psalm 34:18")
    _reference(db_session, "patience", book="James", chapter=1, verse_start=2, verse_end=4, reference_display="James 1:2-4")
    _reference(
        db_session, "relationships", book="1 Corinthians", chapter=13, verse_start=4, verse_end=7,
        reference_display="1 Corinthians 13:4-7",
    )
    model = _model(
        theme_strength=(ThemeStrength(theme="anxiety", count=2, citations=(_citation("anxiety"),)),),
        supporting_themes=(Explained(value="hope", citations=(_citation("hope"),)),),
        clarification=Explained(value="grief", citations=(_citation("grief"),)),
        blocker=Explained(value="patience", citations=(_citation("patience"),)),
        advice=Explained(value="relationships", citations=(_citation("relationships"),)),
    )
    assert model.central_issue.value == "anxiety"

    perspective = select_scripture_reflections(db_session, model)

    assert [r.theme for r in perspective.reflections] == ["anxiety", "hope", "grief", "patience", "relationships"]


def test_falls_back_to_a_mapped_supporting_theme_when_central_issue_is_unmapped(db_session):
    """The fix under test: central_issue "ambition" has no mapping;
    supporting_themes ranks an unmapped theme ("recognition") ahead of a
    mapped one ("hope") -- selection must skip the unmapped entry and
    use the first supporting theme that does have an approved reference,
    respecting supporting_themes' own existing rank order.
    """
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    model = _model(
        theme_strength=(
            ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),
            ThemeStrength(theme="recognition", count=1, citations=(_citation("recognition"),)),
            ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),
        ),
        supporting_themes=(
            Explained(value="recognition", citations=(_citation("recognition"),)),
            Explained(value="hope", citations=(_citation("hope"),)),
        ),
    )
    assert model.central_issue.value == "ambition"

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 1
    assert perspective.reflections[0].theme == "hope"
    assert perspective.reflections[0].reference_display == "Romans 15:13"


def test_no_reflection_when_neither_central_issue_nor_any_supporting_theme_has_a_mapping(db_session):
    model = _model(
        theme_strength=(
            ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),
            ThemeStrength(theme="recognition", count=1, citations=(_citation("recognition"),)),
            ThemeStrength(theme="momentum", count=1, citations=(_citation("momentum"),)),
        ),
        supporting_themes=(
            Explained(value="recognition", citations=(_citation("recognition"),)),
            Explained(value="momentum", citations=(_citation("momentum"),)),
        ),
    )

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


# --- Semantic relation cluster (_RELATED_THEMES / _theme_cluster) ----------------


def test_theme_cluster_includes_a_curated_related_theme():
    from app.services.scripture.selection import _theme_cluster

    assert _theme_cluster("discernment") == ("discernment", "clarity")
    assert _theme_cluster("clarity") == ("clarity", "discernment")


def test_theme_cluster_is_just_the_theme_itself_when_nothing_is_curated():
    from app.services.scripture.selection import _theme_cluster

    assert _theme_cluster("hope") == ("hope",)
    assert _theme_cluster("anxiety") == ("anxiety",)


def test_related_theme_pairs_reference_real_vocabulary_tags():
    """Guards against a future _RELATED_THEMES edit introducing a typo'd
    or invented tag -- every theme named on either side of a curated
    relation must already exist verbatim in the real, closed
    theme_vocabulary.yaml, exactly like a scripture_references.yaml
    theme must (app/seed/loader.py's own validation).
    """
    from app.seed.loader import load_theme_vocabulary
    from app.services.scripture.selection import _RELATED_THEMES

    vocabulary = load_theme_vocabulary()
    for theme, related in _RELATED_THEMES.items():
        assert theme in vocabulary
        for other in related:
            assert other in vocabulary


def test_a_curated_related_theme_contributes_its_own_real_reference_not_a_fabricated_one(db_session):
    """A theme with a curated relation (discernment -> clarity) merges in
    the related theme's own already-approved row(s) -- real content a
    human reviewer added to scripture_references.yaml, never a synthesized
    or placeholder reference. Each returned reflection's own `theme` field
    truthfully names which approved tag it came from.
    """
    _reference(
        db_session, "discernment", book="1 Kings", chapter=3, verse_start=9, verse_end=None,
        reference_display="1 Kings 3:9",
    )
    _reference(
        db_session, "clarity", book="Psalms", chapter=119, verse_start=105, verse_end=None,
        reference_display="Psalm 119:105",
    )
    model = _model(theme_strength=(ThemeStrength(theme="discernment", count=1, citations=(_citation("discernment"),)),))

    perspective = select_scripture_reflections(db_session, model)

    assert {r.theme for r in perspective.reflections} == {"discernment", "clarity"}
    assert {r.reference_display for r in perspective.reflections} == {"1 Kings 3:9", "Psalm 119:105"}
    for reflection in perspective.reflections:
        assert reflection.theme_citations  # every reflection traces to real reading evidence


def test_a_theme_without_a_curated_relation_does_not_pull_in_an_unrelated_themes_reference(db_session):
    """Existing behavior guard: a theme with no curated relation (e.g.
    "anxiety") must only ever match its own exact tag -- an approved
    reference under a different, unrelated theme ("hope") must never be
    pulled in just because it also happens to have a mapping.
    """
    _reference(db_session, "anxiety", reference_display="Philippians 4:6-7")
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    model = _model(theme_strength=(ThemeStrength(theme="anxiety", count=1, citations=(_citation("anxiety"),)),))

    perspective = select_scripture_reflections(db_session, model)

    assert {r.theme for r in perspective.reflections} == {"anxiety"}


def test_discernment_candidate_still_returns_nothing_when_neither_it_nor_clarity_is_mapped(db_session):
    model = _model(theme_strength=(ThemeStrength(theme="discernment", count=1, citations=(_citation("discernment"),)),))

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


def test_a_reference_reached_by_two_different_candidates_clusters_is_not_duplicated(db_session):
    """Deduplication across *candidates*, not just within one candidate's
    own cluster: central_issue "discernment" pulls in clarity's reference
    via its curated relation, and clarity is *also*, separately, ranked as
    its own supporting theme -- a real, plausible combination since a
    reading can independently promote both a card's primary theme
    (discernment) and its secondary theme (clarity). Clarity's own
    reference must appear exactly once, not twice, even though two
    different candidates' clusters both resolve to it.
    """
    _reference(
        db_session, "discernment", book="1 Kings", chapter=3, verse_start=9, verse_end=None,
        reference_display="1 Kings 3:9",
    )
    _reference(
        db_session, "clarity", book="Psalms", chapter=119, verse_start=105, verse_end=None,
        reference_display="Psalm 119:105",
    )
    model = _model(
        theme_strength=(ThemeStrength(theme="discernment", count=2, citations=(_citation("discernment"),)),),
        supporting_themes=(Explained(value="clarity", citations=(_citation("clarity"),)),),
    )
    assert model.central_issue.value == "discernment"

    perspective = select_scripture_reflections(db_session, model)

    assert [r.reference_display for r in perspective.reflections] == ["1 Kings 3:9", "Psalm 119:105"]
    assert len(perspective.reflections) == 2  # not 3 -- clarity's row is not repeated


# --- Fallback through clarification / blocker / advice ---------------------------


def test_production_scenario_falls_back_to_clarification_when_nothing_earlier_matches(db_session):
    """The exact reported production scenario (reading
    00626797-39c9-4b12-bb7e-a5582293e135): central_issue "momentum" and
    every ranked supporting theme (recognition, assertiveness,
    collaboration) are unmapped, but clarification "grief" is an
    approved Scripture theme and must now be selected -- with its own
    citations (not theme_strength's), since "grief" here is not itself a
    theme_strength entry.
    """
    _reference(db_session, "grief", book="Psalms", chapter=34, verse_start=18, verse_end=None, reference_display="Psalm 34:18")
    grief_citations = (_citation("grief", card_name="Three of Swords"),)
    model = _model(
        theme_strength=(
            ThemeStrength(theme="momentum", count=2, citations=(_citation("momentum"),)),
            ThemeStrength(theme="recognition", count=2, citations=(_citation("recognition"),)),
            ThemeStrength(theme="assertiveness", count=1, citations=(_citation("assertiveness"),)),
            ThemeStrength(theme="collaboration", count=1, citations=(_citation("collaboration"),)),
        ),
        supporting_themes=(
            Explained(value="recognition", citations=(_citation("recognition"),)),
            Explained(value="assertiveness", citations=(_citation("assertiveness"),)),
            Explained(value="collaboration", citations=(_citation("collaboration"),)),
        ),
        clarification=Explained(value="grief", citations=grief_citations),
        blocker=Explained(value="intuition", citations=(_citation("intuition"),)),
        advice=Explained(value="strategy", citations=(_citation("strategy"),)),
    )
    assert model.central_issue.value == "momentum"

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 1
    reflection = perspective.reflections[0]
    assert reflection.theme == "grief"
    assert reflection.reference_display == "Psalm 34:18"
    assert reflection.theme_citations == grief_citations


def test_supporting_theme_and_clarification_both_contribute_supporting_theme_first(db_session):
    """A ranked supporting theme is still tried before clarification, and
    both now contribute when both are mapped: central_issue is unmapped
    ("ambition"), so the supporting theme's references come first,
    followed by clarification's -- clarification is no longer discarded
    just because an earlier candidate also matched.
    """
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    _reference(db_session, "grief", book="Psalms", chapter=34, verse_start=18, verse_end=None, reference_display="Psalm 34:18")
    model = _model(
        theme_strength=(
            ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),
            ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),
        ),
        supporting_themes=(Explained(value="hope", citations=(_citation("hope"),)),),
        clarification=Explained(value="grief", citations=(_citation("grief"),)),
    )
    assert model.central_issue.value == "ambition"

    perspective = select_scripture_reflections(db_session, model)

    assert [r.theme for r in perspective.reflections] == ["hope", "grief"]


def test_clarification_is_used_when_central_issue_and_supporting_themes_are_unmapped(db_session):
    _reference(db_session, "grief", book="Psalms", chapter=34, verse_start=18, verse_end=None, reference_display="Psalm 34:18")
    model = _model(
        theme_strength=(
            ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),
            ThemeStrength(theme="recognition", count=1, citations=(_citation("recognition"),)),
        ),
        supporting_themes=(Explained(value="recognition", citations=(_citation("recognition"),)),),
        clarification=Explained(value="grief", citations=(_citation("grief"),)),
    )
    assert model.central_issue.value == "ambition"

    perspective = select_scripture_reflections(db_session, model)

    assert {r.theme for r in perspective.reflections} == {"grief"}


def test_blocker_is_used_when_central_issue_supporting_themes_and_clarification_are_unmapped(db_session):
    _reference(db_session, "patience", book="James", chapter=1, verse_start=2, verse_end=4, reference_display="James 1:2-4")
    model = _model(
        theme_strength=(ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),),
        supporting_themes=(Explained(value="recognition", citations=(_citation("recognition"),)),),
        clarification=Explained(value="momentum", citations=(_citation("momentum"),)),
        blocker=Explained(value="patience", citations=(_citation("patience"),)),
    )
    assert model.central_issue.value == "ambition"

    perspective = select_scripture_reflections(db_session, model)

    assert {r.theme for r in perspective.reflections} == {"patience"}


def test_advice_is_used_when_every_earlier_candidate_is_unmapped(db_session):
    _reference(
        db_session, "relationships", book="1 Corinthians", chapter=13, verse_start=4, verse_end=7,
        reference_display="1 Corinthians 13:4-7",
    )
    model = _model(
        theme_strength=(ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),),
        supporting_themes=(Explained(value="recognition", citations=(_citation("recognition"),)),),
        clarification=Explained(value="momentum", citations=(_citation("momentum"),)),
        blocker=Explained(value="assertiveness", citations=(_citation("assertiveness"),)),
        advice=Explained(value="relationships", citations=(_citation("relationships"),)),
    )
    assert model.central_issue.value == "ambition"

    perspective = select_scripture_reflections(db_session, model)

    assert {r.theme for r in perspective.reflections} == {"relationships"}


def test_no_reflection_when_nothing_in_the_entire_candidate_hierarchy_has_a_mapping(db_session):
    model = _model(
        theme_strength=(ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),),
        supporting_themes=(Explained(value="recognition", citations=(_citation("recognition"),)),),
        clarification=Explained(value="momentum", citations=(_citation("momentum"),)),
        blocker=Explained(value="assertiveness", citations=(_citation("assertiveness"),)),
        advice=Explained(value="collaboration", citations=(_citation("collaboration"),)),
    )

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


def test_theme_candidates_deduplicates_preserving_first_occurrence_order():
    """A theme repeated across stages (a supporting theme re-appearing as
    central_issue, clarification re-appearing as a supporting theme,
    advice repeating blocker) must appear exactly once in
    _theme_candidates(), at its first-occurrence position -- proving
    duplicates are collapsed without disturbing priority order.
    """
    model = _model(
        theme_strength=(ThemeStrength(theme="ambition", count=2, citations=(_citation("ambition"),)),),
        supporting_themes=(
            Explained(value="hope", citations=(_citation("hope"),)),
            Explained(value="ambition", citations=(_citation("ambition"),)),  # duplicate of central_issue
        ),
        clarification=Explained(value="hope", citations=(_citation("hope"),)),  # duplicate of a supporting theme
        blocker=Explained(value="grief", citations=(_citation("grief"),)),
        advice=Explained(value="grief", citations=(_citation("grief"),)),  # duplicate of blocker
    )
    assert model.central_issue.value == "ambition"

    assert _theme_candidates(model) == ("ambition", "hope", "grief")


def test_empty_theme_strength_produces_no_reflections(db_session):
    model = _model(theme_strength=())

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


# --- Single Card: the card's own first authored theme, not central_issue --------


def test_single_card_reading_uses_the_cards_first_authored_theme_not_central_issue(db_session):
    _reference(db_session, "hope", book="Romans", chapter=15, verse_start=13, verse_end=None, reference_display="Romans 15:13")
    model = _single_card_model(themes=("hope", "renewal", "healing"), card_name="The Star")

    # This fixture's own central_issue intentionally differs from
    # themes[0] (mirroring the real engine's alphabetical tie-break among
    # The Star's count=1 themes) -- proving Scripture is NOT driven by
    # central_issue for a Single Card reading.
    assert model.central_issue.value == "healing"
    assert model.card_interpretations[0].themes[0] == "hope"

    perspective = select_scripture_reflections(db_session, model)

    assert len(perspective.reflections) == 1
    assert perspective.reflections[0].theme == "hope"


def test_single_card_reading_returns_no_reflection_when_its_first_theme_is_unmapped(db_session):
    # No ScriptureReference rows seeded at all in this isolated test
    # session -- themes[0] ("hope") is unmapped here, and there must be
    # no fallback to "renewal" or "healing" even though they're also
    # this card's own themes.
    model = _single_card_model(themes=("hope", "renewal", "healing"), card_name="The Star")

    perspective = select_scripture_reflections(db_session, model)

    assert perspective.reflections == ()


# --- Scripture layer does not alter deterministic tarot interpretation ---------


def test_does_not_mutate_the_source_interpretive_model(db_session):
    _reference(db_session, "hope")
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),))
    before = model.model_dump(mode="json")

    select_scripture_reflections(db_session, model)

    assert model.model_dump(mode="json") == before


def test_writes_no_rows_to_the_database(db_session):
    _reference(db_session, "hope")
    before_count = len(db_session.execute(select(ScriptureReference)).scalars().all())
    model = _model(theme_strength=(ThemeStrength(theme="hope", count=1, citations=(_citation("hope"),)),))

    select_scripture_reflections(db_session, model)

    after_count = len(db_session.execute(select(ScriptureReference)).scalars().all())
    assert after_count == before_count


# --- Guardrail disclaimer --------------------------------------------------------


def test_disclaimer_is_always_present_and_disclaims_divine_endorsement(db_session):
    # No ScriptureReference rows needed -- the disclaimer is attached
    # regardless of whether any reflection was found.
    model = _model(theme_strength=())

    perspective = select_scripture_reflections(db_session, model)

    assert "God's will" in perspective.disclaimer
    assert "not" in perspective.disclaimer.lower()


# --- Real end-to-end integration (real engine + real seeded scripture data) ----


def test_integration_single_card_uses_the_stars_own_first_theme(seeded_session):
    """The Star's real authored themes are hope/renewal/healing
    (primary_themes) then inner_strength (secondary) -- all tied at
    count=1 for a Single Card reading, so central_issue resolves to
    "healing" (alphabetically first). Scripture must still use "hope"
    (themes[0]), which has a real approved mapping in the seeded dataset.
    """
    from app.services.interpretation.engine import interpret

    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "The Star", Orientation.UPRIGHT)],
    )
    model = interpret(reading, seeded_session)

    assert model.central_issue.value == "healing"
    assert model.card_interpretations[0].themes[0] == "hope"

    perspective = select_scripture_reflections(seeded_session, model)

    assert {r.theme for r in perspective.reflections} == {"hope"}


def test_integration_discernment_produces_multiple_related_references(seeded_session):
    """The exact reported bug: a Single Card reading of Queen of Swords
    establishes "discernment" as its strongest theme (primary_themes[0]
    in rider_waite_smith/swords.yaml), and Scripture must not come back
    empty for it. It also proves the semantic-relation cluster end to
    end against the real seeded dataset: Queen of Swords' own authored
    content already pairs `discernment` (primary) with `clarity`
    (secondary) on the very same card, mirroring
    selection.py's `_RELATED_THEMES["discernment"] == ("clarity",)`, so
    the returned reflections legitimately span both real, approved theme
    tags -- not just the one exact string "discernment" -- without any
    fuzzy/keyword matching involved.
    """
    from app.services.interpretation.engine import interpret

    reading = build_reading(
        seeded_session, spread_name="Single Card",
        draws=[("The Card", "Queen of Swords", Orientation.UPRIGHT)],
    )
    model = interpret(reading, seeded_session)

    assert model.card_interpretations[0].themes[0] == "discernment"

    perspective = select_scripture_reflections(seeded_session, model)

    themes_present = {r.theme for r in perspective.reflections}
    assert themes_present == {"discernment", "clarity"}
    assert len(perspective.reflections) >= 2
    # Every reflection traces back to real evidence in this reading, never
    # a fabricated citation.
    for reflection in perspective.reflections:
        assert len(reflection.theme_citations) >= 1


def test_integration_multi_card_falls_back_to_a_mapped_supporting_theme(seeded_session):
    """The real Celtic Cross fixture used throughout this project's own
    test suite computes central_issue="inner_guidance", which has no
    approved Scripture mapping -- but this same reading's own
    already-ranked supporting_themes includes "patience" (mapped).
    Scripture must now surface "patience"'s approved reference, proving
    the fallback works end-to-end against the real engine and the real
    seeded reference data, not just hand-built fixtures.
    """
    from app.services.interpretation.engine import interpret

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
    model = interpret(reading, seeded_session)

    assert model.central_issue.value == "inner_guidance"
    assert any(t.value == "patience" for t in model.supporting_themes)  # ranked fallback candidate

    perspective = select_scripture_reflections(seeded_session, model)

    assert {r.theme for r in perspective.reflections} == {"patience"}
