from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate load-bearing backend configuration.",
    )
    parser.add_argument(
        "--target",
        choices=["local", "render"],
        default="local",
        help="Validation profile.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    warnings: list[str] = []
    errors: list[str] = []

    try:
        settings = get_settings()
    except Exception as exc:  # pragma: no cover - settings parsing exceptions vary.
        print(f"ERROR: Failed to load settings: {exc}")
        return 1

    try:
        sync_url = settings.sync_database_url
    except RuntimeError as exc:
        errors.append(str(exc))
    else:
        if args.target == "render":
            if "localhost" in sync_url or "@db:" in sync_url:
                errors.append("Render target check failed: DATABASE__URL points to a local host.")
            if "*" in settings.app.cors_origins:
                warnings.append("Render target warning: APP__CORS_ORIGINS includes '*'.")

    for warning in warnings:
        print(f"WARN: {warning}")

    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print("Config check failed.")
        return 1

    if warnings:
        print("Config check passed with warnings.")
    else:
        print("Config check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
