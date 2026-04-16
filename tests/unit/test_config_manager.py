"""Unit tests for ConfigManager.load() — Requirements 6.1, 6.2, 6.3, 6.5."""

import json
import sys
from pathlib import Path

import pytest

from acmg.config_manager import ConfigManager, ResolvedConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: missing config files → built-in defaults
# ---------------------------------------------------------------------------

class TestLoadDefaults:
    def test_no_config_files_returns_defaults(self, tmp_path, monkeypatch):
        """When neither repo-level nor global config exists, defaults are returned."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

        cm = ConfigManager()
        config = cm.load(str(tmp_path))

        assert config == ResolvedConfig()

    def test_default_model(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        config = ConfigManager().load(str(tmp_path))
        assert config.model == "gpt-4o-mini"

    def test_default_base_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        config = ConfigManager().load(str(tmp_path))
        assert config.base_url == "https://api.openai.com/v1"

    def test_default_max_tokens(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        config = ConfigManager().load(str(tmp_path))
        assert config.max_tokens == 8000

    def test_default_auto_accept(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        config = ConfigManager().load(str(tmp_path))
        assert config.auto_accept is False

    def test_default_conventional_commits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        config = ConfigManager().load(str(tmp_path))
        assert config.conventional_commits is True

    def test_default_api_key_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        config = ConfigManager().load(str(tmp_path))
        assert config.api_key is None


# ---------------------------------------------------------------------------
# Tests: repo-level config is read
# ---------------------------------------------------------------------------

class TestLoadRepoConfig:
    def test_repo_model_is_loaded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"model": "gpt-4o"})
        config = ConfigManager().load(str(tmp_path))
        assert config.model == "gpt-4o"

    def test_repo_api_key_is_loaded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"apiKey": "sk-repo"})
        config = ConfigManager().load(str(tmp_path))
        assert config.api_key == "sk-repo"

    def test_repo_base_url_is_loaded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"baseUrl": "http://localhost:11434/v1"})
        config = ConfigManager().load(str(tmp_path))
        assert config.base_url == "http://localhost:11434/v1"

    def test_repo_max_tokens_is_loaded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"maxTokens": 4000})
        config = ConfigManager().load(str(tmp_path))
        assert config.max_tokens == 4000

    def test_repo_auto_accept_is_loaded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"autoAccept": True})
        config = ConfigManager().load(str(tmp_path))
        assert config.auto_accept is True

    def test_repo_conventional_commits_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"conventionalCommits": False})
        config = ConfigManager().load(str(tmp_path))
        assert config.conventional_commits is False


# ---------------------------------------------------------------------------
# Tests: global config is read
# ---------------------------------------------------------------------------

class TestLoadGlobalConfig:
    def test_global_model_is_loaded(self, tmp_path, monkeypatch):
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))
        _write_config(home_dir / ".git-acmg.json", {"model": "gpt-3.5-turbo"})
        config = ConfigManager().load(str(repo_dir))
        assert config.model == "gpt-3.5-turbo"

    def test_global_api_key_is_loaded(self, tmp_path, monkeypatch):
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))
        _write_config(home_dir / ".git-acmg.json", {"apiKey": "sk-global"})
        config = ConfigManager().load(str(repo_dir))
        assert config.api_key == "sk-global"


# ---------------------------------------------------------------------------
# Tests: merge precedence — repo overrides global, global overrides defaults
# ---------------------------------------------------------------------------

class TestMergePrecedence:
    def test_repo_overrides_global(self, tmp_path, monkeypatch):
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

        _write_config(home_dir / ".git-acmg.json", {"model": "gpt-3.5-turbo", "maxTokens": 2000})
        _write_config(repo_dir / ".git-acmg.json", {"model": "gpt-4o"})

        config = ConfigManager().load(str(repo_dir))
        assert config.model == "gpt-4o"          # repo wins
        assert config.max_tokens == 2000          # global fills in

    def test_global_overrides_defaults(self, tmp_path, monkeypatch):
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

        _write_config(home_dir / ".git-acmg.json", {"maxTokens": 1000})

        config = ConfigManager().load(str(repo_dir))
        assert config.max_tokens == 1000          # global overrides default 8000
        assert config.model == "gpt-4o-mini"      # default still applies

    def test_repo_only_key_not_in_global_uses_repo_value(self, tmp_path, monkeypatch):
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

        _write_config(home_dir / ".git-acmg.json", {})
        _write_config(repo_dir / ".git-acmg.json", {"apiKey": "sk-only-repo"})

        config = ConfigManager().load(str(repo_dir))
        assert config.api_key == "sk-only-repo"

    def test_all_three_levels(self, tmp_path, monkeypatch):
        """Repo > global > default for three different keys."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

        _write_config(home_dir / ".git-acmg.json", {"model": "global-model", "maxTokens": 500})
        _write_config(repo_dir / ".git-acmg.json", {"model": "repo-model"})

        config = ConfigManager().load(str(repo_dir))
        assert config.model == "repo-model"       # repo wins
        assert config.max_tokens == 500           # global wins over default
        assert config.auto_accept is False        # built-in default


# ---------------------------------------------------------------------------
# Tests: unrecognized keys — warning logged, recognized keys still loaded
# ---------------------------------------------------------------------------

class TestUnrecognizedKeys:
    def test_unrecognized_key_logs_warning_to_stderr(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"unknownKey": "value", "model": "gpt-4o"})

        ConfigManager().load(str(tmp_path))

        captured = capsys.readouterr()
        assert "unknownKey" in captured.err
        assert "warning" in captured.err.lower()

    def test_unrecognized_key_does_not_prevent_recognized_keys(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(
            tmp_path / ".git-acmg.json",
            {"bogusField": 123, "model": "gpt-4o", "maxTokens": 500},
        )

        config = ConfigManager().load(str(tmp_path))

        assert config.model == "gpt-4o"
        assert config.max_tokens == 500

    def test_multiple_unrecognized_keys_each_get_a_warning(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        _write_config(tmp_path / ".git-acmg.json", {"foo": 1, "bar": 2})

        ConfigManager().load(str(tmp_path))

        captured = capsys.readouterr()
        assert "foo" in captured.err
        assert "bar" in captured.err

    def test_unrecognized_key_in_global_config_logs_warning(self, tmp_path, monkeypatch, capsys):
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: home_dir))

        _write_config(home_dir / ".git-acmg.json", {"notAKey": "oops"})

        ConfigManager().load(str(repo_dir))

        captured = capsys.readouterr()
        assert "notAKey" in captured.err
