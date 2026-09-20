"""Unit tests for app/services/reflection_engine/anthropic_client.py --
the one place a specific AI provider's HTTP shape is allowed to appear
(client.py's own docstring). Uses httpx2's MockTransport to intercept the
outbound request in-process -- no real network call is ever made, matching
every other AI Narrative Layer test in this project.
"""

from __future__ import annotations

import httpx2 as httpx
import pytest

from app.core.config import Settings
from app.services.reflection_engine.anthropic_client import AnthropicReflectionEngineClient
from app.services.reflection_engine.client import (
    ReflectionEngineNotConfiguredError,
    ReflectionEngineRequestError,
)


def _settings(**overrides) -> Settings:
    defaults = dict(ai_api_key="test-key", ai_model="claude-test", ai_base_url="https://api.anthropic.test")
    defaults.update(overrides)
    return Settings(**defaults)


def _install_transport(monkeypatch, handler) -> None:
    def _fake_post(url, *, json, headers, timeout):
        request = httpx.Request("POST", url, json=json, headers=headers)
        return handler(request)

    monkeypatch.setattr(httpx, "post", _fake_post)


def test_not_configured_raises_before_any_request_is_attempted(monkeypatch):
    called = False

    def _handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{}"}]})

    _install_transport(monkeypatch, _handler)
    client = AnthropicReflectionEngineClient(_settings(ai_api_key=""))

    with pytest.raises(ReflectionEngineNotConfiguredError):
        client.complete(system_prompt="sys", user_prompt="user")
    assert called is False


def test_sends_the_expected_request_shape(monkeypatch):
    import json as _json

    captured = {}

    def _handler(request):
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = _json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello"}]})

    _install_transport(monkeypatch, _handler)
    client = AnthropicReflectionEngineClient(_settings())

    result = client.complete(system_prompt="the system prompt", user_prompt="the user prompt")

    assert result == "hello"
    assert captured["url"] == "https://api.anthropic.test/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["body"]["model"] == "claude-test"
    assert captured["body"]["system"] == "the system prompt"
    assert captured["body"]["messages"] == [{"role": "user", "content": "the user prompt"}]


def test_non_200_response_raises_request_error(monkeypatch):
    _install_transport(monkeypatch, lambda request: httpx.Response(500, text="internal error"))
    client = AnthropicReflectionEngineClient(_settings())

    with pytest.raises(ReflectionEngineRequestError):
        client.complete(system_prompt="sys", user_prompt="user")


def test_unexpected_response_shape_raises_request_error(monkeypatch):
    _install_transport(monkeypatch, lambda request: httpx.Response(200, json={"unexpected": "shape"}))
    client = AnthropicReflectionEngineClient(_settings())

    with pytest.raises(ReflectionEngineRequestError):
        client.complete(system_prompt="sys", user_prompt="user")


def test_transport_error_raises_request_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", _raise)
    client = AnthropicReflectionEngineClient(_settings())

    with pytest.raises(ReflectionEngineRequestError):
        client.complete(system_prompt="sys", user_prompt="user")
