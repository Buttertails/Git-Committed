"""Commit message generation using an LLM."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class GenerationResult:
    message: str
    success: bool
    error: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    subject_line: str
    body: str | None = None
    errors: list[str] = field(default_factory=list)


class MessageGenerator:
    def __init__(self, llm_client: "LLMClient | None" = None) -> None:  # type: ignore[name-defined]
        if llm_client is None:
            from acmg.llm_client import LLMClient
            llm_client = LLMClient()
        self.llm_client = llm_client

    def generate(self, diff: str, config: "ResolvedConfig") -> GenerationResult:  # type: ignore[name-defined]
        """Generate a commit message from a diff using the LLM."""
        from acmg.llm_client import LLMPrompt

        system_message, user_message = self.build_prompt(diff, config)
        prompt = LLMPrompt(system_message=system_message, user_message=user_message)
        response = self.llm_client.complete(prompt, config)

        if response.success and not response.timed_out:
            self.validate_message(response.content)
            return GenerationResult(success=True, message=response.content)
        else:
            error_msg = response.error or "Unknown error"
            if response.timed_out:
                error_msg = response.error or "LLM request timed out"
            print(f"acmg: error: {error_msg}", file=sys.stderr)
            return GenerationResult(success=False, error=error_msg, message="")

    def build_prompt(self, diff: str, config: "ResolvedConfig") -> tuple[str, str]:  # type: ignore[name-defined]
        """Build (system_message, user_message) tuple for the LLM."""
        lines = [
            "You are a git commit message generator.",
            "Your task is to produce a concise, accurate commit message from the provided diff.",
            "",
            "Rules:",
            "- Write the subject line in the imperative mood (e.g. \"Add feature\" not \"Added feature\").",
            "- The subject line MUST be 72 characters or fewer.",
            "- The subject line MUST NOT end with a period.",
            "- If you include a body, separate it from the subject line with a blank line.",
        ]

        if config.conventional_commits:
            lines += [
                "",
                "Format the subject line as:",
                "  <type>(<scope>): <description>",
                "where <type> is one of: feat, fix, docs, style, refactor, test, chore.",
                "<scope> is optional; omit the parentheses when there is no scope.",
            ]
        else:
            lines += [
                "",
                "Use a plain imperative subject line without any type prefix.",
            ]

        lines += [
            "",
            "Output only the commit message — no explanations, no markdown fences.",
        ]

        system_message = "\n".join(lines)
        user_message = diff
        return system_message, user_message

    def validate_message(self, message: str) -> ValidationResult:
        """Validate a commit message against format rules.

        Rules checked:
        - Subject line must be 72 characters or fewer.
        - Subject line must not end with a period.
        - If a body is present, a blank line must separate it from the subject.
        """
        lines = message.split("\n")
        subject_line = lines[0]
        errors: list[str] = []

        # Determine body and check blank-line separator
        body: str | None = None
        if len(lines) > 1:
            if lines[1] != "":
                errors.append(
                    "A blank line must separate the subject from the body."
                )
            # Body is everything after the first line (skip the separator line)
            body_lines = lines[2:] if len(lines) > 2 else []
            body = "\n".join(body_lines) if body_lines else None

        # Rule: subject line must be 72 characters or fewer
        if len(subject_line) > 72:
            errors.append(
                f"Subject line is {len(subject_line)} characters, which exceeds the 72-character limit."
            )

        # Rule: subject line must not end with a period
        if subject_line.endswith("."):
            errors.append("Subject line must not end with a period.")

        return ValidationResult(
            valid=len(errors) == 0,
            subject_line=subject_line,
            body=body,
            errors=errors,
        )
