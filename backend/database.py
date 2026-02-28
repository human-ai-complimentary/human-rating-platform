from __future__ import annotations

from collections.abc import AsyncGenerator
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import Settings, get_settings


class Database:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        if self._engine is not None and self._session_maker is not None:
            return

        self._engine = create_async_engine(
            self._settings.async_database_url,
            pool_pre_ping=True,
        )
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    async def disconnect(self) -> None:
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._session_maker = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._session_maker is None:
            raise RuntimeError("Database is not initialized. Ensure app lifespan startup has run.")
        async with self._session_maker() as session:
            yield session


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    database: Database = request.app.state.database
    async with database.session() as session:
        yield session


def build_database(settings: Settings | None = None) -> Database:
    return Database(settings=settings or get_settings())
