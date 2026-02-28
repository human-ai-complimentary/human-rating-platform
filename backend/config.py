"""Central backend configuration surface.

Design goals for contributors:
1. Keep config contract explicit and small.
2. Prefer nested keys for both TOML and env overrides.
3. Keep overrides ergonomic in real deployments (ignore unrelated env keys).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

BASE_DIR = Path(__file__).resolve().parent


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AppSettings(_StrictModel):
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"],
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        err = (
            "APP__CORS_ORIGINS must be a JSON array of strings, "
            "for example '[\"https://app.example.com\"]'."
        )
        if value is None:
            return ["*"]

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(err) from exc

        if not isinstance(value, list):
            raise ValueError(err)

        if any(not isinstance(item, str) for item in value):
            raise ValueError(err)

        return [item.strip() for item in value if item.strip()]


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
        raise RuntimeError("DATABASE__URL must start with postgresql:// or postgresql+asyncpg://")

    @property
    def async_database_url(self) -> str:
        return self.sync_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
