"""Terminal I/O for user accept/edit/discard interaction."""

import os
import sys
from typing import Literal


UserChoice = Literal["accept", "edit", "discard"]

_CI_ENV_VARS = ("CI", "GITHUB_ACTIONS", "TRAVIS", "CIRCLECI", "JENKINS_URL")


class UserInteraction:
    def __init__(self, config=None) -> None:
        self._config = config

    def is_interactive(self) -> bool:
        """Return True when running in an interactive terminal."""
        if not sys.stdin.isatty():
            return False
        for var in _CI_ENV_VARS:
            if os.environ.get(var):
                return False
        if self._config is not None and getattr(self._config, "auto_accept", False):
            return False
        return True

    def prompt_user(self, message: str) -> UserChoice:
        """Display the generated message and prompt the user for a choice."""
        print("\n--- Generated commit message ---", file=sys.stderr)
        print(message, file=sys.stderr)
        print("--------------------------------", file=sys.stderr)

        while True:
            sys.stderr.write("\nAccept this message? [a]ccept / [e]dit / [d]iscard (default: accept): ")
            sys.stderr.flush()
            raw = sys.stdin.readline()
            choice = raw.strip().lower()

            if choice in ("", "a", "accept"):
                return "accept"
            elif choice in ("e", "edit"):
                return "edit"
            elif choice in ("d", "discard"):
                return "discard"
            else:
                print("Please enter 'a', 'e', or 'd'.", file=sys.stderr)

    def write_commit_message(self, file_path: str, message: str) -> None:
        """Write the commit message to the git commit message file."""
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(message)
