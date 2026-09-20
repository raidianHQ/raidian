"""The one concrete `ReflectionEngineClient` this project ships: a thin HTTP
call to Anthropic's Messages API. See client.py's own docstring for why this
is the *only* place a provider SDK/HTTP shape is allowed to appear.

Uses `httpx2` (already a project dependency -- app/api/scripture.py's own
test suite and every other API test depend on it transitively via
fastapi.testclient, see requirements.txt) directly rather than adding a new
`anthropic` SDK dependency, per "do not introduce a new AI provider
abstraction unless the repository actually needs one" -- a single JSON POST
does not need a full SDK.
"""

from __future__ import annotations

import httpx2 as httpx

from app.core.config import Settings
from app.services.reflection_engine.client import (
    ReflectionEngineNotConfiguredError,
    ReflectionEngineRequestError,
)

_MESSAGES_PATH = "/v1/messages"


class AnthropicReflectionEngineClient:
    """Implements `ReflectionEngineClient` (structurally -- Protocol, no
    inheritance required) against Anthropic's Messages API.

    Constructed fresh per request by app/api/dependencies.py::get_reflection_engine_client
    -- cheap (no connection is opened until `complete()` runs), so there is
    no pooled/shared client lifecycle to manage.
    """

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.ai_api_key
        self._base_url = settings.ai_base_url
        self._model = settings.ai_model
        self._anthropic_version = settings.ai_anthropic_version
        self._timeout_seconds = settings.ai_request_timeout_seconds
        self._max_output_tokens = settings.ai_max_output_tokens

    @property
    def model(self) -> str:
        return self._model

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise ReflectionEngineNotConfiguredError(
                "RAIDIAN_AI_API_KEY is not set -- the Reflection Engine cannot reach an AI provider"
            )

        payload = {
            "model": self._model,
            "max_tokens": self._max_output_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._anthropic_version,
            "content-type": "application/json",
        }

        try:
            response = httpx.post(
                f"{self._base_url}{_MESSAGES_PATH}",
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise ReflectionEngineRequestError(f"Reflection Engine request failed: {exc}") from exc

        if response.status_code != 200:
            raise ReflectionEngineRequestError(
                f"Reflection Engine provider returned HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            body = response.json()
            content = body["content"]
            text = "".join(block["text"] for block in content if block.get("type") == "text")
        except (ValueError, KeyError, TypeError) as exc:
            raise ReflectionEngineRequestError(
                f"Reflection Engine provider returned an unexpected response shape: {exc}"
            ) from exc

        if not text:
            raise ReflectionEngineRequestError("Reflection Engine provider returned no text content")

        return text
