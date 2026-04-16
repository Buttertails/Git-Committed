"""Integration tests for the git hook flow.

Tests:
1. Stage a real file in a temp git repo and verify DiffExtractor captures the diff.
2. Mock the OpenAI HTTP endpoint and run the full _cmd_hook flow, verifying the
   generated message is written to the commit message file.

Requirements: 1.1, 1.3, 3.3
"""

import argparse
import json
import os
import subprocess
from unittest.mock import patch

import pytest

from acmg.diff_extractor import DiffExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path):
    """Initialise a bare git repo with a user identity in *path*."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )


def _stage_file(repo_path, filename, content):
    """Write *content* to *filename* inside *repo_path* and stage it."""
    file_path = repo_path / filename
    file_path.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "add", filename],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )
    return file_path


def _make_openai_response(message: str) -> dict:
    """Return a minimal OpenAI Chat Completions JSON response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": message},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


# ---------------------------------------------------------------------------
# Test 1: DiffExtractor captures staged changes in a real git repo
# ---------------------------------------------------------------------------


class TestDiffExtractorIntegration:
    """Verify that DiffExtractor.extract_staged_diff() works against a real repo."""

    def test_staged_new_file_is_captured(self, tmp_path):
        """Staging a new file produces a non-empty diff (Req 1.1)."""
        _init_git_repo(tmp_path)
        _stage_file(tmp_path, "hello.py", "print('hello')\n")

        extractor = DiffExtractor()
        # Run from within the temp repo so git finds the right index.
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            result = extractor.extract_staged_diff()
        finally:
            os.chdir(original_cwd)

        assert not result.is_empty, "Expected a non-empty diff after staging a file"
        assert "hello.py" in result.diff, "Diff should reference the staged file"
        assert "print('hello')" in result.diff, "Diff should contain the file content"

    def test_no_staged_files_returns_empty(self, tmp_path):
        """An empty staging area produces an empty diff (Req 1.2)."""
        _init_git_repo(tmp_path)
        # Write a file but do NOT stage it.
        (tmp_path / "unstaged.py").write_text("x = 1\n", encoding="utf-8")

        extractor = DiffExtractor()
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            result = extractor.extract_staged_diff()
        finally:
            os.chdir(original_cwd)

        assert result.is_empty, "Expected is_empty=True when nothing is staged"
        assert result.diff == ""

    def test_staged_rename_is_captured(self, tmp_path):
        """Renames appear in the diff (Req 1.3)."""
        _init_git_repo(tmp_path)

        # Create and commit the original file first.
        _stage_file(tmp_path, "old_name.py", "x = 1\n")
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        # Rename the file and stage the rename.
        subprocess.run(
            ["git", "mv", "old_name.py", "new_name.py"],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        extractor = DiffExtractor()
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            result = extractor.extract_staged_diff()
        finally:
            os.chdir(original_cwd)

        assert not result.is_empty, "Rename should produce a non-empty diff"
        # The diff should mention at least one of the file names.
        assert "old_name.py" in result.diff or "new_name.py" in result.diff

    def test_staged_deletion_is_captured(self, tmp_path):
        """Deletions appear in the diff (Req 1.3)."""
        _init_git_repo(tmp_path)

        _stage_file(tmp_path, "to_delete.py", "y = 2\n")
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "rm", "to_delete.py"],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        extractor = DiffExtractor()
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            result = extractor.extract_staged_diff()
        finally:
            os.chdir(original_cwd)

        assert not result.is_empty, "Deletion should produce a non-empty diff"
        assert "to_delete.py" in result.diff


# ---------------------------------------------------------------------------
# Test 2: Full _cmd_hook flow with mocked OpenAI endpoint
# ---------------------------------------------------------------------------


class TestCmdHookIntegration:
    """Run the full _cmd_hook flow against a real git repo with a mocked HTTP layer."""

    def _make_mock_response(self, message: str):
        """Return a mock httpx.Response-like object."""
        import httpx

        return httpx.Response(
            status_code=200,
            json=_make_openai_response(message),
        )

    def test_hook_writes_generated_message_in_non_interactive_mode(self, tmp_path):
        """Full hook flow: staged file → mocked LLM → message written to file (Req 3.3).

        The test runs in a non-interactive environment (CI=true), so the hook
        auto-accepts the generated message without prompting.
        """
        _init_git_repo(tmp_path)
        _stage_file(tmp_path, "feature.py", "def add(a, b):\n    return a + b\n")

        commit_msg_file = tmp_path / "COMMIT_EDITMSG"
        commit_msg_file.write_text("", encoding="utf-8")

        expected_message = "feat: add addition helper function"
        mock_response = self._make_mock_response(expected_message)

        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))

            with patch("httpx.post", return_value=mock_response), \
                 patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key", "CI": "true"}):

                from acmg.cli import _cmd_hook

                args = argparse.Namespace(
                    commit_msg_file=str(commit_msg_file),
                    source="",
                    sha="",
                )
                _cmd_hook(args)

        finally:
            os.chdir(original_cwd)

        written = commit_msg_file.read_text(encoding="utf-8")
        assert written == expected_message, (
            f"Expected commit message file to contain {expected_message!r}, got {written!r}"
        )

    def test_hook_skips_merge_source(self, tmp_path):
        """Hook exits without writing anything when source is 'merge' (Req 1.1 / skip logic)."""
        _init_git_repo(tmp_path)
        _stage_file(tmp_path, "file.py", "x = 1\n")

        commit_msg_file = tmp_path / "COMMIT_EDITMSG"
        original_content = "Merge branch 'feature'\n"
        commit_msg_file.write_text(original_content, encoding="utf-8")

        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
                from acmg.cli import _cmd_hook

                args = argparse.Namespace(
                    commit_msg_file=str(commit_msg_file),
                    source="merge",
                    sha="",
                )
                with pytest.raises(SystemExit) as exc_info:
                    _cmd_hook(args)
                assert exc_info.value.code == 0

        finally:
            os.chdir(original_cwd)

        # File should be untouched.
        assert commit_msg_file.read_text(encoding="utf-8") == original_content

    def test_hook_exits_cleanly_on_empty_diff(self, tmp_path):
        """Hook exits with code 0 and writes nothing when nothing is staged."""
        _init_git_repo(tmp_path)
        # Do NOT stage anything.

        commit_msg_file = tmp_path / "COMMIT_EDITMSG"
        commit_msg_file.write_text("", encoding="utf-8")

        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
                from acmg.cli import _cmd_hook

                args = argparse.Namespace(
                    commit_msg_file=str(commit_msg_file),
                    source="",
                    sha="",
                )
                with pytest.raises(SystemExit) as exc_info:
                    _cmd_hook(args)
                assert exc_info.value.code == 0

        finally:
            os.chdir(original_cwd)

        assert commit_msg_file.read_text(encoding="utf-8") == ""

    def test_hook_exits_cleanly_when_api_key_missing(self, tmp_path):
        """Hook exits with code 0 (non-blocking) when no API key is configured."""
        _init_git_repo(tmp_path)
        _stage_file(tmp_path, "file.py", "z = 3\n")

        commit_msg_file = tmp_path / "COMMIT_EDITMSG"
        commit_msg_file.write_text("", encoding="utf-8")

        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))

            # Remove OPENAI_API_KEY from the environment.
            env_without_key = {
                k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"
            }
            with patch.dict(os.environ, env_without_key, clear=True):
                from acmg.cli import _cmd_hook

                args = argparse.Namespace(
                    commit_msg_file=str(commit_msg_file),
                    source="",
                    sha="",
                )
                # The hook calls sys.exit(0) on LLM failure — that is the
                # correct non-blocking behaviour (Req 2.5 / 3.2).
                with pytest.raises(SystemExit) as exc_info:
                    _cmd_hook(args)
                assert exc_info.value.code == 0

        finally:
            os.chdir(original_cwd)

        # Commit message file should remain empty (no message generated).
        assert commit_msg_file.read_text(encoding="utf-8") == ""
