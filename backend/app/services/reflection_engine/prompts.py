"""Loads and assembles the Reflection Engine's prompt files.

RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 12 names these exact paths and
notes they were "currently empty and need to be authored before this layer
can function" -- authoring their content is part of this layer's own
implementation, not a separate content task. They live at the repository
root (`prompts/`), not under `backend/app/`, per the Product Spec and
docs/ROADMAP.md's Phase 4 instruction ("Author `prompts/system/safety.md`,
`prompts/system/tone.md`, `prompts/system/reflection_engine.md`, and
`prompts/interpretation.md`") -- this assumes the repository is checked out
whole (backend/ alongside prompts/), the same assumption every reference
in the Product Spec already makes. A future deploy that ships `backend/`
alone will need to bundle `prompts/` alongside it.

The *system* prompt (role + safety + tone) is fixed and identical for
every call; only the *user* prompt (the actual reading data) varies per
request. Read fresh on every call rather than cached at import time, so a
prompt edit takes effect without a process restart -- prompt files are
small (a few KB) and this only runs once per AI Narrative generation
request, never in a hot loop.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.ai_narrative import DeterministicReadingContext

_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"
_SYSTEM_DIR = _PROMPTS_DIR / "system"

_REFLECTION_ENGINE_PROMPT_PATH = _SYSTEM_DIR / "reflection_engine.md"
_SAFETY_PROMPT_PATH = _SYSTEM_DIR / "safety.md"
_TONE_PROMPT_PATH = _SYSTEM_DIR / "tone.md"
_INTERPRETATION_PROMPT_PATH = _PROMPTS_DIR / "interpretation.md"


class PromptFileMissingError(RuntimeError):
    """Raised when a required prompt file is missing or blank -- the
    Reflection Engine refuses to fall back to an undocumented, in-code
    default prompt (that would defeat the entire point of these files
    being reviewable, versioned, and shared between the Interpretation
    Engine's own banned-language list and this layer's system prompt, per
    Product Spec Section 14).
    """


def _read_prompt(path: Path) -> str:
    if not path.is_file():
        raise PromptFileMissingError(f"Required Reflection Engine prompt file is missing: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise PromptFileMissingError(f"Required Reflection Engine prompt file is blank: {path}")
    return text


def build_system_prompt() -> str:
    """The fixed behavioral contract sent as every request's `system`
    field: role framing, then the non-negotiable safety constraints, then
    tone guidance. Order matters only for readability -- safety.md's own
    constraints are absolute regardless of where they appear in the
    prompt.
    """
    sections = [
        _read_prompt(_REFLECTION_ENGINE_PROMPT_PATH),
        _read_prompt(_SAFETY_PROMPT_PATH),
        _read_prompt(_TONE_PROMPT_PATH),
    ]
    return "\n\n---\n\n".join(sections)


def build_user_prompt(context: DeterministicReadingContext) -> str:
    """The per-request task instructions (interpretation.md) followed by
    the entire factual basis for this reading, as JSON.

    Serializing `context` (a DeterministicReadingContext -- itself just an
    InterpretiveModel plus an optional ScripturalPerspective, see
    app/schemas/ai_narrative.py) is what satisfies Product Spec Section
    12's "Input: a finished Interpretive Model only -- never raw Card
    Draws": nothing else from the database is ever serialized into a
    prompt.
    """
    task = _read_prompt(_INTERPRETATION_PROMPT_PATH)
    data = context.model_dump(mode="json")
    return f"{task}\n\n---\n\nREADING DATA (JSON):\n\n{json.dumps(data, indent=2)}"
