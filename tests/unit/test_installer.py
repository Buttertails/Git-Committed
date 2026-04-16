"""Unit tests for the Installer class."""

import os
import stat
import tempfile

import pytest

from acmg.installer import Installer, SENTINEL_BEGIN, SENTINEL_END


@pytest.fixture
def installer():
    return Installer()


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary directory that looks like a git repository."""
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def non_git_dir(tmp_path):
    """Create a temporary directory that is NOT a git repository."""
    return tmp_path


# ---------------------------------------------------------------------------
# is_git_repository
# ---------------------------------------------------------------------------

class TestIsGitRepository:
    def test_returns_true_when_git_dir_exists(self, installer, git_repo):
        assert installer.is_git_repository(str(git_repo)) is True

    def test_returns_true_for_subdirectory_of_git_repo(self, installer, git_repo):
        subdir = git_repo / "src" / "deep"
        subdir.mkdir(parents=True)
        assert installer.is_git_repository(str(subdir)) is True

    def test_returns_false_when_no_git_dir(self, installer, non_git_dir):
        assert installer.is_git_repository(str(non_git_dir)) is False


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

class TestInstall:
    def test_creates_hook_file_with_sentinel_block(self, installer, git_repo):
        installer.install(str(git_repo))
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        assert hook_path.exists()
        content = hook_path.read_text()
        assert SENTINEL_BEGIN in content
        assert SENTINEL_END in content
        assert 'acmg hook "$1" "$2" "$3"' in content

    def test_creates_hook_file_with_shebang_when_absent(self, installer, git_repo):
        installer.install(str(git_repo))
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        content = hook_path.read_text()
        assert content.startswith("#!/bin/sh")

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Windows does not support POSIX execute bits via os.chmod",
    )
    def test_makes_hook_file_executable(self, installer, git_repo):
        installer.install(str(git_repo))
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        mode = os.stat(str(hook_path)).st_mode
        # Owner execute
        assert mode & stat.S_IXUSR
        # Group execute
        assert mode & stat.S_IXGRP
        # Other execute
        assert mode & stat.S_IXOTH

    def test_install_is_idempotent(self, installer, git_repo):
        installer.install(str(git_repo))
        installer.install(str(git_repo))
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        content = hook_path.read_text()
        # Sentinel block should appear exactly once
        assert content.count(SENTINEL_BEGIN) == 1
        assert content.count(SENTINEL_END) == 1

    def test_install_appends_to_existing_hook_content(self, installer, git_repo):
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        existing_content = "#!/bin/sh\necho 'existing hook'\n"
        hook_path.write_text(existing_content)

        installer.install(str(git_repo))

        content = hook_path.read_text()
        assert "echo 'existing hook'" in content
        assert SENTINEL_BEGIN in content
        assert SENTINEL_END in content

    def test_install_raises_system_exit_in_non_git_directory(self, installer, non_git_dir):
        with pytest.raises(SystemExit) as exc_info:
            installer.install(str(non_git_dir))
        assert exc_info.value.code == 1

    def test_install_prints_error_to_stderr_in_non_git_directory(
        self, installer, non_git_dir, capsys
    ):
        with pytest.raises(SystemExit):
            installer.install(str(non_git_dir))
        captured = capsys.readouterr()
        assert "not inside a git repository" in captured.err


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

class TestUninstall:
    def test_uninstall_removes_sentinel_block(self, installer, git_repo):
        installer.install(str(git_repo))
        installer.uninstall(str(git_repo))
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        content = hook_path.read_text()
        assert SENTINEL_BEGIN not in content
        assert SENTINEL_END not in content
        assert 'acmg hook "$1" "$2" "$3"' not in content

    def test_uninstall_preserves_other_hook_content(self, installer, git_repo):
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        existing_content = "#!/bin/sh\necho 'existing hook'\n"
        hook_path.write_text(existing_content)

        installer.install(str(git_repo))
        installer.uninstall(str(git_repo))

        content = hook_path.read_text()
        assert "echo 'existing hook'" in content
        assert SENTINEL_BEGIN not in content

    def test_uninstall_does_nothing_when_hook_file_absent(self, installer, git_repo):
        # Should not raise
        installer.uninstall(str(git_repo))

    def test_uninstall_does_nothing_when_sentinel_absent(self, installer, git_repo):
        hook_path = git_repo / ".git" / "hooks" / "prepare-commit-msg"
        original = "#!/bin/sh\necho 'no sentinel here'\n"
        hook_path.write_text(original)

        installer.uninstall(str(git_repo))

        assert hook_path.read_text() == original

    def test_uninstall_raises_system_exit_in_non_git_directory(self, installer, non_git_dir):
        with pytest.raises(SystemExit) as exc_info:
            installer.uninstall(str(non_git_dir))
        assert exc_info.value.code == 1

    def test_uninstall_prints_error_to_stderr_in_non_git_directory(
        self, installer, non_git_dir, capsys
    ):
        with pytest.raises(SystemExit):
            installer.uninstall(str(non_git_dir))
        captured = capsys.readouterr()
        assert "not inside a git repository" in captured.err
