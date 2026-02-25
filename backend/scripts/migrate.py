from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _build_alembic_config() -> Config:
    settings = get_settings()

    config = Config()
    config.set_main_option(
        "script_location",
        str(_resolve_path(settings.migration_script_location)),
    )
    config.set_main_option(
        "version_locations",
        str(_resolve_path(settings.migration_version_locations)),
    )
    config.set_main_option("sqlalchemy.url", settings.sync_database_url)

    # Avoid default logger config that expects alembic.ini sections.
    config.attributes["configure_logger"] = False
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Alembic migrations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_upgrade = subparsers.add_parser("upgrade", help="Upgrade to a revision")
    parser_upgrade.add_argument("revision", nargs="?", default="head")

    parser_stamp = subparsers.add_parser("stamp", help="Stamp revision without running")
    parser_stamp.add_argument("revision", nargs="?", default="head")

    parser_revision = subparsers.add_parser("revision", help="Create a new revision")
    parser_revision.add_argument("-m", "--message", required=True)
    parser_revision.add_argument("--autogenerate", action="store_true")

    subparsers.add_parser("current", help="Show current revision")
    subparsers.add_parser("history", help="Show revision history")

    args = parser.parse_args()
    config = _build_alembic_config()

    # Keep migration behavior explicit: we do not auto-stamp or infer schema state.
    # Every environment advances only through concrete Alembic commands.
    if args.command == "upgrade":
        command.upgrade(config, args.revision)
    elif args.command == "stamp":
        command.stamp(config, args.revision)
    elif args.command == "revision":
        command.revision(
            config,
            message=args.message,
            autogenerate=args.autogenerate,
        )
    elif args.command == "current":
        command.current(config)
    elif args.command == "history":
        command.history(config)
    else:
        parser.error(f"Unsupported command: {args.command}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
