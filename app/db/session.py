from typing import Generator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import settings


def get_async_db_url():
    conn = settings.DATABASE_URL
    if conn and conn.startswith("postgres://"):
        conn = conn.replace("postgres://", "postgresql+asyncpg://", 1)
    elif conn and conn.startswith("postgresql://"):
        conn = conn.replace("postgresql://", "postgresql+asyncpg://", 1)
    return conn


async_engine = create_async_engine(
    get_async_db_url(),
    future=True,
    pool_pre_ping=True,
    connect_args={"server_settings": {"timezone": "utc"}},
    poolclass=NullPool,
)

async_maker = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


def get_session() -> AsyncSession:
    return async_maker()
