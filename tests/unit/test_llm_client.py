"""Unit tests for LLMClient.complete() — Requirements 3.1, 3.2, 3.3, 3.4, 3.5."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from acmg.config_manager import ResolvedConfig
from acmg.llm_client import LLMClient, LLMPrompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prompt(system: str = "You are a helpful assistant.", user: str = "Write a commit message.") -> LLMPrompt:
    return LLMPrompt(system_message=system, user_message=user)


def _make_config(**kwargs) -> ResolvedConfig:
    defaults = {
        "api_key": "sk-test-key",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    }
    defaults.update(kwargs)
    return ResolvedConfig(**defaults)


def _make_openai_response(content: str) -> dict:
    """Build a minimal OpenAI Chat Completions response payload."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# Tests: missing API key
# ---------------------------------------------------------------------------

class TestMissingApiKey:
    def test_no_env_var_no_config_returns_failure(self, monkeypatch, capsys):
        """When OPENAI_API_KEY is unset and config.api_key is None, return success=False."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key=None)
        client = LLMClient()

        result = client.complete(_make_prompt(), config)

        assert result.success is False
        assert result.content == ""
        assert result.error is not None
        assert "No API key" in result.error

    def test_no_env_var_no_config_prints_to_stderr(self, monkeypatch, capsys):
        """Missing API key should print a descriptive error to stderr."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key=None)
        client = LLMClient()

        client.complete(_make_prompt(), config)

        captured = capsys.readouterr()
        assert "error" in captured.err.lower()
        assert "API key" in captured.err

    def test_env_var_takes_precedence_over_none_config(self, monkeypatch):
        """OPENAI_API_KEY env var should be used even when config.api_key is None."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        config = _make_config(api_key=None)
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("feat: add feature")

        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = client.complete(_make_prompt(), config)

        assert result.success is True
        # Verify the env var key was used in the Authorization header
        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        # Access via keyword argument
        assert "sk-from-env" in mock_post.call_args.kwargs.get("headers", {}).get("Authorization", "")


# ---------------------------------------------------------------------------
# Tests: HTTP error responses
# ---------------------------------------------------------------------------

class TestHttpErrors:
    def test_http_500_returns_failure(self, monkeypatch):
        """HTTP 500 response should return success=False with error message."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.post", return_value=mock_response):
            result = client.complete(_make_prompt(), config)

        assert result.success is False
        assert result.content == ""
        assert "500" in result.error
        assert "Internal Server Error" in result.error

    def test_http_401_returns_failure(self, monkeypatch):
        """HTTP 401 response should return success=False with error message."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-bad-key")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.post", return_value=mock_response):
            result = client.complete(_make_prompt(), config)

        assert result.success is False
        assert "401" in result.error

    def test_http_error_timed_out_is_false(self, monkeypatch):
        """HTTP errors should not set timed_out=True."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch("httpx.post", return_value=mock_response):
            result = client.complete(_make_prompt(), config)

        assert result.timed_out is False


# ---------------------------------------------------------------------------
# Tests: timeout
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_timeout_returns_failure_with_timed_out_true(self, monkeypatch):
        """TimeoutException should return success=False with timed_out=True."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            result = client.complete(_make_prompt(), config)

        assert result.success is False
        assert result.timed_out is True
        assert result.content == ""
        assert result.error is not None
        assert "timed out" in result.error.lower()

    def test_timeout_error_message_mentions_15_seconds(self, monkeypatch):
        """Timeout error message should mention the 15-second limit."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            result = client.complete(_make_prompt(), config)

        assert "15" in result.error

    def test_request_uses_15_second_timeout(self, monkeypatch):
        """httpx.post should always be called with timeout=15.0."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("fix: resolve issue")

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client.complete(_make_prompt(), config)

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs.get("timeout") == 15.0


# ---------------------------------------------------------------------------
# Tests: successful response
# ---------------------------------------------------------------------------

class TestSuccessfulResponse:
    def test_success_returns_true(self, monkeypatch):
        """HTTP 200 response should return success=True."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("feat: add login page")

        with patch("httpx.post", return_value=mock_response):
            result = client.complete(_make_prompt(), config)

        assert result.success is True

    def test_success_extracts_content(self, monkeypatch):
        """Successful response should extract the message content correctly."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()
        expected_content = "feat: add user authentication"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response(expected_content)

        with patch("httpx.post", return_value=mock_response):
            result = client.complete(_make_prompt(), config)

        assert result.content == expected_content

    def test_success_error_is_none(self, monkeypatch):
        """Successful response should have error=None."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("chore: update deps")

        with patch("httpx.post", return_value=mock_response):
            result = client.complete(_make_prompt(), config)

        assert result.error is None
        assert result.timed_out is False

    def test_request_sends_correct_body(self, monkeypatch):
        """Request body should include model and messages with correct roles."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test", model="gpt-4o")
        client = LLMClient()
        prompt = _make_prompt(system="Be concise.", user="Here is the diff.")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("docs: update readme")

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client.complete(prompt, config)

        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs.get("json")
        assert body["model"] == "gpt-4o"
        assert body["messages"][0] == {"role": "system", "content": "Be concise."}
        assert body["messages"][1] == {"role": "user", "content": "Here is the diff."}

    def test_request_uses_correct_url(self, monkeypatch):
        """Request URL should be {base_url}/chat/completions."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-test", base_url="http://localhost:11434/v1")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("fix: patch bug")

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client.complete(_make_prompt(), config)

        call_args = mock_post.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        assert url == "http://localhost:11434/v1/chat/completions"

    def test_request_uses_bearer_auth_header(self, monkeypatch):
        """Authorization header should be 'Bearer <api_key>'."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-my-secret-key")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("refactor: simplify logic")

        with patch("httpx.post", return_value=mock_response) as mock_post:
            client.complete(_make_prompt(), config)

        headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-my-secret-key"

    def test_config_api_key_used_when_no_env_var(self, monkeypatch):
        """config.api_key should be used when OPENAI_API_KEY env var is not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = _make_config(api_key="sk-from-config")
        client = LLMClient()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = _make_openai_response("test: add unit tests")

        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = client.complete(_make_prompt(), config)

        assert result.success is True
        headers = mock_post.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-from-config"
