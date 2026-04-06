from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _ensure_async_url(url: str) -> str:
    """Convert postgresql:// to postgresql+asyncpg:// and strip Supabase-specific params."""
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    # Strip params that asyncpg doesn't understand (Supabase adds ?pgbouncer=true)
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Remove non-asyncpg params
    for key in ("pgbouncer", "sslmode", "supa"):
        params.pop(key, None)
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


# Pooled connection (port 6543) for API requests — fast, PgBouncer managed
engine = create_async_engine(
    _ensure_async_url(settings.database_url),
    echo=settings.is_dev,
    pool_size=5,
    max_overflow=10,
    # Supabase uses PgBouncer in transaction mode — disable prepared statement cache
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)

# Direct connection (port 5432) for long-running operations like sync and migrations
_direct_url = settings.direct_database_url or settings.database_url
direct_engine = create_async_engine(
    _ensure_async_url(_direct_url),
    echo=settings.is_dev,
    pool_size=2,
    max_overflow=3,
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
direct_session_factory = async_sessionmaker(direct_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
