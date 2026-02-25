from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, AliasPath, Field, field_validator
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


class Settings(BaseSettings):
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", AliasPath("app", "env")),
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        validation_alias=AliasChoices(
            "CORS_ORIGINS",
            AliasPath("app", "cors_origins"),
        ),
    )
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/human_rating_platform",
        validation_alias=AliasChoices("DATABASE_URL", AliasPath("database", "url")),
    )

    migration_script_location: str = Field(
        default="backend/alembic",
        validation_alias=AliasChoices(
            "MIGRATION_SCRIPT_LOCATION",
            AliasPath("migrations", "script_location"),
        ),
    )
    migration_version_locations: str = Field(
        default="backend/alembic/versions",
        validation_alias=AliasChoices(
            "MIGRATION_VERSION_LOCATIONS",
            AliasPath("migrations", "version_locations"),
        ),
    )
    export_stream_batch_size: int = Field(
        default=1000,
        ge=1,
        validation_alias=AliasChoices(
            "EXPORT_STREAM_BATCH_SIZE",
            AliasPath("exports", "stream_batch_size"),
        ),
    )
    test_export_seed_row_count: int = Field(
        default=1500,
        ge=1,
        validation_alias=AliasChoices(
            "TEST_EXPORT_SEED_ROW_COUNT",
            AliasPath("testing", "export_seed_row_count"),
        ),
    )
    dev_seed_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "DEV_SEED_ENABLED",
            AliasPath("seeding", "enabled"),
        ),
    )
    dev_seed_experiment_name: str = Field(
        default="Seed - Local Baseline",
        validation_alias=AliasChoices(
            "DEV_SEED_EXPERIMENT_NAME",
            AliasPath("seeding", "experiment_name"),
        ),
    )
    dev_seed_question_count: int = Field(
        default=50,
        ge=1,
        validation_alias=AliasChoices(
            "DEV_SEED_QUESTION_COUNT",
            AliasPath("seeding", "question_count"),
        ),
    )
    dev_seed_num_ratings_per_question: int = Field(
        default=3,
        ge=1,
        validation_alias=AliasChoices(
            "DEV_SEED_NUM_RATINGS_PER_QUESTION",
            AliasPath("seeding", "num_ratings_per_question"),
        ),
    )
    dev_seed_completion_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "DEV_SEED_COMPLETION_URL",
            AliasPath("seeding", "prolific_completion_url"),
        ),
    )

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
        # Highest priority first.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
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
        raise TypeError("CORS_ORIGINS must be a comma-separated string or list")

    @property
    def sync_database_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            return url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL")

    @property
    def async_database_url(self) -> str:
        sync_url = self.sync_database_url
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
