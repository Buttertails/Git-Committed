"""Unit tests for DiffExtractor.extract_staged_diff() and truncate_diff()."""

from unittest.mock import patch, MagicMock

import pytest

from acmg.diff_extractor import DiffExtractor, DiffResult


SAMPLE_DIFF = """\
diff --git a/foo.py b/foo.py
index 1234567..abcdefg 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def hello():
-    pass
+    print("hello")
+
"""


class TestExtractStagedDiff:
    def _run(self, stdout: str) -> DiffResult:
        """Helper: patch subprocess.run and call extract_staged_diff."""
        mock_result = MagicMock()
        mock_result.stdout = stdout
        with patch("acmg.diff_extractor.subprocess.run", return_value=mock_result) as mock_run:
            extractor = DiffExtractor()
            result = extractor.extract_staged_diff()
            # Verify the correct git command was used
            mock_run.assert_called_once_with(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
            )
        return result

    def test_empty_diff_returns_is_empty_true(self):
        """When git diff --cached returns no output, is_empty should be True."""
        result = self._run("")
        assert result.is_empty is True
        assert result.diff == ""
        assert result.was_truncated is False

    def test_non_empty_diff_returns_is_empty_false(self):
        """When git diff --cached returns output, is_empty should be False."""
        result = self._run(SAMPLE_DIFF)
        assert result.is_empty is False

    def test_non_empty_diff_preserves_raw_output(self):
        """The raw diff text should be stored verbatim in DiffResult.diff."""
        result = self._run(SAMPLE_DIFF)
        assert result.diff == SAMPLE_DIFF

    def test_non_empty_diff_was_truncated_false(self):
        """extract_staged_diff never truncates; was_truncated should be False."""
        result = self._run(SAMPLE_DIFF)
        assert result.was_truncated is False

    def test_returns_diff_result_instance(self):
        """Return type should be DiffResult."""
        result = self._run(SAMPLE_DIFF)
        assert isinstance(result, DiffResult)

    def test_whitespace_only_output_treated_as_non_empty(self):
        """Whitespace-only output (unlikely but possible) is treated as non-empty."""
        result = self._run("   \n")
        # Non-empty string → is_empty False
        assert result.is_empty is False

    def test_rename_and_deletion_diff_captured(self):
        """Renames and deletions in the diff are captured as-is."""
        rename_diff = (
            "diff --git a/old.py b/new.py\n"
            "similarity index 100%\n"
            "rename from old.py\n"
            "rename to new.py\n"
        )
        result = self._run(rename_diff)
        assert result.is_empty is False
        assert result.diff == rename_diff


import math


HEADER_COMMENT = "# [acmg: diff truncated to fit token limit]\n"


def _estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def _make_diff(num_hunks: int, lines_per_hunk: int = 10) -> str:
    """Build a synthetic unified diff with the given number of hunks."""
    parts = ["diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n"]
    for i in range(num_hunks):
        hunk_lines = "\n".join(
            f"+line_{i}_{j}" for j in range(lines_per_hunk)
        )
        parts.append(f"@@ -{i * lines_per_hunk + 1},{lines_per_hunk} +{i * lines_per_hunk + 1},{lines_per_hunk} @@\n{hunk_lines}\n")
    return "".join(parts)


class TestTruncateDiff:
    def test_diff_within_limit_returned_unchanged(self):
        """A diff whose token count fits within max_tokens is returned as-is."""
        diff = "small diff content"
        max_tokens = _estimate_tokens(diff) + 100  # plenty of room
        extractor = DiffExtractor()
        result = extractor.truncate_diff(diff, max_tokens)
        assert result == diff

    def test_diff_exactly_at_limit_returned_unchanged(self):
        """A diff whose token count equals max_tokens is returned unchanged."""
        diff = "x" * 40  # 40 chars → ceil(40/4) = 10 tokens
        extractor = DiffExtractor()
        result = extractor.truncate_diff(diff, 10)
        assert result == diff

    def test_truncated_diff_has_header_comment(self):
        """When truncation occurs, the result starts with the header comment."""
        diff = _make_diff(num_hunks=20, lines_per_hunk=20)
        max_tokens = 50  # much smaller than the full diff
        extractor = DiffExtractor()
        result = extractor.truncate_diff(diff, max_tokens)
        assert result.startswith(HEADER_COMMENT)

    def test_truncated_result_token_count_within_limit(self):
        """The truncated result must have an estimated token count <= max_tokens."""
        diff = _make_diff(num_hunks=30, lines_per_hunk=15)
        max_tokens = 100
        extractor = DiffExtractor()
        result = extractor.truncate_diff(diff, max_tokens)
        assert _estimate_tokens(result) <= max_tokens

    def test_truncated_result_contains_only_original_hunks(self):
        """Truncated output must not contain content that wasn't in the original diff."""
        diff = _make_diff(num_hunks=10, lines_per_hunk=10)
        max_tokens = 80
        extractor = DiffExtractor()
        result = extractor.truncate_diff(diff, max_tokens)
        # Strip the header and verify every remaining line came from the original
        body = result[len(HEADER_COMMENT):]
        for line in body.splitlines():
            assert line in diff or line == ""

    def test_truncation_prefers_most_recent_hunks(self):
        """When truncating, hunks from the end of the diff are preferred."""
        # Build a diff where each hunk has a unique marker
        hunk_a = "@@ -1,1 +1,1 @@\n+first_hunk_content_aaa\n"
        hunk_b = "@@ -2,1 +2,1 @@\n+last_hunk_content_zzz\n"
        file_header = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n"
        diff = file_header + hunk_a + hunk_b

        # Set max_tokens tight enough to exclude hunk_a but include hunk_b
        # header_comment + file_header + hunk_b should fit; hunk_a should be dropped
        needed = _estimate_tokens(HEADER_COMMENT + hunk_b)
        max_tokens = needed + 5  # just enough for header + last hunk, not first

        extractor = DiffExtractor()
        result = extractor.truncate_diff(diff, max_tokens)

        assert "last_hunk_content_zzz" in result
        assert _estimate_tokens(result) <= max_tokens
