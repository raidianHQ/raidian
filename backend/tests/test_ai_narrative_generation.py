"""Unit tests for app/services/ai_narrative/generation.py -- the module
that builds prompts, calls the (fake) Reflection Engine, and validates the
result. No test here makes a real AI provider call
(tests/reflection_engine_fakes.py::FakeReflectionEngineClient stands in for
one) -- see Documentation/AI_NARRATIVE_LAYER_DESIGN.md Section 4.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.schemas.ai_narrative import DeterministicReadingContext
from app.schemas.interpretive_model import (
    CardInterpretation,
    Citation,
    Explained,
    InterpretiveModel,
    Relationships,
    ThemeStrength,
)
from app.schemas.scripture_model import ScripturalPerspective, ScriptureReflection
from app.services.ai_narrative.generation import (
    AINarrativeProviderError,
    AINarrativeValidationError,
    generate_ai_narrative,
)
from app.services.reflection_engine.client import ReflectionEngineNotConfiguredError, ReflectionEngineRequestError
from tests.reflection_engine_fakes import FakeReflectionEngineClient, valid_content_with


def _citation(theme: str = "clarity", card_name: str = "Ace of Swords") -> Citation:
    return Citation(
        source_type="card_draw", card_draw_id=uuid4(), card_name=card_name,
        position_name="Situation", position_semantic_role="situation", contributing_theme=theme,
    )


def _model(**overrides) -> InterpretiveModel:
    defaults: dict = dict(
        schema_version="1.0", engine_version="0.1.0-foundation", reference_data_version="a" * 64,
        generated_at=datetime.now(timezone.utc),
        central_question="Should I take the new job offer?",
        spread_name="Single Card",
        card_interpretations=(
            CardInterpretation(
                position_name="The Card", semantic_role="general", position_order=1,
                card_name="Ace of Swords", orientation="upright",
                meaning_text="A breakthrough moment of mental clarity.",
                themes=("clarity",), citation=_citation(),
            ),
        ),
        relationships=Relationships(major_arcana_count=0, minor_arcana_count=1),
        theme_strength=(ThemeStrength(theme="clarity", count=1, citations=(_citation(),)),),
        central_issue=Explained(value="clarity", citations=(_citation(),)),
        evidence_strength="unresolved",
        deterministic_synthesis=Explained(value="Clarity is the focus.", citations=(_citation(),)),
    )
    defaults.update(overrides)
    return InterpretiveModel(**defaults)


def _scripture() -> ScripturalPerspective:
    reflection = ScriptureReflection(
        theme="patience", book="James", chapter=1, verse_start=2, verse_end=4,
        reference_display="James 1:2-4", translation="KJV",
        context_note="A note.", reflection_connection="A connection.",
        theme_citations=(_citation("patience"),),
    )
    return ScripturalPerspective(
        schema_version="1.0", generated_at=datetime.now(timezone.utc),
        source_schema_version="1.0", reflections=(reflection,),
    )


# --- Successful generation, correct data supplied ---------------------------------


def test_generate_ai_narrative_returns_a_validated_response_on_success():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient()

    response = generate_ai_narrative(client, context, provider="anthropic", model="claude-test")

    assert response.provider == "anthropic"
    assert response.model == "claude-test"
    assert response.source_schema_version == "1.0"
    assert len(response.key_themes) >= 1
    assert len(response.reflection_questions) >= 1
    assert response.scriptural_reflection is None


def test_the_ai_layer_is_supplied_the_actual_deterministic_reading_data():
    model = _model(central_question="Should I move to a new city?")
    context = DeterministicReadingContext(interpretation=model, scripture=None)
    client = FakeReflectionEngineClient()

    generate_ai_narrative(client, context, provider="anthropic", model="claude-test")

    assert len(client.calls) == 1
    user_prompt = client.calls[0]["user_prompt"]
    assert "Should I move to a new city?" in user_prompt
    assert "Ace of Swords" in user_prompt
    assert "clarity" in user_prompt
    # Never raw Card Draws / DB identifiers -- only the already-serialized
    # InterpretiveModel content (Product Spec Section 12).
    payload = json.loads(user_prompt.split("READING DATA (JSON):\n\n")[1])
    assert payload["interpretation"]["central_question"] == "Should I move to a new city?"
    assert payload["scripture"] is None


def test_system_prompt_carries_the_safety_constraints():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient()

    generate_ai_narrative(client, context, provider="anthropic", model="claude-test")

    system_prompt = client.calls[0]["system_prompt"]
    assert "destiny" in system_prompt.lower()
    assert "God's will" in system_prompt or "divine revelation" in system_prompt.lower()


# --- Scripture: opt-in only, and never invented ------------------------------------


def test_scripture_disabled_context_is_not_sent_and_response_must_omit_it():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(response_text=json.dumps(valid_content_with(scriptural_reflection=None)))

    response = generate_ai_narrative(client, context, provider="anthropic", model="claude-test")

    assert response.scriptural_reflection is None
    assert '"scripture": null' in client.calls[0]["user_prompt"]


def test_scripture_enabled_is_sent_and_may_appear_in_the_response():
    context = DeterministicReadingContext(interpretation=_model(), scripture=_scripture())
    client = FakeReflectionEngineClient(
        response_text=json.dumps(valid_content_with(scriptural_reflection="James 1:2-4 speaks to patience here."))
    )

    response = generate_ai_narrative(client, context, provider="anthropic", model="claude-test")

    assert response.scriptural_reflection == "James 1:2-4 speaks to patience here."
    assert "James" in client.calls[0]["user_prompt"]


def test_ai_cannot_introduce_a_scripture_reflection_that_was_not_supplied():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(
        response_text=json.dumps(valid_content_with(scriptural_reflection="A fabricated verse about clarity."))
    )

    with pytest.raises(AINarrativeValidationError):
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")


# --- Malformed responses are rejected safely ---------------------------------------


def test_non_json_response_is_rejected():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(response_text="Sorry, here is your reading in plain prose instead.")

    with pytest.raises(AINarrativeValidationError):
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")


def test_response_missing_a_required_field_is_rejected():
    content = valid_content_with()
    del content["opening_summary"]
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(response_text=json.dumps(content))

    with pytest.raises(AINarrativeValidationError):
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")


def test_response_with_an_unexpected_extra_field_is_rejected():
    content = valid_content_with(unexpected_field="should not be here")
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(response_text=json.dumps(content))

    with pytest.raises(AINarrativeValidationError):
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")


def test_response_with_empty_key_themes_is_rejected():
    content = valid_content_with(key_themes=[])
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(response_text=json.dumps(content))

    with pytest.raises(AINarrativeValidationError):
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")


def test_response_wrapped_in_a_markdown_fence_is_still_parsed():
    content = valid_content_with()
    fenced = f"```json\n{json.dumps(content)}\n```"
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(response_text=fenced)

    response = generate_ai_narrative(client, context, provider="anthropic", model="claude-test")

    assert response.opening_summary == content["opening_summary"]


# --- Provider failures ---------------------------------------------------------------


def test_provider_request_failure_raises_ai_narrative_provider_error():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(error_to_raise=ReflectionEngineRequestError("network unreachable"))

    with pytest.raises(AINarrativeProviderError) as excinfo:
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")
    assert isinstance(excinfo.value.__cause__, ReflectionEngineRequestError)


def test_not_configured_failure_raises_ai_narrative_provider_error_with_that_cause():
    context = DeterministicReadingContext(interpretation=_model(), scripture=None)
    client = FakeReflectionEngineClient(error_to_raise=ReflectionEngineNotConfiguredError("no api key"))

    with pytest.raises(AINarrativeProviderError) as excinfo:
        generate_ai_narrative(client, context, provider="anthropic", model="claude-test")
    assert isinstance(excinfo.value.__cause__, ReflectionEngineNotConfiguredError)
