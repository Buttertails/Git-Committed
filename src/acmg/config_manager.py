"""Configuration management for acmg."""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


ConfigKey = Literal[
    "apiKey",
    "model",
    "baseUrl",
    "maxTokens",
    "autoAccept",
    "conventionalCommits",
]

# Mapping from JSON config key names to ResolvedConfig field names and types.
_KEY_MAP: dict[str, tuple[str, type]] = {
    "apiKey": ("api_key", str),
    "model": ("model", str),
    "baseUrl": ("base_url", str),
    "maxTokens": ("max_tokens", int),
    "autoAccept": ("auto_accept", bool),
    "conventionalCommits": ("conventional_commits", bool),
}


@dataclass
class ResolvedConfig:
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 8000
    auto_accept: bool = False
    conventional_commits: bool = True


def _load_json_file(path: Path) -> dict[str, Any]:
    """Read and parse a JSON config file. Returns an empty dict if the file
    does not exist or cannot be parsed."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def _apply_raw_config(
    config: ResolvedConfig,
    raw: dict[str, Any],
    source_label: str,
) -> None:
    """Apply recognized keys from *raw* onto *config* in-place.

    Emits a stderr warning for every unrecognized key found in *raw*.
    """
    for key, value in raw.items():
        if key not in _KEY_MAP:
            print(
                f"acmg: warning: unrecognized config key '{key}' in {source_label}",
                file=sys.stderr,
            )
            continue
        field_name, field_type = _KEY_MAP[key]
        # Coerce the value to the expected type when possible.
        try:
            coerced = field_type(value)
        except (TypeError, ValueError):
            print(
                f"acmg: warning: invalid value for config key '{key}' in {source_label}; "
                f"expected {field_type.__name__}",
                file=sys.stderr,
            )
            continue
        setattr(config, field_name, coerced)


class ConfigManager:
    def load(self, repo_root: str) -> ResolvedConfig:
        """Load and merge repo-level and global config files.

        Precedence (highest → lowest):
          1. Repository-level  <repo_root>/.git-acmg.json
          2. Global            ~/.git-acmg.json
          3. Built-in defaults (ResolvedConfig field defaults)
        """
        config = ResolvedConfig()

        global_path = Path.home() / ".git-acmg.json"
        repo_path = Path(repo_root) / ".git-acmg.json"

        global_raw = _load_json_file(global_path)
        repo_raw = _load_json_file(repo_path)

        # Apply global first, then repo-level so repo values overwrite global.
        _apply_raw_config(config, global_raw, str(global_path))
        _apply_raw_config(config, repo_raw, str(repo_path))

        return config

    def set(self, key: ConfigKey, value: str, repo_root: str) -> None:
        """Write a key-value pair to the repo-level config file.

        The *value* parameter is always a string (from the CLI). It is coerced
        to the correct type for the given key before being written:
          - int keys  (maxTokens):              "8000" → 8000
          - bool keys (autoAccept, conventionalCommits): "true"/"false" → bool
          - str keys  (apiKey, model, baseUrl): stored as-is
        """
        repo_path = Path(repo_root) / ".git-acmg.json"

        # Load existing content so we preserve unrelated keys.
        existing: dict[str, Any] = {}
        if repo_path.exists():
            try:
                with repo_path.open("r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            except (json.JSONDecodeError, OSError):
                existing = {}

        # Coerce the string value to the expected type.
        _, field_type = _KEY_MAP[key]
        if field_type is bool:
            coerced: Any = value.strip().lower() in ("true", "1", "yes")
        else:
            coerced = field_type(value)

        existing[key] = coerced

        with repo_path.open("w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
            fh.write("\n")
