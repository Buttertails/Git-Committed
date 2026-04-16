# Requirements Document

## Introduction

This feature is an NLP-powered automatic git commit message generator. It integrates into the git workflow via a prepare-commit-msg hook, intercepts staged changes before a commit is finalized, sends the diff to a language model (defaulting to the OpenAI API), and presents the generated message to the user for acceptance, editing, or rejection. The goal is to reduce the cognitive overhead of writing commit messages while remaining non-invasive and transparent to the user.

## Glossary

- **System**: The auto-commit-message-generator tool as a whole.
- **Hook**: The git `prepare-commit-msg` hook script installed by the System.
- **Diff**: The unified diff output of staged changes produced by `git diff --cached`.
- **Message_Generator**: The component responsible for sending the Diff to the language model and receiving a commit message.
- **LLM_Client**: The component that communicates with an external language model API (e.g., OpenAI).
- **Prompt**: The structured input sent to the LLM_Client containing the Diff and instructions.
- **Commit_Message**: A short, single-line summary (≤72 characters) optionally followed by a blank line and a body, describing the intent of the staged changes.
- **User**: The developer invoking `git commit`.
- **Config_File**: A per-repository or global configuration file (`.git-acmg.json` or `~/.git-acmg.json`) storing API keys, model selection, and preferences.
- **Installer**: The CLI command (`acmg install`) that registers the Hook in a git repository.

---

## Requirements

### Requirement 1: Diff Extraction

**User Story:** As a developer, I want the tool to automatically extract staged changes, so that I do not have to manually provide the diff as input.

#### Acceptance Criteria

1. WHEN the User runs `git commit`, THE Hook SHALL extract the full unified diff of all staged changes using `git diff --cached`.
2. IF no files are staged, THEN THE Hook SHALL exit without invoking the Message_Generator and allow the git commit process to proceed normally.
3. THE Hook SHALL include file renames, deletions, and new file additions in the extracted Diff.
4. WHEN the Diff exceeds 8,000 tokens, THE Message_Generator SHALL truncate the Diff to the most recently changed hunks to fit within the token limit.

---

### Requirement 2: Commit Message Generation

**User Story:** As a developer, I want the tool to generate a concise and descriptive commit message from my staged changes, so that I spend less time writing commit messages.

#### Acceptance Criteria

1. WHEN a non-empty Diff is available, THE Message_Generator SHALL send a Prompt containing the Diff to the LLM_Client and receive a Commit_Message in response.
2. THE Message_Generator SHALL construct the Prompt to instruct the model to produce a Commit_Message in the imperative mood (e.g., "Add feature" not "Added feature").
3. THE Commit_Message subject line produced by the Message_Generator SHALL be no longer than 72 characters.
4. THE Message_Generator SHALL request a single-sentence subject line and an optional multi-line body from the model.
5. IF the LLM_Client returns an error or times out after 15 seconds, THEN THE Message_Generator SHALL log the error to stderr and allow the git commit process to continue with an empty or user-provided message.
6. WHERE a Config_File specifies a preferred model identifier, THE LLM_Client SHALL use that model; otherwise THE LLM_Client SHALL default to `gpt-4o-mini`.

---

### Requirement 3: OpenAI API Integration

**User Story:** As a developer, I want the tool to use the OpenAI API so that I can leverage a high-quality language model with my existing API key.

#### Acceptance Criteria

1. THE LLM_Client SHALL authenticate with the OpenAI API using an API key read from the `OPENAI_API_KEY` environment variable or the Config_File.
2. IF the API key is absent from both the environment and the Config_File, THEN THE LLM_Client SHALL print a descriptive error message to stderr and exit with a non-zero status code without blocking the git commit.
3. THE LLM_Client SHALL send requests to the OpenAI Chat Completions endpoint using the configured model.
4. THE LLM_Client SHALL set a request timeout of 15 seconds for all API calls.
5. WHERE the Config_File specifies an alternative OpenAI-compatible base URL, THE LLM_Client SHALL use that URL instead of the default OpenAI endpoint, enabling use of local or third-party models.

---

### Requirement 4: User Interaction and Confirmation

**User Story:** As a developer, I want to review the generated commit message and choose to accept, edit, or reject it, so that I remain in control of what gets committed.

#### Acceptance Criteria

1. WHEN a Commit_Message is generated, THE Hook SHALL display the Commit_Message to the User in the terminal before the git commit editor opens.
2. THE Hook SHALL prompt the User with three options: accept the generated message, open it in the git commit editor for editing, or discard it and write a message manually.
3. WHEN the User accepts the Commit_Message, THE Hook SHALL write the Commit_Message into the commit message file so that git uses it without opening an editor.
4. WHEN the User chooses to edit, THE Hook SHALL pre-populate the git commit editor with the generated Commit_Message.
5. WHEN the User discards the Commit_Message, THE Hook SHALL leave the commit message file empty so that git opens the editor with the default template.
6. IF the terminal is non-interactive (e.g., called from a script or CI environment), THEN THE Hook SHALL automatically write the generated Commit_Message without prompting the User.

---

### Requirement 5: Git Hook Installation

**User Story:** As a developer, I want a simple installation command that wires the tool into my repository's git hooks, so that the integration is automatic and I do not have to configure it manually.

#### Acceptance Criteria

1. THE Installer SHALL provide a CLI command (`acmg install`) that installs the Hook as the `prepare-commit-msg` hook in the current repository's `.git/hooks/` directory.
2. WHEN an existing `prepare-commit-msg` hook is present, THE Installer SHALL append a call to the System rather than overwriting the existing hook.
3. THE Installer SHALL make the installed Hook file executable.
4. THE System SHALL provide an `acmg uninstall` command that removes the System's lines from the `prepare-commit-msg` hook without deleting unrelated hook content.
5. IF the current directory is not inside a git repository, THEN THE Installer SHALL print a descriptive error message and exit with a non-zero status code.

---

### Requirement 6: Configuration Management

**User Story:** As a developer, I want to configure the tool's behavior (model, API key, token limits) without modifying the hook script, so that settings are portable and easy to update.

#### Acceptance Criteria

1. THE System SHALL read configuration from a Config_File located at `.git-acmg.json` in the repository root, falling back to `~/.git-acmg.json` for global settings.
2. THE System SHALL support the following configuration keys: `apiKey`, `model`, `baseUrl`, `maxTokens`, and `autoAccept`.
3. WHEN both a repository-level and a global Config_File exist, THE System SHALL merge the two, with repository-level values taking precedence over global values.
4. THE System SHALL provide an `acmg config set <key> <value>` command that writes a key-value pair to the repository-level Config_File.
5. IF a Config_File contains an unrecognized key, THEN THE System SHALL log a warning to stderr and continue with the recognized keys.

---

### Requirement 7: Commit Message Format Compliance

**User Story:** As a developer, I want generated messages to follow the conventional commit format, so that my project history is consistent and tooling that parses commit messages continues to work.

#### Acceptance Criteria

1. THE Message_Generator SHALL instruct the model to produce a Commit_Message subject line in the format `<type>(<scope>): <description>`, where `type` is one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`, or `chore`.
2. WHERE the Config_File sets `conventionalCommits` to `false`, THE Message_Generator SHALL omit the `<type>(<scope>):` prefix and produce a plain imperative subject line.
3. THE Message_Generator SHALL ensure the generated subject line does not end with a period.
4. WHEN a body is included in the Commit_Message, THE Message_Generator SHALL ensure a blank line separates the subject from the body.
