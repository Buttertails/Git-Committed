# Git-Committed (`acmg`)

**AI-powered git commit message generator.**

`acmg` (Auto Commit Message Generator) writes clear, conventional commit messages
for you by analyzing your staged changes with an LLM. It plugs directly into git's
commit workflow through a `prepare-commit-msg` hook, so messages are generated
inline the moment you run `git commit` — with full control to accept, edit, or
discard the suggestion.

---

## Features

- **Automatic commit messages** — generates a message from your staged diff using an OpenAI-compatible chat API.
- **Native git integration** — installs a `prepare-commit-msg` hook; no change to your normal `git commit` workflow.
- **Conventional Commits** — produces `type(scope): description` subject lines by default (toggleable).
- **Interactive control** — accept, edit, or discard the generated message in your terminal.
- **CI-safe** — automatically runs non-interactively in CI or when stdin is not a TTY.
- **Layered configuration** — merge a global (`~/.git-acmg.json`) and repo-level (`.git-acmg.json`) config, with sensible built-in defaults.
- **Token-aware** — estimates token usage and truncates large diffs to fit the model's limit.
- **Key safety** — installation adds `.git-acmg.json` to `.gitignore` so API keys are never committed.

---

## Installation

Requires Python 3.10+.

```bash
# Clone and install
git clone https://github.com/Buttertails/Git-Committed.git
cd Git-Committed
pip install .
```

This exposes the `acmg` command.

---

## Quick start

From inside any git repository:

```bash
# 1. Install the commit hook for this repo
acmg install

# 2. Configure your API key (or set OPENAI_API_KEY in your environment)
acmg config set apiKey sk-your-key-here

# 3. Commit as usual — a message is generated for you
git add .
git commit
```

When you commit, `acmg` reads your staged diff, generates a message, and prompts:

```
--- Generated commit message ---
feat(auth): add token refresh handling
--------------------------------

Accept this message? [a]ccept / [e]dit / [d]iscard (default: accept):
```

---

## Configuration

Configuration is read from two files and merged (repo-level overrides global,
which overrides built-in defaults):

1. Repository-level: `<repo>/.git-acmg.json`
2. Global: `~/.git-acmg.json`

Set values with `acmg config set <key> <value>`:

```bash
acmg config set model gpt-4o-mini
acmg config set maxTokens 8000
acmg config set conventionalCommits true
acmg config set autoAccept false
```

| Key                   | Type    | Default                        | Description                                              |
| --------------------- | ------- | ------------------------------ | -------------------------------------------------------- |
| `apiKey`              | string  | —                              | API key. Overridden by the `OPENAI_API_KEY` env var.     |
| `model`               | string  | `gpt-4o-mini`                  | Chat model to use.                                       |
| `baseUrl`             | string  | `https://api.openai.com/v1`    | API base URL (point at any OpenAI-compatible endpoint).  |
| `maxTokens`           | int     | `8000`                         | Token budget; larger diffs are truncated to fit.         |
| `autoAccept`          | bool    | `false`                        | Accept generated messages without prompting.             |
| `conventionalCommits` | bool    | `true`                         | Emit `type(scope): description` subject lines.           |

> **API key resolution order:** `OPENAI_API_KEY` environment variable → `apiKey` in config.
> Prefer the environment variable to keep keys out of files.

---

## Commands

| Command                          | Description                                                        |
| -------------------------------- | ------------------------------------------------------------------ |
| `acmg install`                   | Install the `prepare-commit-msg` hook in the current repository.   |
| `acmg uninstall`                 | Remove the `acmg` hook from the current repository.                |
| `acmg config set <key> <value>`  | Set a configuration key in the repo-level config file.             |
| `acmg hook <file> [source] [sha]`| Internal — invoked by git's hook. Not run manually.                |

`acmg` skips generation for merge, squash, amend, and template commits so it
never interferes with those flows.

---

## How it works

1. **Diff extraction** — runs `git diff --cached` to capture the staged changes.
2. **Truncation** — estimates tokens and trims oldest hunks if the diff exceeds `maxTokens`.
3. **Prompt building** — constructs a system prompt enforcing imperative mood, a 72-char subject limit, and (optionally) Conventional Commits format.
4. **LLM request** — sends the prompt to the configured chat endpoint via `httpx`.
5. **User interaction** — writes the message straight to git's commit file in non-interactive mode, or prompts to accept/edit/discard in a terminal.

### Architecture

| Module                 | Responsibility                                            |
| ---------------------- | --------------------------------------------------------- |
| `cli.py`               | Argument parsing and subcommand dispatch.                 |
| `diff_extractor.py`    | Reads and truncates the staged git diff.                  |
| `message_generator.py` | Builds prompts and validates generated messages.          |
| `llm_client.py`        | HTTP client for the chat completions API.                 |
| `config_manager.py`    | Loads, merges, and writes layered configuration.          |
| `installer.py`         | Installs/uninstalls the git hook idempotently.            |
| `user_interaction.py`  | Terminal prompts and commit-file writing.                 |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest
```

Tests are organized into `tests/unit` and `tests/integration`.

---

## License

MIT
