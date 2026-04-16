"""Integration tests for the Installer class against a real git repository.

Tests use a real temp git repo (initialized with `git init`) to verify
end-to-end hook installation and uninstallation behavior.

Requirements: 5.1, 5.2, 5.3, 5.4
"""

import os
import stat
import subprocess

import pytest

from acmg.installer import Installer, SENTINEL_BEGIN, SENTINEL_END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path):
    """Initialise a real git repo in *path* with a user identity."""
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_git_repo(tmp_path):
    """Create a real git repository in a temp directory."""
    _init_git_repo(tmp_path)
    return tmp_path


@pytest.fixture
def installer():
    return Installer()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInstallerIntegration:
    """Integration tests for Installer using a real git repository."""

    def test_install_creates_hook_file(self, installer, real_git_repo):
        """acmg install creates the prepare-commit-msg hook file (Req 5.1)."""
        hook_path = real_git_repo / ".git" / "hooks" / "prepare-commit-msg"
        assert not hook_path.exists(), "Hook file should not exist before install"

        installer.install(str(real_git_repo))

        assert hook_path.exists(), "Hook file should be created after install"

    def test_install_hook_contains_sentinel_block(self, installer, real_git_repo):
        """Installed hook contains the acmg sentinel block (Req 5.1)."""
        installer.install(str(real_git_repo))

        hook_path = real_git_repo / ".git" / "hooks" / "prepare-commit-msg"
        content = hook_path.read_text()

        assert SENTINEL_BEGIN in content, "Hook should contain '# BEGIN acmg'"
        assert SENTINEL_END in content, "Hook should contain '# END acmg'"
        assert 'acmg hook "$1" "$2" "$3"' in content, "Hook should contain the acmg invocation"

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Windows does not support POSIX execute bits via os.chmod",
    )
    def test_install_makes_hook_executable(self, installer, real_git_repo):
        """Installed hook file is executable (Req 5.3)."""
        installer.install(str(real_git_repo))

        hook_path = real_git_repo / ".git" / "hooks" / "prepare-commit-msg"
        mode = os.stat(str(hook_path)).st_mode

        assert mode & stat.S_IXUSR, "Hook should be executable by owner"
        assert mode & stat.S_IXGRP, "Hook should be executable by group"
        assert mode & stat.S_IXOTH, "Hook should be executable by others"

    def test_uninstall_removes_sentinel_block(self, installer, real_git_repo):
        """acmg uninstall removes the sentinel block from the hook (Req 5.4)."""
        installer.install(str(real_git_repo))
        installer.uninstall(str(real_git_repo))

        hook_path = real_git_repo / ".git" / "hooks" / "prepare-commit-msg"
        content = hook_path.read_text()

        assert SENTINEL_BEGIN not in content, "Sentinel begin should be removed after uninstall"
        assert SENTINEL_END not in content, "Sentinel end should be removed after uninstall"
        assert 'acmg hook "$1" "$2" "$3"' not in content, "acmg invocation should be removed"

    def test_uninstall_preserves_existing_hook_content(self, installer, real_git_repo):
        """acmg uninstall preserves pre-existing hook content (Req 5.4)."""
        hook_path = real_git_repo / ".git" / "hooks" / "prepare-commit-msg"
        existing_content = "#!/bin/sh\necho 'pre-existing hook logic'\n"
        hook_path.write_text(existing_content)

        installer.install(str(real_git_repo))
        installer.uninstall(str(real_git_repo))

        content = hook_path.read_text()
        assert "echo 'pre-existing hook logic'" in content, (
            "Pre-existing hook content should be preserved after uninstall"
        )
        assert SENTINEL_BEGIN not in content, "Sentinel block should be removed"

    def test_install_appends_to_existing_hook(self, installer, real_git_repo):
        """acmg install appends to an existing hook rather than overwriting it (Req 5.2)."""
        hook_path = real_git_repo / ".git" / "hooks" / "prepare-commit-msg"
        existing_content = "#!/bin/sh\necho 'existing hook'\n"
        hook_path.write_text(existing_content)

        installer.install(str(real_git_repo))

        content = hook_path.read_text()
        assert "echo 'existing hook'" in content, "Existing hook content should be preserved"
        assert SENTINEL_BEGIN in content, "Sentinel block should be appended"
