"""HTTP client for the OpenAI Chat Completions API."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import httpx


@dataclass
class LLMPrompt:
    system_message: str
    user_message: str


@dataclass
class LLMResponse:
    content: str
    success: bool
    error: str | None = None
    timed_out: bool = False


class LLMClient:
    def complete(self, prompt: LLMPrompt, config: "ResolvedConfig") -> LLMResponse:  # type: ignore[name-defined]
        """Send a prompt to the LLM and return the response.

        API key resolution order:
          1. OPENAI_API_KEY environment variable
          2. config.api_key
          3. Neither set → print error to stderr, return failure response
        """
        api_key = os.environ.get("OPENAI_API_KEY") or config.api_key

        if not api_key:
            print(
                "acmg: error: No API key configured. "
                "Set the OPENAI_API_KEY environment variable or add 'apiKey' to .git-acmg.json.",
                file=sys.stderr,
            )
            return LLMResponse(
                content="",
                success=False,
                error="No API key configured. Set OPENAI_API_KEY or add apiKey to config.",
            )

        url = f"{config.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": prompt.system_message},
                {"role": "user", "content": prompt.user_message},
            ],
        }

        try:
            response = httpx.post(url, json=body, headers=headers, timeout=15.0)
        except httpx.TimeoutException:
            return LLMResponse(
                content="",
                success=False,
                timed_out=True,
                error="Request timed out after 15 seconds",
            )

        if response.status_code != 200:
            return LLMResponse(
                content="",
                success=False,
                error=f"HTTP {response.status_code}: {response.text}",
            )

        content = response.json()["choices"][0]["message"]["content"]
        return LLMResponse(content=content, success=True)
