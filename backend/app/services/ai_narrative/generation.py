"""Runs one Reflection Engine (ADR-0005) generation and validates its
result. The only module in this project that constructs a prompt or
parses provider output -- app/api/ai_narrative.py and
reading_orchestration.py never touch either.

Two distinct failure modes, kept as separate exception types so a caller
(and a test) can tell them apart:
  - AINarrativeProviderError -- the Reflection Engine call itself failed
    (not configured, network error, non-2xx, timeout). Nothing about the
    reading was ever examined.
  - AINarrativeValidationError -- the provider answered, but the response
    was not usable: malformed JSON, a missing/extra/mistyped field, or a
    violation of a hard safety constraint this layer enforces itself
    (currently: no scriptural_reflection when Scripture was not supplied
    -- "AI must not invent additional Scripture references").

Both are subclasses of AINarrativeGenerationError so a caller that only
cares "did generation succeed" can catch one type. Neither is ever raised
after a database write -- see generate_ai_narrative's own docstring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.ai_narrative import AINarrativeResponse, DeterministicReadingContext
from app.services.reflection_engine.client import ReflectionEngineClient, ReflectionEngineError
from app.services.reflection_engine.prompts import build_system_prompt, build_user_prompt

SCHEMA_VERSION = "1.0"


class AINarrativeGenerationError(Exception):
    """Base class for any failure to produce a usable AINarrativeResponse.
    The deterministic Reading/Interpretation is guaranteed untouched --
    generate_ai_narrative() performs no database access of any kind.
    """


class AINarrativeProviderError(AINarrativeGenerationError):
    """The Reflection Engine call itself failed. Wraps the underlying
    ReflectionEngineError (see `__cause__`) -- app/api/ai_narrative.py
    inspects that cause to distinguish "not configured" (503) from every
    other provider failure (502).
    """


class AINarrativeValidationError(AINarrativeGenerationError):
    """The provider responded, but the response could not be safely used."""


class _RawAINarrativeContent(BaseModel):
    """The subset of AINarrativeResponse's fields the AI itself is asked
    to produce -- everything else on AINarrativeResponse (schema_version,
    source_schema_version, generated_at, provider, model) is computed by
    this module, never trusted from provider output.
    """

    model_config = ConfigDict(extra="forbid")

    opening_summary: str
    overall_narrative: str
    key_themes: tuple[str, ...] = Field(min_length=1)
    card_relationships: tuple[str, ...] = ()
    reflective_synthesis: str
    reflection_questions: tuple[str, ...] = Field(min_length=1)
    scriptural_reflection: str | None = None


def _strip_markdown_fence(text: str) -> str:
    """Provider text is instructed (prompts/interpretation.md) to be raw
    JSON with no markdown fence, but models are not perfectly reliable
    instruction-followers -- stripping one optional ```/```json fence is a
    tolerance for that, not a relaxation of the strict parse/validate
    that follows.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        stripped = stripped.removesuffix("```").strip()
    return stripped


def generate_ai_narrative(
    client: ReflectionEngineClient,
    context: DeterministicReadingContext,
    *,
    provider: str,
    model: str,
) -> AINarrativeResponse:
    """Builds the prompts, calls the Reflection Engine, and returns a
    validated AINarrativeResponse. Never persists anything -- see
    app/services/ai_narrative/persistence.py for that, always called
    separately and only after this function returns successfully (mirrors
    interpretation/engine.py's own compute-then-persist split).
    """
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(context)

    try:
        raw_text = client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    except ReflectionEngineError as exc:
        raise AINarrativeProviderError(f"Reflection Engine call failed: {exc}") from exc

    try:
        parsed = json.loads(_strip_markdown_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise AINarrativeValidationError(f"Reflection Engine response was not valid JSON: {exc}") from exc

    try:
        content = _RawAINarrativeContent.model_validate(parsed)
    except ValidationError as exc:
        raise AINarrativeValidationError(
            f"Reflection Engine response did not match the required shape: {exc}"
        ) from exc

    if context.scripture is None and content.scriptural_reflection:
        raise AINarrativeValidationError(
            "Reflection Engine response included a scriptural_reflection, but no "
            "ScripturalPerspective was supplied in this request's DeterministicReadingContext "
            "-- refusing to persist a possibly-invented Scripture reflection"
        )

    return AINarrativeResponse(
        schema_version=SCHEMA_VERSION,
        source_schema_version=context.interpretation.schema_version,
        generated_at=datetime.now(timezone.utc),
        provider=provider,
        model=model,
        opening_summary=content.opening_summary,
        overall_narrative=content.overall_narrative,
        key_themes=content.key_themes,
        card_relationships=content.card_relationships,
        reflective_synthesis=content.reflective_synthesis,
        reflection_questions=content.reflection_questions,
        scriptural_reflection=content.scriptural_reflection,
    )
