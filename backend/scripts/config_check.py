from __future__ import annotations

import argparse
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import Settings, get_settings  # noqa: E402


@dataclass
class ValidationResult:
    """Holds the result of a configuration validation."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class ProviderValidator(ABC):
    """Base class for environment/provider-specific configuration checks.

    To add a new provider:
      1. Subclass ProviderValidator
      2. Set the `name` class var (this becomes the --target CLI value)
      3. Implement `validate()`
      4. Register it in `get_validators()`
    """

    name: ClassVar[str]

    @abstractmethod
    def validate(self, settings: Settings, result: ValidationResult) -> None:
        """Evaluate settings and append any warnings or errors to the result."""


class LocalValidator(ProviderValidator):
    """Validates local development configuration."""

    name = "local"

    def validate(self, settings: Settings, result: ValidationResult) -> None:
        # Local environments are generally permissive. Add specific checks here if needed.
        pass


class RenderValidator(ProviderValidator):
    """Validates configuration for Render deployments."""

    name = "render"

    def validate(self, settings: Settings, result: ValidationResult) -> None:
        # 1. Database connection check
        try:
            sync_url = settings.sync_database_url
            if "localhost" in sync_url or "@db:" in sync_url:
                result.add_error("DATABASE__URL points to a local host instead of a managed database.")
        except RuntimeError as exc:
            result.add_error(f"DATABASE__URL resolution failed: {exc}")

        # 2. CORS check
        if "*" in settings.app.cors_origins:
            result.add_warning("APP__CORS_ORIGINS includes '*' which is overly permissive for production.")


def get_validators() -> dict[str, ProviderValidator]:
    """Discover and return all available provider validators."""
    validators = [LocalValidator(), RenderValidator()]
    return {v.name: v for v in validators}


def _build_parser(available_targets: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate load-bearing backend configuration against specific deployment targets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--target",
        choices=available_targets,
        default="local",
        help="Validation profile (deployment provider).",
    )
    return parser


def main() -> int:
    registry = get_validators()
    parser = _build_parser(list(registry.keys()))
    args = parser.parse_args()

    validator = registry[args.target]
    result = ValidationResult()

    print(f"🔍 Validating configuration for target: '{validator.name}'...")

    try:
        settings = get_settings()
        validator.validate(settings, result)
    except Exception as exc:  # pragma: no cover
        result.add_error(f"Failed to parse settings: {exc}")

    # Output Results
    for warning in result.warnings:
        print(f"⚠️  WARN: {warning}")

    for error in result.errors:
        print(f"❌ ERROR: {error}", file=sys.stderr)

    if not result.is_valid:
        print(f"\n💥 Config check failed with {len(result.errors)} error(s).")
        return 1

    if result.warnings:
        print(f"\n✅ Config check passed cleanly, but with {len(result.warnings)} warning(s).")
    else:
        print("\n✅ Config check passed cleanly. You are good to go!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
