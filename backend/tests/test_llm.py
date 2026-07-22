"""Tests for the shared LLM utility — retry-once-on-validation-failure.

Mocks the AsyncOpenAI client so no network is touched. Proves:
1. invalid JSON shape then valid → retry succeeds, 2 calls made
2. invalid twice → LLMCallError (endpoints translate to 502), 2 calls made
3. refusal finish_reason → LLMCallError, no retry
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.ai.llm import LLMCallError, call_llm_with_retry


class _Out(BaseModel):
    name: str
    count: int


def _response(content: str, finish_reason: str = "stop"):
    """Build a minimal chat-completion response mock."""
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _client_with(side_effects):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=side_effects)
    client.close = AsyncMock()
    return client


def _fake_settings():
    """conftest blanks OPENAI_API_KEY to keep the suite offline, so these
    utility tests stub settings with a dummy key to get past the guard."""
    s = MagicMock()
    s.openai_api_key = "test-key"
    s.openai_base_url = "https://example.invalid/v1"
    s.openai_model = "test-model"
    return s


def test_retry_succeeds_on_second_attempt():
    invalid = _response(json.dumps({"name": "x"}))  # missing count
    valid = _response(json.dumps({"name": "x", "count": 3}))
    client = _client_with([invalid, valid])

    with patch("app.ai.llm.get_settings", return_value=_fake_settings()), \
         patch("app.ai.llm.AsyncOpenAI", return_value=client):
        result, model = asyncio.run(
            call_llm_with_retry("sys", "user", _Out)
        )
    assert result.count == 3
    assert client.chat.completions.create.call_count == 2
    # Retry prompt must carry the validation error forward
    second_call = client.chat.completions.create.call_args_list[1]
    retry_user_msg = second_call.kwargs["messages"][1]["content"]
    assert "failed validation" in retry_user_msg


def test_double_failure_raises():
    invalid = _response(json.dumps({"name": "x"}))  # missing count, twice
    client = _client_with([invalid, invalid])

    with patch("app.ai.llm.get_settings", return_value=_fake_settings()), \
         patch("app.ai.llm.AsyncOpenAI", return_value=client):
        with pytest.raises(LLMCallError, match="invalid data after retry"):
            asyncio.run(call_llm_with_retry("sys", "user", _Out))
    assert client.chat.completions.create.call_count == 2


def test_refusal_no_retry():
    refused = _response("", finish_reason="refusal")
    client = _client_with([refused])

    with patch("app.ai.llm.get_settings", return_value=_fake_settings()), \
         patch("app.ai.llm.AsyncOpenAI", return_value=client):
        with pytest.raises(LLMCallError, match="declined"):
            asyncio.run(call_llm_with_retry("sys", "user", _Out))
    assert client.chat.completions.create.call_count == 1


def test_invalid_json_raises():
    bad = _response("not json at all")
    client = _client_with([bad])

    with patch("app.ai.llm.get_settings", return_value=_fake_settings()), \
         patch("app.ai.llm.AsyncOpenAI", return_value=client):
        with pytest.raises(LLMCallError, match="Invalid JSON"):
            asyncio.run(call_llm_with_retry("sys", "user", _Out))


def test_missing_key_raises():
    settings = MagicMock()
    settings.openai_api_key = None
    with patch("app.ai.llm.get_settings", return_value=settings):
        with pytest.raises(LLMCallError, match="not configured"):
            asyncio.run(call_llm_with_retry("sys", "user", _Out))
