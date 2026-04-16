# Implementation Plan: Auto Commit Message Generator

## Overview

Implement the `acmg` Python package as a pip-installable CLI tool that integrates with git's `prepare-commit-msg` hook to automatically generate commit messages using an LLM. The implementation follows the component architecture defined in the design: `DiffExtractor`, `MessageGenerator`, `LLMClient`, `UserInteraction`, `Installer`, `ConfigManager`, and a CLI entry point.

## Tasks

- [x] 1. Set up project structure and core data models
  - Create `src/acmg/` package directory with `__init__.py`
  - Create `pyproject.toml` with package metadata, entry point `acmg`, and dependencies (`httpx`, `openai`)
  - Add `[project.optional-dependencies]` dev group with `pytest`, `hypothesis`, `pytest-cov`
  - Define all dataclasses in their respective modules: `DiffResult`, `GenerationResult`, `ValidationResult`, `LLMPrompt`, `LLMResponse`, `ResolvedConfig`
  - Define `ConfigKey` `Literal` type alias in `config_manager.py`
  - Define `UserChoice` `Literal` type alias in `user_interaction.py`
  - Create `tests/unit/`, `tests/property/`, `tests/integration/` directories with `__init__.py` files
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1_

- [x] 2. Implement `ConfigManager`
  - [x] 2.1 Implement `ConfigManager.load(repo_root)` in `src/acmg/config_manager.py`
    - Read `.git-acmg.json` from `repo_root` (repo-level) and `~/.git-acmg.json` (global)
    - Merge configs with repo-level values taking precedence over global, global over built-in defaults
    - Log a `stderr` warning for each unrecognized key; continue loading recognized keys
    - Return a fully populated `ResolvedConfig` instance
    - _Requirements: 6.1, 6.2, 6.3, 6.5_
  - [x] 2.2 Implement `ConfigManager.set(key, value, repo_root)` in `src/acmg/config_manager.py`
    - Write the key-value pair to the repo-level `.git-acmg.json`, creating the file if absent
    - Preserve existing keys in the file
    - _Requirements: 6.4_
  - [ ]* 2.3 Write property test for config merge precedence (Property 4)
    - **Property 4: Config merge respects precedence**
    - Use `st.fixed_dictionaries(...)` for repo and global config objects (either or both may be absent)
    - Assert every repo-level key has the repo-level value, absent repo keys fall back to global, absent both fall back to defaults
    - Annotate: `# Feature: auto-commit-message-generator, Property 4: Config merge respects precedence`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_config_merge_property.py`
    - **Validates: Requirements 6.1, 6.2, 6.3**
  - [ ]* 2.4 Write property test for config set round-trip (Property 5)
    - **Property 5: Config set round-trip**
    - Use `st.sampled_from(config_keys)` and `st.text()` for value; call `set` then `load` and assert the key equals the written value
    - Annotate: `# Feature: auto-commit-message-generator, Property 5: Config set round-trip`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_config_merge_property.py`
    - **Validates: Requirements 6.4**
  - [ ]* 2.5 Write unit tests for `ConfigManager`
    - Test unrecognized key logs warning to stderr and recognized keys are still loaded
    - Test missing config files return built-in defaults
    - File: `tests/unit/test_config_manager.py`
    - _Requirements: 6.5_

- [x] 3. Implement `DiffExtractor`
  - [x] 3.1 Implement `DiffExtractor.extract_staged_diff()` in `src/acmg/diff_extractor.py`
    - Run `git diff --cached` via `subprocess`, capture stdout
    - Set `is_empty=True` and return early when output is empty
    - Include renames, deletions, and new file additions (default `git diff --cached` behavior)
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 3.2 Implement `DiffExtractor.truncate_diff(diff, max_tokens)` in `src/acmg/diff_extractor.py`
    - Estimate token count as `ceil(len(diff) / 4)`
    - Split diff into hunks; greedily include hunks from the end until token budget is exhausted
    - Prepend a header comment indicating the diff was truncated
    - Set `was_truncated=True` on the returned `DiffResult`
    - _Requirements: 1.4_
  - [ ]* 3.3 Write property test for diff truncation (Property 1)
    - **Property 1: Diff truncation fits within token limit**
    - Use `st.text()` for diff content, `st.integers(min_value=100)` for `max_tokens`
    - Assert `ceil(len(result) / 4) <= max_tokens` and result contains only hunks from the original diff
    - Annotate: `# Feature: auto-commit-message-generator, Property 1: Diff truncation fits within token limit`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_diff_truncation_property.py`
    - **Validates: Requirements 1.4**
  - [ ]* 3.4 Write unit tests for `DiffExtractor`
    - Test empty diff sets `is_empty=True`
    - Test diff within token limit is not truncated
    - Test diff exceeding token limit is truncated and header comment is present
    - File: `tests/unit/test_diff_extractor.py`
    - _Requirements: 1.1, 1.2, 1.4_

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement `MessageGenerator`
  - [x] 5.1 Implement `MessageGenerator.build_prompt(diff, config)` in `src/acmg/message_generator.py`
    - Return a `(system_message, user_message)` tuple
    - System message includes: role, imperative mood instruction, subject ≤72 chars, no trailing period, blank line before body
    - Include conventional commits format spec (`<type>(<scope>): <description>`) when `config.conventional_commits` is `True`; omit it when `False`
    - User message contains the diff content
    - _Requirements: 2.2, 2.4, 7.1, 7.2_
  - [x] 5.2 Implement `MessageGenerator.validate_message(message)` in `src/acmg/message_generator.py`
    - Return `valid: False` when subject line exceeds 72 characters
    - Return `valid: False` when subject line ends with a period
    - Return `valid: False` when a body is present but no blank line separates it from the subject
    - Return `valid: True` with parsed `subject_line` and `body` when all rules pass
    - _Requirements: 2.3, 7.3, 7.4_
  - [x] 5.3 Implement `MessageGenerator.generate(diff, config)` in `src/acmg/message_generator.py`
    - Call `build_prompt`, then `LLMClient.complete()`
    - On success, validate the response with `validate_message`; return `GenerationResult(success=True, message=...)`
    - On `LLMResponse.success=False` or timeout, log error to stderr and return `GenerationResult(success=False, error=...)`
    - _Requirements: 2.1, 2.5_
  - [ ]* 5.4 Write property test for prompt construction (Property 2)
    - **Property 2: Prompt construction reflects config**
    - Use `st.text()` for diff, `st.booleans()` for `conventional_commits`
    - Assert imperative mood instruction always present in system message; conventional commits spec present/absent per flag; diff always in user message
    - Annotate: `# Feature: auto-commit-message-generator, Property 2: Prompt construction reflects config`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_prompt_construction_property.py`
    - **Validates: Requirements 2.2, 2.4, 7.1, 7.2**
  - [ ]* 5.5 Write property test for message validation (Property 3)
    - **Property 3: Message validation enforces format rules**
    - Use `st.text()` for message content
    - Assert `valid: False` for subject >72 chars, subject ending with period, body without blank line separator; `valid: True` when all rules satisfied
    - Annotate: `# Feature: auto-commit-message-generator, Property 3: Message validation enforces format rules`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_message_validation_property.py`
    - **Validates: Requirements 2.3, 7.3, 7.4**
  - [ ]* 5.6 Write unit tests for `MessageGenerator`
    - Test LLM error returns `success=False` and logs to stderr
    - Test LLM timeout returns `success=False` and logs to stderr
    - File: `tests/unit/test_message_generator.py`
    - _Requirements: 2.5_

- [x] 6. Implement `LLMClient`
  - [x] 6.1 Implement `LLMClient.complete(prompt, config)` in `src/acmg/llm_client.py`
    - Resolve API key: `OPENAI_API_KEY` env var takes precedence over `config.api_key`; if neither is set, print descriptive error to stderr and return `LLMResponse(success=False)`
    - Send POST to `{config.base_url}/chat/completions` using `httpx` with `timeout=15.0`
    - Use `config.model` (default `gpt-4o-mini`) in the request body
    - On HTTP error or `httpx.TimeoutException`, return `LLMResponse(success=False, timed_out=True/False, error=...)`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 2.6_
  - [ ]* 6.2 Write property test for API request timeout (Property 8)
    - **Property 8: API request timeout is always enforced**
    - Use `st.fixed_dictionaries(...)` for any config/prompt combination; mock `httpx.Client` and assert `timeout` argument equals `15.0`
    - Annotate: `# Feature: auto-commit-message-generator, Property 8: API request timeout is always enforced`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_api_client_property.py`
    - **Validates: Requirements 3.4**
  - [ ]* 6.3 Write property test for API key resolution (Property 9)
    - **Property 9: API key resolution follows precedence**
    - Use `st.one_of(st.none(), st.text())` for env var and config key; assert env var used when set, config key used when env var absent, `None` when both absent
    - Annotate: `# Feature: auto-commit-message-generator, Property 9: API key resolution follows precedence`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_api_client_property.py`
    - **Validates: Requirements 3.1**
  - [ ]* 6.4 Write unit tests for `LLMClient`
    - Test missing API key prints descriptive error to stderr and returns `success=False`
    - Test HTTP error returns `success=False` with error message
    - Test timeout returns `success=False` with `timed_out=True`
    - File: `tests/unit/test_llm_client.py`
    - _Requirements: 3.2, 3.4_

- [x] 7. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement `UserInteraction`
  - [x] 8.1 Implement `UserInteraction.is_interactive()` in `src/acmg/user_interaction.py`
    - Return `False` when `sys.stdin.isatty()` is `False`
    - Return `False` when `CI`, `GITHUB_ACTIONS`, or similar CI env vars are set
    - Return `False` when `config.auto_accept` is `True`
    - Return `True` otherwise
    - _Requirements: 4.6_
  - [x] 8.2 Implement `UserInteraction.prompt_user(message)` in `src/acmg/user_interaction.py`
    - Display the generated commit message to the terminal
    - Prompt with three options: accept, edit, discard
    - Return the appropriate `UserChoice` literal
    - _Requirements: 4.1, 4.2_
  - [x] 8.3 Implement `UserInteraction.write_commit_message(file_path, message)` in `src/acmg/user_interaction.py`
    - Write `message` to `file_path` (the commit message file passed by git)
    - _Requirements: 4.3_
  - [ ]* 8.4 Write property test for non-interactive auto-accept (Property 10)
    - **Property 10: Non-interactive environments auto-accept**
    - Use `st.text()` for message, `st.booleans()` for CI flags and `auto_accept`; assert no prompt is shown and message is written when `is_interactive()` returns `False`
    - Annotate: `# Feature: auto-commit-message-generator, Property 10: Non-interactive environments auto-accept`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_api_client_property.py`
    - **Validates: Requirements 4.6**
  - [ ]* 8.5 Write unit tests for `UserInteraction`
    - Test user accept → message written to commit file
    - Test user edit → file pre-populated, editor opened
    - Test user discard → commit file left empty
    - File: `tests/unit/test_user_interaction.py`
    - _Requirements: 4.3, 4.4, 4.5_

- [x] 9. Implement `Installer`
  - [x] 9.1 Implement `Installer.is_git_repository(directory)` in `src/acmg/installer.py`
    - Return `True` when a `.git` directory exists at or above `directory`
    - _Requirements: 5.5_
  - [x] 9.2 Implement `Installer.install(repo_root)` in `src/acmg/installer.py`
    - Locate `.git/hooks/prepare-commit-msg`; create the file if absent
    - If the file exists and already contains the sentinel block, skip (idempotent)
    - If the file exists without the sentinel block, append the sentinel block
    - Sentinel block format:
      ```sh
      # BEGIN acmg
      acmg hook "$1" "$2" "$3"
      # END acmg
      ```
    - Make the hook file executable (`chmod +x`)
    - Print a descriptive error and exit with code 1 if not in a git repository
    - _Requirements: 5.1, 5.2, 5.3, 5.5_
  - [x] 9.3 Implement `Installer.uninstall(repo_root)` in `src/acmg/installer.py`
    - Remove only the sentinel block (`# BEGIN acmg` … `# END acmg`) from the hook file
    - Leave all other hook content intact
    - Print a descriptive error and exit with code 1 if not in a git repository
    - _Requirements: 5.4, 5.5_
  - [ ]* 9.4 Write property test for hook install preserves existing content (Property 6)
    - **Property 6: Hook install preserves existing content**
    - Use `st.text()` for existing hook file content; assert resulting file contains original content AND the sentinel block
    - Annotate: `# Feature: auto-commit-message-generator, Property 6: Hook install preserves existing content`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_hook_content_property.py`
    - **Validates: Requirements 5.2**
  - [ ]* 9.5 Write property test for hook install/uninstall round-trip (Property 7)
    - **Property 7: Hook install/uninstall round-trip**
    - Use `st.text()` for existing hook file content; call `install` then `uninstall` and assert file is exactly restored to original content
    - Annotate: `# Feature: auto-commit-message-generator, Property 7: Hook install/uninstall round-trip`
    - `@settings(max_examples=100)`
    - File: `tests/property/test_hook_content_property.py`
    - **Validates: Requirements 5.4**
  - [ ]* 9.6 Write unit tests for `Installer`
    - Test hook file is made executable after install
    - Test non-git directory prints descriptive error and exits with code 1
    - Test install is idempotent (running twice does not duplicate sentinel block)
    - File: `tests/unit/test_installer.py`
    - _Requirements: 5.3, 5.5_

- [x] 10. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement the `acmg` CLI entry point and hook runner
  - [x] 11.1 Implement the `acmg hook` subcommand in `src/acmg/cli.py`
    - Accept `$1` (commit message file path), `$2` (commit source), `$3` (SHA) as arguments
    - Skip generation when `$2` is `merge`, `squash`, `commit`, or `template`
    - Call `DiffExtractor.extract_staged_diff()`; exit cleanly when `is_empty=True`
    - Call `DiffExtractor.truncate_diff()` when diff exceeds `config.max_tokens`
    - Call `MessageGenerator.generate()`; on `success=False`, exit cleanly
    - Call `UserInteraction.is_interactive()`:
      - If non-interactive: call `write_commit_message()` directly
      - If interactive: call `prompt_user()` and handle accept/edit/discard
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  - [x] 11.2 Implement `acmg install` and `acmg uninstall` subcommands in `src/acmg/cli.py`
    - `acmg install`: resolve repo root, call `Installer.install()`
    - `acmg uninstall`: resolve repo root, call `Installer.uninstall()`
    - _Requirements: 5.1, 5.4, 5.5_
  - [x] 11.3 Implement `acmg config set <key> <value>` subcommand in `src/acmg/cli.py`
    - Resolve repo root, call `ConfigManager.set(key, value, repo_root)`
    - _Requirements: 6.4_
  - [ ]* 11.4 Write unit tests for CLI entry point
    - Test `acmg hook` skips generation for `merge`, `squash`, `commit`, `template` sources
    - Test `acmg hook` exits cleanly on empty diff
    - Test `acmg hook` exits cleanly on LLM failure
    - File: `tests/unit/test_cli.py`
    - _Requirements: 1.2, 2.5, 4.6_

- [x] 12. Write integration tests
  - [x] 12.1 Write git hook integration test in `tests/integration/test_git_hook_integration.py`
    - Create a temp git repo, stage a file, invoke the hook, verify diff is captured
    - Mock the OpenAI endpoint with `httpx` transport mock; run full hook flow; verify message written to commit file
    - _Requirements: 1.1, 1.3, 3.3_
  - [x] 12.2 Write installer integration test in `tests/integration/test_installer_integration.py`
    - Run `acmg install` in a temp git repo; verify hook file created, contains sentinel block, and is executable
    - Run `acmg uninstall`; verify sentinel block removed and other content preserved
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints at tasks 4, 7, 10, and 13 ensure incremental validation
- Property tests (Properties 1–10) validate universal correctness guarantees using Hypothesis with `@settings(max_examples=100)`
- Unit tests validate specific examples and error conditions
- Integration tests use real temp git repositories and mocked HTTP transports
- The `acmg hook` subcommand is the critical path; all other subcommands (`install`, `uninstall`, `config set`) are supporting infrastructure
