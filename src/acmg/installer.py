"""Git hook installer and uninstaller."""

import os
import stat
import sys

SENTINEL_BEGIN = "# BEGIN acmg"
SENTINEL_END = "# END acmg"
SENTINEL_BLOCK = "\n# BEGIN acmg\nacmg hook \"$1\" \"$2\" \"$3\"\n# END acmg\n"
HOOK_SHEBANG = "#!/bin/sh\n"
HOOK_FILENAME = "prepare-commit-msg"
GITIGNORE_ENTRY = ".git-acmg.json"


class Installer:
    def is_git_repository(self, directory: str) -> bool:
        """Return True when directory is inside a git repository."""
        current = os.path.abspath(directory)
        while True:
            if os.path.isdir(os.path.join(current, ".git")):
                return True
            parent = os.path.dirname(current)
            if parent == current:
                # Reached filesystem root
                return False
            current = parent

    def install(self, repo_root: str) -> None:
        """Install the prepare-commit-msg hook in the given repository."""
        if not self.is_git_repository(repo_root):
            print(
                f"Error: '{repo_root}' is not inside a git repository. "
                "Run 'acmg install' from within a git repository.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        hook_path = os.path.join(repo_root, ".git", "hooks", HOOK_FILENAME)

        # Read existing content or start fresh
        if os.path.exists(hook_path):
            with open(hook_path, "r") as f:
                content = f.read()
        else:
            content = HOOK_SHEBANG

        # Idempotency check: skip if sentinel block already present
        if SENTINEL_BEGIN in content:
            return

        # Append sentinel block
        new_content = content.rstrip("\n") + SENTINEL_BLOCK

        with open(hook_path, "w") as f:
            f.write(new_content)

        # Make the hook file executable
        os.chmod(
            hook_path,
            stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
        )

        # Ensure .git-acmg.json is in .gitignore to prevent accidental key commits
        self._ensure_gitignore(repo_root)

    def _ensure_gitignore(self, repo_root: str) -> None:
        """Add .git-acmg.json to .gitignore if not already present."""
        gitignore_path = os.path.join(repo_root, ".gitignore")

        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Check if already ignored (exact line or glob that would cover it)
            lines = [line.strip() for line in content.splitlines()]
            if GITIGNORE_ENTRY in lines:
                return
            # Append the entry
            separator = "\n" if content.endswith("\n") else "\n\n"
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(f"{separator}# acmg config (may contain API keys)\n{GITIGNORE_ENTRY}\n")
        else:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(f"# acmg config (may contain API keys)\n{GITIGNORE_ENTRY}\n")

        print(f"acmg: added {GITIGNORE_ENTRY} to .gitignore")

    def uninstall(self, repo_root: str) -> None:
        """Remove the acmg sentinel block from the prepare-commit-msg hook."""
        if not self.is_git_repository(repo_root):
            print(
                f"Error: '{repo_root}' is not inside a git repository. "
                "Run 'acmg uninstall' from within a git repository.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        hook_path = os.path.join(repo_root, ".git", "hooks", HOOK_FILENAME)

        # If the hook file doesn't exist, nothing to do
        if not os.path.exists(hook_path):
            return

        with open(hook_path, "r") as f:
            content = f.read()

        # If sentinel block is not present, nothing to do
        if SENTINEL_BEGIN not in content:
            return

        # Remove the sentinel block (including surrounding newlines)
        lines = content.splitlines(keepends=True)
        new_lines = []
        inside_block = False
        for line in lines:
            stripped = line.rstrip("\n").rstrip("\r")
            if stripped == SENTINEL_BEGIN:
                inside_block = True
                continue
            if stripped == SENTINEL_END:
                inside_block = False
                continue
            if not inside_block:
                new_lines.append(line)

        new_content = "".join(new_lines)

        with open(hook_path, "w") as f:
            f.write(new_content)
