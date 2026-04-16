"""CLI entry point for the acmg command."""

import argparse
import subprocess
import sys


# Sources that indicate git is handling the message itself — skip generation.
_SKIP_SOURCES = {"merge", "squash", "commit", "template"}


def _get_repo_root() -> str:
    """Return the absolute path to the repository root.

    Runs ``git rev-parse --show-toplevel``. Prints an error and exits with
    code 1 if the command fails (e.g. not inside a git repository).
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(
            "acmg: error: not inside a git repository (or git is not installed).",
            file=sys.stderr,
        )
        sys.exit(1)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_hook(args: argparse.Namespace) -> None:
    """Handle ``acmg hook <commit_msg_file> [<source>] [<sha>]``."""
    from acmg.config_manager import ConfigManager
    from acmg.diff_extractor import DiffExtractor
    from acmg.message_generator import MessageGenerator
    from acmg.user_interaction import UserInteraction

    commit_msg_file: str = args.commit_msg_file
    source: str = args.source or ""
    # sha is available as args.sha but not used in logic

    # Skip generation for merge, squash, amend, and template commits.
    if source in _SKIP_SOURCES:
        sys.exit(0)

    repo_root = _get_repo_root()
    config = ConfigManager().load(repo_root)

    extractor = DiffExtractor()
    diff_result = extractor.extract_staged_diff()

    if diff_result.is_empty:
        sys.exit(0)

    diff = diff_result.diff

    # Truncate if the diff exceeds the configured token limit.
    import math
    estimated_tokens = math.ceil(len(diff) / 4)
    if estimated_tokens > config.max_tokens:
        diff = extractor.truncate_diff(diff, config.max_tokens)

    gen_result = MessageGenerator().generate(diff, config)
    if not gen_result.success:
        sys.exit(0)

    message = gen_result.message
    ui = UserInteraction(config=config)

    if not ui.is_interactive():
        ui.write_commit_message(commit_msg_file, message)
    else:
        choice = ui.prompt_user(message)
        if choice == "accept":
            ui.write_commit_message(commit_msg_file, message)
        elif choice == "edit":
            # Pre-populate the file; git will open the editor with it.
            ui.write_commit_message(commit_msg_file, message)
        elif choice == "discard":
            # Leave the file as-is; git opens the editor with the default template.
            pass


def _cmd_install(args: argparse.Namespace) -> None:
    """Handle ``acmg install``."""
    from acmg.installer import Installer

    repo_root = _get_repo_root()
    Installer().install(repo_root)


def _cmd_uninstall(args: argparse.Namespace) -> None:
    """Handle ``acmg uninstall``."""
    from acmg.installer import Installer

    repo_root = _get_repo_root()
    Installer().uninstall(repo_root)


def _cmd_config_set(args: argparse.Namespace) -> None:
    """Handle ``acmg config set <key> <value>``."""
    from acmg.config_manager import ConfigManager

    repo_root = _get_repo_root()
    ConfigManager().set(args.key, args.value, repo_root)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acmg",
        description="Auto commit message generator — git hook integration.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # -- hook ----------------------------------------------------------------
    hook_parser = subparsers.add_parser(
        "hook",
        help="Run the commit message generator (called by git's prepare-commit-msg hook).",
    )
    hook_parser.add_argument(
        "commit_msg_file",
        metavar="<commit-msg-file>",
        help="Path to the commit message file ($1 from git).",
    )
    hook_parser.add_argument(
        "source",
        metavar="<source>",
        nargs="?",
        default="",
        help="Commit source ($2 from git): message, template, merge, squash, commit.",
    )
    hook_parser.add_argument(
        "sha",
        metavar="<sha>",
        nargs="?",
        default="",
        help="Commit SHA ($3 from git, only for --amend).",
    )
    hook_parser.set_defaults(func=_cmd_hook)

    # -- install -------------------------------------------------------------
    install_parser = subparsers.add_parser(
        "install",
        help="Install the prepare-commit-msg hook in the current repository.",
    )
    install_parser.set_defaults(func=_cmd_install)

    # -- uninstall -----------------------------------------------------------
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Remove the acmg hook from the current repository.",
    )
    uninstall_parser.set_defaults(func=_cmd_uninstall)

    # -- config --------------------------------------------------------------
    config_parser = subparsers.add_parser(
        "config",
        help="Manage acmg configuration.",
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", metavar="<config-command>"
    )

    config_set_parser = config_subparsers.add_parser(
        "set",
        help="Set a configuration key in the repository-level config file.",
    )
    config_set_parser.add_argument(
        "key",
        metavar="<key>",
        help="Configuration key (e.g. apiKey, model, maxTokens).",
    )
    config_set_parser.add_argument(
        "value",
        metavar="<value>",
        help="Value to set.",
    )
    config_set_parser.set_defaults(func=_cmd_config_set)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the acmg CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)
