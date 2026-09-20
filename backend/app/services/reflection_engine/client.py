"""The Reflection Engine's own client boundary (ADR-0005, docs/DECISIONS.md;
docs/ARCHITECTURE.md's "Reflection Engine" Core Service).

ADR-0005: "Artificial intelligence shall be accessed exclusively through the
Reflection Engine. Individual application components should never
communicate directly with AI providers." `ReflectionEngineClient` is that
one sanctioned seam -- every caller in this codebase (today: only
app/services/ai_narrative/generation.py) depends on this Protocol, never on
a specific provider SDK/HTTP shape directly. Swapping providers later means
writing one new class here, not touching any caller.

Deliberately a single `complete()` method, not a general-purpose multi-turn
chat/tool-use abstraction -- the only thing anything in this project needs
today (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 12: one system prompt, one
user prompt, one text response) per "do not introduce a new AI provider
abstraction unless the repository actually needs one."
"""

from __future__ import annotations

from typing import Protocol


class ReflectionEngineError(Exception):
    """Base class for every Reflection Engine failure. Never raised
    directly -- callers catch this to handle "the AI layer failed" in
    general, or one of the subclasses below for a more specific reason.
    """


class ReflectionEngineNotConfiguredError(ReflectionEngineError):
    """Raised when no AI provider credential is configured (Settings.ai_api_key
    is blank -- the zero-config default for local dev/test, see
    app/core/config.py). Fails closed before any network call is attempted.
    """


class ReflectionEngineRequestError(ReflectionEngineError):
    """Raised when the provider call itself fails: a transport/network
    error, a non-2xx response, a timeout, or a 2xx response whose shape
    does not match what the provider is documented to return. Never raised
    for a well-formed response the AI Narrative Layer merely disagrees with
    the *content* of -- that is a validation concern one layer up (see
    app/services/ai_narrative/generation.py::AINarrativeValidationError).
    """


class ReflectionEngineClient(Protocol):
    """One provider-agnostic text-completion call: a system prompt (the
    fixed behavioral contract -- see
    app/services/reflection_engine/prompts.py) plus a user prompt (the
    per-request structured data, e.g. a DeterministicReadingContext), in;
    the provider's raw text response, out.

    Callers are responsible for parsing/validating the returned text (see
    generation.py) -- this boundary makes no assumption about response
    shape beyond "some text came back."
    """

    def complete(self, *, system_prompt: str, user_prompt: str) -> str: ...
