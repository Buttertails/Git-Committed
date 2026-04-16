"""Unit tests for UserInteraction."""

import os
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from acmg.user_interaction import UserInteraction


# ---------------------------------------------------------------------------
# is_interactive()
# ---------------------------------------------------------------------------

def test_is_interactive_returns_false_when_stdin_not_tty():
    ui = UserInteraction()
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = False
        assert ui.is_interactive() is False


def test_is_interactive_returns_false_when_ci_env_var_set():
    ui = UserInteraction()
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch.dict(os.environ, {"CI": "true"}, clear=False):
            assert ui.is_interactive() is False


def test_is_interactive_returns_false_when_github_actions_set():
    ui = UserInteraction()
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            assert ui.is_interactive() is False


def test_is_interactive_returns_false_when_auto_accept_true():
    config = MagicMock()
    config.auto_accept = True
    ui = UserInteraction(config=config)
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        # Ensure no CI env vars are set
        env_without_ci = {
            k: v for k, v in os.environ.items()
            if k not in ("CI", "GITHUB_ACTIONS", "TRAVIS", "CIRCLECI", "JENKINS_URL")
        }
        with patch.dict(os.environ, env_without_ci, clear=True):
            assert ui.is_interactive() is False


def test_is_interactive_returns_true_in_normal_conditions():
    config = MagicMock()
    config.auto_accept = False
    ui = UserInteraction(config=config)
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        env_without_ci = {
            k: v for k, v in os.environ.items()
            if k not in ("CI", "GITHUB_ACTIONS", "TRAVIS", "CIRCLECI", "JENKINS_URL")
        }
        with patch.dict(os.environ, env_without_ci, clear=True):
            assert ui.is_interactive() is True


# ---------------------------------------------------------------------------
# write_commit_message()
# ---------------------------------------------------------------------------

def test_write_commit_message_writes_message_to_file(tmp_path):
    file_path = str(tmp_path / "COMMIT_EDITMSG")
    ui = UserInteraction()
    ui.write_commit_message(file_path, "feat: add new feature\n\nSome body text.")
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert content == "feat: add new feature\n\nSome body text."


def test_write_commit_message_overwrites_existing_content(tmp_path):
    file_path = str(tmp_path / "COMMIT_EDITMSG")
    with open(file_path, "w") as fh:
        fh.write("old message")
    ui = UserInteraction()
    ui.write_commit_message(file_path, "new message")
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert content == "new message"


# ---------------------------------------------------------------------------
# prompt_user()
# ---------------------------------------------------------------------------

def _make_stdin(text: str):
    """Return a mock stdin that reads the given text."""
    mock = MagicMock()
    mock.readline.return_value = text + "\n"
    mock.isatty.return_value = True
    return mock


def test_prompt_user_returns_accept_when_user_inputs_a():
    ui = UserInteraction()
    with patch("sys.stdin", _make_stdin("a")):
        result = ui.prompt_user("feat: some message")
    assert result == "accept"


def test_prompt_user_returns_accept_on_empty_input():
    ui = UserInteraction()
    with patch("sys.stdin", _make_stdin("")):
        result = ui.prompt_user("feat: some message")
    assert result == "accept"


def test_prompt_user_returns_edit_when_user_inputs_e():
    ui = UserInteraction()
    with patch("sys.stdin", _make_stdin("e")):
        result = ui.prompt_user("feat: some message")
    assert result == "edit"


def test_prompt_user_returns_discard_when_user_inputs_d():
    ui = UserInteraction()
    with patch("sys.stdin", _make_stdin("d")):
        result = ui.prompt_user("feat: some message")
    assert result == "discard"
