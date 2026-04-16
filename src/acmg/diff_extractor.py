"""Diff extraction and truncation for staged git changes."""

import subprocess
from dataclasses import dataclass


@dataclass
class DiffResult:
    diff: str           # raw unified diff text
    is_empty: bool      # True when no files are staged
    was_truncated: bool


class DiffExtractor:
    def extract_staged_diff(self) -> DiffResult:
        """Run git diff --cached and return the result."""
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout

        if not output:
            return DiffResult(diff="", is_empty=True, was_truncated=False)

        return DiffResult(diff=output, is_empty=False, was_truncated=False)

    def truncate_diff(self, diff: str, max_tokens: int) -> str:
        """Truncate diff to fit within max_tokens, keeping most recent hunks.

        Token count is estimated as ceil(len(diff) / 4). If the diff fits
        within max_tokens it is returned unchanged. Otherwise, hunks (sections
        starting with '@@') are greedily included from the END of the diff
        until the token budget is exhausted, and a header comment is prepended.
        """
        import math

        def _estimate_tokens(text: str) -> int:
            return math.ceil(len(text) / 4)

        if _estimate_tokens(diff) <= max_tokens:
            return diff

        header = "# [acmg: diff truncated to fit token limit]\n"
        header_tokens = _estimate_tokens(header)
        remaining_budget = max_tokens - header_tokens

        # Split into hunks: each hunk starts with '@@'
        # The first segment (before any '@@') is the file header lines.
        parts = diff.split("\n@@")
        # Re-attach the '@@' prefix to all parts except the first
        hunks = [parts[0]] + ["\n@@" + p for p in parts[1:]]

        # Greedily include hunks from the END until budget is exhausted
        selected = []
        for hunk in reversed(hunks):
            hunk_tokens = _estimate_tokens(hunk)
            if hunk_tokens <= remaining_budget:
                selected.append(hunk)
                remaining_budget -= hunk_tokens
            # If a single hunk is too large, skip it entirely

        selected.reverse()
        truncated_body = "".join(selected)
        return header + truncated_body
