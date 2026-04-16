"""Unit tests for MessageGenerator.build_prompt."""

import pytest

from acmg.config_manager import ResolvedConfig
from acmg.message_generator import MessageGenerator, ValidationResult


@pytest.fixture
def generator() -> MessageGenerator:
    return MessageGenerator()


@pytest.fixture
def config_conventional() -> ResolvedConfig:
    return ResolvedConfig(conventional_commits=True)


@pytest.fixture
def config_plain() -> ResolvedConfig:
    return ResolvedConfig(conventional_commits=False)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestBuildPromptReturnType:
    def test_returns_tuple_of_two_strings(self, generator, config_conventional):
        result = generator.build_prompt("diff content", config_conventional)
        assert isinstance(result, tuple)
        assert len(result) == 2
        system_msg, user_msg = result
        assert isinstance(system_msg, str)
        assert isinstance(user_msg, str)


# ---------------------------------------------------------------------------
# System message — always-present content
# ---------------------------------------------------------------------------

class TestSystemMessageAlwaysPresent:
    def test_contains_role_description(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        assert "git commit message generator" in system_msg.lower()

    def test_contains_imperative_mood_instruction(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        assert "imperative" in system_msg.lower()

    def test_contains_subject_line_length_constraint(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        assert "72" in system_msg

    def test_contains_no_trailing_period_rule(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        # The rule about not ending with a period must be present
        assert "period" in system_msg.lower() or "not end" in system_msg.lower()

    def test_contains_blank_line_body_separator_rule(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        assert "blank line" in system_msg.lower()

    def test_imperative_example_present(self, generator, config_conventional):
        """The system message should give a concrete imperative mood example."""
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        # e.g. "Add feature" not "Added feature"
        assert "Add" in system_msg or "add" in system_msg.lower()


# ---------------------------------------------------------------------------
# System message — conventional commits ON
# ---------------------------------------------------------------------------

class TestSystemMessageConventionalCommitsOn:
    def test_includes_conventional_format_spec(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        assert "<type>" in system_msg or "type" in system_msg.lower()
        assert "<scope>" in system_msg or "scope" in system_msg.lower()
        assert "<description>" in system_msg or "description" in system_msg.lower()

    def test_lists_allowed_types(self, generator, config_conventional):
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        for t in ("feat", "fix", "docs", "style", "refactor", "test", "chore"):
            assert t in system_msg

    def test_format_pattern_present(self, generator, config_conventional):
        """The colon-space separator pattern should appear in the system message."""
        system_msg, _ = generator.build_prompt("diff", config_conventional)
        # The format spec uses ): or ): <description>
        assert "):" in system_msg or "<type>(" in system_msg


# ---------------------------------------------------------------------------
# System message — conventional commits OFF
# ---------------------------------------------------------------------------

class TestSystemMessageConventionalCommitsOff:
    def test_omits_type_scope_format(self, generator, config_plain):
        system_msg, _ = generator.build_prompt("diff", config_plain)
        # The conventional format spec should NOT appear
        assert "<type>(<scope>):" not in system_msg

    def test_omits_type_list(self, generator, config_plain):
        system_msg, _ = generator.build_prompt("diff", config_plain)
        # The conventional commit type list (as a comma-separated enumeration)
        # should not appear. We check for the distinctive multi-type pattern
        # rather than individual words that may appear in other contexts.
        import re
        # Match patterns like "feat, fix" or "feat|fix" that indicate a type list
        assert not re.search(r"\bfeat\b.*\bfix\b", system_msg, re.DOTALL), (
            "Conventional commit type list should not appear when conventional_commits=False"
        )

    def test_mentions_plain_subject(self, generator, config_plain):
        system_msg, _ = generator.build_prompt("diff", config_plain)
        assert "plain" in system_msg.lower() or "imperative" in system_msg.lower()


# ---------------------------------------------------------------------------
# User message — diff content
# ---------------------------------------------------------------------------

class TestUserMessage:
    def test_user_message_contains_diff(self, generator, config_conventional):
        diff = "diff --git a/foo.py b/foo.py\n+print('hello')"
        _, user_msg = generator.build_prompt(diff, config_conventional)
        assert user_msg == diff

    def test_user_message_is_exact_diff(self, generator, config_plain):
        diff = "some diff content\nwith multiple lines"
        _, user_msg = generator.build_prompt(diff, config_plain)
        assert user_msg == diff

    def test_empty_diff_passed_through(self, generator, config_conventional):
        _, user_msg = generator.build_prompt("", config_conventional)
        assert user_msg == ""

    def test_diff_not_modified(self, generator, config_conventional):
        diff = "--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new"
        _, user_msg = generator.build_prompt(diff, config_conventional)
        assert user_msg == diff


# ---------------------------------------------------------------------------
# Config toggle consistency
# ---------------------------------------------------------------------------

class TestConfigToggle:
    def test_conventional_true_differs_from_false(self, generator):
        diff = "some diff"
        system_on, _ = generator.build_prompt(diff, ResolvedConfig(conventional_commits=True))
        system_off, _ = generator.build_prompt(diff, ResolvedConfig(conventional_commits=False))
        assert system_on != system_off

    def test_user_message_same_regardless_of_conventional_flag(self, generator):
        diff = "some diff"
        _, user_on = generator.build_prompt(diff, ResolvedConfig(conventional_commits=True))
        _, user_off = generator.build_prompt(diff, ResolvedConfig(conventional_commits=False))
        assert user_on == user_off == diff


# ---------------------------------------------------------------------------
# validate_message
# ---------------------------------------------------------------------------

class TestValidateMessageReturnType:
    def test_returns_validation_result(self, generator):
        result = generator.validate_message("Add feature")
        assert isinstance(result, ValidationResult)

    def test_valid_result_has_no_errors(self, generator):
        result = generator.validate_message("Add feature")
        assert result.errors == []


class TestValidateMessageSubjectLineTooLong:
    def test_subject_exactly_72_chars_is_valid(self, generator):
        subject = "A" * 72
        result = generator.validate_message(subject)
        assert result.valid is True

    def test_subject_73_chars_is_invalid(self, generator):
        subject = "A" * 73
        result = generator.validate_message(subject)
        assert result.valid is False

    def test_subject_too_long_has_error_message(self, generator):
        subject = "A" * 80
        result = generator.validate_message(subject)
        assert any("72" in e for e in result.errors)

    def test_subject_too_long_error_count(self, generator):
        subject = "A" * 80
        result = generator.validate_message(subject)
        # At least one error for length
        assert len(result.errors) >= 1


class TestValidateMessageTrailingPeriod:
    def test_subject_ending_with_period_is_invalid(self, generator):
        result = generator.validate_message("Add feature.")
        assert result.valid is False

    def test_subject_ending_with_period_has_error(self, generator):
        result = generator.validate_message("Add feature.")
        assert any("period" in e.lower() for e in result.errors)

    def test_subject_not_ending_with_period_is_valid(self, generator):
        result = generator.validate_message("Add feature")
        assert result.valid is True

    def test_subject_ending_with_other_punctuation_is_valid(self, generator):
        result = generator.validate_message("Add feature!")
        assert result.valid is True


class TestValidateMessageBlankLineSeparator:
    def test_body_without_blank_line_is_invalid(self, generator):
        message = "Add feature\nThis is the body"
        result = generator.validate_message(message)
        assert result.valid is False

    def test_body_without_blank_line_has_error(self, generator):
        message = "Add feature\nThis is the body"
        result = generator.validate_message(message)
        assert any("blank line" in e.lower() for e in result.errors)

    def test_body_with_blank_line_is_valid(self, generator):
        message = "Add feature\n\nThis is the body"
        result = generator.validate_message(message)
        assert result.valid is True

    def test_body_with_blank_line_no_errors(self, generator):
        message = "Add feature\n\nThis is the body"
        result = generator.validate_message(message)
        assert result.errors == []


class TestValidateMessageParsing:
    def test_subject_line_populated(self, generator):
        result = generator.validate_message("Add feature")
        assert result.subject_line == "Add feature"

    def test_body_none_when_no_body(self, generator):
        result = generator.validate_message("Add feature")
        assert result.body is None

    def test_body_populated_when_present(self, generator):
        message = "Add feature\n\nDetailed explanation here"
        result = generator.validate_message(message)
        assert result.body == "Detailed explanation here"

    def test_multiline_body_preserved(self, generator):
        message = "Add feature\n\nLine one\nLine two"
        result = generator.validate_message(message)
        assert result.body == "Line one\nLine two"

    def test_subject_line_populated_with_body(self, generator):
        message = "Add feature\n\nBody text"
        result = generator.validate_message(message)
        assert result.subject_line == "Add feature"


class TestValidateMessageMultipleViolations:
    def test_long_subject_with_period_has_two_errors(self, generator):
        subject = "A" * 73 + "."
        result = generator.validate_message(subject)
        assert result.valid is False
        assert len(result.errors) == 2

    def test_all_three_violations(self, generator):
        # Long subject ending with period, body without blank line
        subject = "A" * 73 + "."
        message = subject + "\nBody without blank line"
        result = generator.validate_message(message)
        assert result.valid is False
        assert len(result.errors) == 3




# ---------------------------------------------------------------------------
# generate() — dependency-injected LLM client
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock
from acmg.llm_client import LLMPrompt, LLMResponse
from acmg.message_generator import GenerationResult


def _make_mock_client(response: LLMResponse) -> MagicMock:
    """Return a mock LLMClient whose complete() returns *response*."""
    client = MagicMock()
    client.complete.return_value = response
    return client


class TestGenerateLLMError:
    def test_llm_error_returns_success_false(self, config_conventional, capsys):
        error_response = LLMResponse(
            content="", success=False, error="API error: 500"
        )
        gen = MessageGenerator(llm_client=_make_mock_client(error_response))
        result = gen.generate("some diff", config_conventional)
        assert result.success is False

    def test_llm_error_returns_empty_message(self, config_conventional, capsys):
        error_response = LLMResponse(
            content="", success=False, error="API error: 500"
        )
        gen = MessageGenerator(llm_client=_make_mock_client(error_response))
        result = gen.generate("some diff", config_conventional)
        assert result.message == ""

    def test_llm_error_propagates_error_field(self, config_conventional, capsys):
        error_response = LLMResponse(
            content="", success=False, error="API error: 500"
        )
        gen = MessageGenerator(llm_client=_make_mock_client(error_response))
        result = gen.generate("some diff", config_conventional)
        assert result.error == "API error: 500"

    def test_llm_error_logs_to_stderr(self, config_conventional, capsys):
        error_response = LLMResponse(
            content="", success=False, error="API error: 500"
        )
        gen = MessageGenerator(llm_client=_make_mock_client(error_response))
        gen.generate("some diff", config_conventional)
        captured = capsys.readouterr()
        assert "API error: 500" in captured.err


class TestGenerateLLMTimeout:
    def test_timeout_returns_success_false(self, config_conventional, capsys):
        timeout_response = LLMResponse(
            content="", success=False, error="Request timed out", timed_out=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(timeout_response))
        result = gen.generate("some diff", config_conventional)
        assert result.success is False

    def test_timeout_returns_empty_message(self, config_conventional, capsys):
        timeout_response = LLMResponse(
            content="", success=False, error="Request timed out", timed_out=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(timeout_response))
        result = gen.generate("some diff", config_conventional)
        assert result.message == ""

    def test_timeout_logs_to_stderr(self, config_conventional, capsys):
        timeout_response = LLMResponse(
            content="", success=False, error="Request timed out", timed_out=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(timeout_response))
        gen.generate("some diff", config_conventional)
        captured = capsys.readouterr()
        assert captured.err != ""

    def test_timeout_error_field_set(self, config_conventional, capsys):
        timeout_response = LLMResponse(
            content="", success=False, error="Request timed out", timed_out=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(timeout_response))
        result = gen.generate("some diff", config_conventional)
        assert result.error is not None


class TestGenerateSuccess:
    def test_success_returns_success_true(self, config_conventional, capsys):
        ok_response = LLMResponse(
            content="feat: add login endpoint", success=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(ok_response))
        result = gen.generate("some diff", config_conventional)
        assert result.success is True

    def test_success_returns_message_content(self, config_conventional, capsys):
        ok_response = LLMResponse(
            content="feat: add login endpoint", success=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(ok_response))
        result = gen.generate("some diff", config_conventional)
        assert result.message == "feat: add login endpoint"

    def test_success_no_stderr_output(self, config_conventional, capsys):
        ok_response = LLMResponse(
            content="feat: add login endpoint", success=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(ok_response))
        gen.generate("some diff", config_conventional)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_success_error_field_is_none(self, config_conventional, capsys):
        ok_response = LLMResponse(
            content="feat: add login endpoint", success=True
        )
        gen = MessageGenerator(llm_client=_make_mock_client(ok_response))
        result = gen.generate("some diff", config_conventional)
        assert result.error is None

    def test_success_passes_diff_to_llm(self, config_conventional):
        ok_response = LLMResponse(content="fix: correct typo", success=True)
        mock_client = _make_mock_client(ok_response)
        gen = MessageGenerator(llm_client=mock_client)
        gen.generate("my diff content", config_conventional)
        # Verify complete() was called once
        mock_client.complete.assert_called_once()
        # The prompt passed should contain the diff as user_message
        call_args = mock_client.complete.call_args
        prompt_arg = call_args[0][0]
        assert prompt_arg.user_message == "my diff content"
