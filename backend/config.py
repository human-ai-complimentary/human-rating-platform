"""Central backend configuration surface.

Design goals for contributors:
1. Keep config contract explicit and small.
2. Prefer nested keys for both TOML and env overrides.
3. Keep overrides ergonomic in real deployments (ignore unrelated env keys).
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

BASE_DIR = Path(__file__).resolve().parent

LEGACY_ENV_KEY_REPLACEMENTS: dict[str, str] = {
    "APP_ENV": "<removed>",
    "CORS_ORIGINS": "APP__CORS_ORIGINS",
    "DATABASE_URL": "DATABASE__URL",
    "EXPORT_STREAM_BATCH_SIZE": "EXPORTS__STREAM_BATCH_SIZE",
    "TEST_EXPORT_SEED_ROW_COUNT": "TESTING__EXPORT_SEED_ROW_COUNT",
    "DEV_SEED_ENABLED": "SEEDING__ENABLED",
    "DEV_SEED_EXPERIMENT_NAME": "SEEDING__EXPERIMENT_NAME",
    "DEV_SEED_QUESTION_COUNT": "SEEDING__QUESTION_COUNT",
    "DEV_SEED_NUM_RATINGS_PER_QUESTION": "SEEDING__NUM_RATINGS_PER_QUESTION",
    "DEV_SEED_COMPLETION_URL": "SEEDING__PROLIFIC_COMPLETION_URL",
    "MIGRATION_SCRIPT_LOCATION": "<removed>",
    "MIGRATION_VERSION_LOCATIONS": "<removed>",
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AppSettings(_StrictModel):
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if value is None:
            return ["*"]
        if isinstance(value, str):
            values = [item.strip() for item in value.split(",")]
            return [item for item in values if item]
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        raise TypeError("APP__CORS_ORIGINS must be a comma-separated string or list")


class DatabaseSettings(_StrictModel):
    url: str = "postgresql://postgres:postgres@localhost:5432/human_rating_platform"


class ExportSettings(_StrictModel):
    stream_batch_size: int = Field(
        default=1000,
        ge=1,
    )


class TestingSettings(_StrictModel):
    export_seed_row_count: int = Field(
        default=1500,
        ge=1,
    )


class SeedingSettings(_StrictModel):
    enabled: bool = False
    experiment_name: str = "Seed - Local Baseline"
    question_count: int = Field(default=50, ge=1)
    num_ratings_per_question: int = Field(default=3, ge=1)
    prolific_completion_url: str | None = None


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    exports: ExportSettings = Field(default_factory=ExportSettings)
    testing: TestingSettings = Field(default_factory=TestingSettings)
    seeding: SeedingSettings = Field(default_factory=SeedingSettings)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        toml_file=BASE_DIR / "config.toml",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: EnvSettingsSource,
        dotenv_settings: DotEnvSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Highest priority first:
        # constructor kwargs > process env > .env > config.toml > file secrets.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    @property
    def sync_database_url(self) -> str:
        url = self.database.url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return f"postgresql://{url.removeprefix('postgresql+asyncpg://')}"
        if url.startswith("postgresql://"):
            return url
        if url.startswith("postgres://"):
            return f"postgresql://{url.removeprefix('postgres://')}"
        raise RuntimeError(
            "DATABASE__URL must start with postgresql://, postgresql+asyncpg://, or postgres://"
        )

    @property
    def async_database_url(self) -> str:
        return self.sync_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _iter_env_file_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()

    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def _build_legacy_keys_error(found: set[str]) -> str:
    lines = [
        "Unsupported legacy config keys detected. This project only supports nested settings keys.",
    ]
    for key in sorted(found):
        replacement = LEGACY_ENV_KEY_REPLACEMENTS.get(key, "<removed>")
        if replacement == "<removed>":
            lines.append(f"- {key} (remove; no replacement)")
        else:
            lines.append(f"- {key} -> {replacement}")
    return "\n".join(lines)


def _assert_no_legacy_env_keys() -> None:
    legacy_keys = set(LEGACY_ENV_KEY_REPLACEMENTS.keys())
    process_keys = set(os.environ.keys())
    dotenv_keys = _iter_env_file_keys(BASE_DIR / ".env")
    found = (process_keys | dotenv_keys).intersection(legacy_keys)
    if found:
        raise RuntimeError(_build_legacy_keys_error(found))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _assert_no_legacy_env_keys()
    return Settings()
