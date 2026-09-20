"""A fake ReflectionEngineClient (app/services/reflection_engine/client.py's
own Protocol) shared by every AI Narrative Layer test. No test in this
project makes a real AI provider call -- see
Documentation/AI_NARRATIVE_LAYER_DESIGN.md Section 4.
"""

from __future__ import annotations

import json

from app.services.reflection_engine.client import ReflectionEngineError

_VALID_CONTENT = {
    "opening_summary": "This reading centers on a moment of transition around the question you brought to it.",
    "overall_narrative": "The cards appear to reinforce one another around a shared theme of patience amid change.",
    "key_themes": ["Patience appears across more than one card in this spread."],
    "card_relationships": ["The Fool and The Star appear to reinforce a sense of hopeful new beginnings."],
    "reflective_synthesis": "This pattern may invite you to consider where patience could serve you here.",
    "reflection_questions": ["Where in this situation might patience be more useful than urgency?"],
    "scriptural_reflection": None,
}


class FakeReflectionEngineClient:
    """Records every call it receives (`calls`) so a test can assert what
    the AI Narrative Layer actually sent, and returns whatever
    `response_text` is set to (or raises `error_to_raise`) so a test can
    control exactly what "the provider said" without any network access.
    """

    def __init__(
        self,
        *,
        response_text: str | None = None,
        error_to_raise: ReflectionEngineError | None = None,
    ) -> None:
        self.response_text = response_text if response_text is not None else json.dumps(_VALID_CONTENT)
        self.error_to_raise = error_to_raise
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if self.error_to_raise is not None:
            raise self.error_to_raise
        return self.response_text


def valid_content_with(**overrides: object) -> dict:
    """A copy of the fake client's default valid AI content, with any
    fields overridden -- lets a test build e.g. a response that includes a
    scriptural_reflection, or one missing a required field.
    """
    content = dict(_VALID_CONTENT)
    content.update(overrides)
    return content
