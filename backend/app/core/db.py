import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Supabase's transaction-mode pooler (port 6543) and other pgBouncer setups
# multiplex many clients onto few server connections, so server-side prepared
# statements cached by asyncpg/SQLAlchemy leak across sessions and error out.
# When talking to the pooler we therefore disable both statement caches and
# give each prepared statement a unique name. Auto-detected from the 6543 port
# used by Supabase, or forced via DB_PGBOUNCER=true.
_use_pgbouncer = settings.db_pgbouncer or ":6543" in settings.database_url

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if _use_pgbouncer:
    _engine_kwargs["connect_args"] = {
        # asyncpg's own prepared-statement cache.
        "statement_cache_size": 0,
        # SQLAlchemy asyncpg dialect's cache (popped by the dialect, not sent
        # to asyncpg).
        "prepared_statement_cache_size": 0,
        # Unique names avoid "prepared statement already exists" when a pooled
        # server connection is reused by a different client.
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
    }
    # Lambda freezes between invocations; don't hold a pool of connections that
    # the pooler may have already closed. Open per-request instead.
    _engine_kwargs["poolclass"] = NullPool

# Note: the pgvector SQLAlchemy ``Vector`` type serializes embeddings to/from the
# textual vector format itself, so we intentionally do NOT register the asyncpg
# vector codec here (doing so would double-encode and fail on inserts).
engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
