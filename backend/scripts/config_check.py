"""Validate load-bearing backend configuration before deployment.

Extension guide
───────────────
  New provider?  Subclass ``ProviderValidator`` — it auto-registers.
  New check?     Add a ``check_*`` method to the validator — it auto-runs.

Example:

    class RailwayValidator(ProviderValidator):
        name = "railway"

        def check_database_is_remote(self, s: Settings, r: ValidationResult) -> None:
            ...

        def check_redis_configured(self, s: Settings, r: ValidationResult) -> None:
            ...

That's it. ``--target railway`` appears in the CLI automatically.
"""

from __future__ import annotations

import argparse
import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import Settings, get_settings  # noqa: E402

# ── Result container ──────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Accumulates errors and warnings from one validation run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ── mutators ──────────────────────────────────────────────────────────
    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    # ── queries ───────────────────────────────────────────────────────────
    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def __bool__(self) -> bool:
        return self.ok


# ── Validator base + auto-registration ────────────────────────────────────────

_REGISTRY: dict[str, type] = {}  # populated by ProviderValidator.__init_subclass__


class ProviderValidator(ABC):
    """Base class for provider-specific configuration checks.

    Subclasses **must** set ``name`` and implement at least one ``check_*``
    method.  All public ``check_*`` methods are discovered and called
    automatically — no manual wiring required.
    """

    name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        if not hasattr(cls, "name") or not isinstance(cls.name, str):
            raise TypeError(f"{cls.__name__} must define a `name: ClassVar[str]`")
        if cls.name in _REGISTRY:
            raise ValueError(f"Duplicate validator name: {cls.name!r}")
        _REGISTRY[cls.name] = cls

    def validate(self, settings: Settings, result: ValidationResult) -> None:
        """Run every ``check_*`` method on *settings*, collecting into *result*."""
        for attr in sorted(dir(self)):
            if attr.startswith("check_") and callable(getattr(self, attr)):
                getattr(self, attr)(settings, result)

    @abstractmethod
    def _abstract_guard(self) -> None:
        """Forces subclasses to be concrete (at least one override required)."""


# ── Concrete validators ──────────────────────────────────────────────────────


class LocalValidator(ProviderValidator):
    """Local development — intentionally permissive."""

    name = "local"

    def _abstract_guard(self) -> None: ...


class RenderValidator(ProviderValidator):
    """Render deployment checks."""

    name = "render"

    def _abstract_guard(self) -> None: ...

    def check_database_is_remote(self, settings: Settings, result: ValidationResult) -> None:
        try:
            url = settings.sync_database_url
        except RuntimeError as exc:
            result.add_error(f"DATABASE__URL resolution failed: {exc}")
            return
        if "localhost" in url or "@db:" in url:
            result.add_error("DATABASE__URL points to a local host instead of a managed database.")

    def check_cors_not_wildcard(self, settings: Settings, result: ValidationResult) -> None:
        if "*" in settings.app.cors_origins:
            result.add_warning(
                "APP__CORS_ORIGINS includes '*' — overly permissive for production."
            )


# ── CLI ───────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target",
        choices=sorted(_REGISTRY),
        default="local",
        help="Validation profile (deployment provider).",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    validator = _REGISTRY[args.target]()
    result = ValidationResult()

    print(f"🔍 config check  target={validator.name}")

    try:
        settings = get_settings()
        validator.validate(settings, result)
    except Exception as exc:  # pragma: no cover
        result.add_error(f"Failed to parse settings: {exc}")

    for w in result.warnings:
        print(f"⚠️  WARN: {w}")
    for e in result.errors:
        print(f"❌ ERROR: {e}", file=sys.stderr)

    if not result:
        print(f"\n💥 Config check failed — {len(result.errors)} error(s).")
        return 1

    suffix = f" ({len(result.warnings)} warning(s))" if result.warnings else ""
    print(f"\n✅ Config check passed.{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
