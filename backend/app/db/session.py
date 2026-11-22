"""Session SQLAlchemy 2.0 asynchrone."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base déclarative commune."""


_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")


def _make_engine(url: str):
    is_sqlite = url.startswith("sqlite")
    eng = create_async_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args={"timeout": 30} if is_sqlite else {},
    )
    if is_sqlite:
        from sqlalchemy import event

        @event.listens_for(eng.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return eng


engine = _make_engine(settings.DATABASE_URL)
SessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Crée le schéma (prod : alembic upgrade head)."""
    global engine, SessionLocal, _IS_SQLITE
    import logging
    from app import models  # noqa: F401  (enregistrement des mappers)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_legacy_schema)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        if not _IS_SQLITE:
            logging.getLogger(__name__).warning(
                "PostgreSQL indisponible (%s). Basculement automatique sur base SQLite locale (diafoot.db).",
                exc,
            )
            fallback_url = "sqlite+aiosqlite:///diafoot.db"
            _IS_SQLITE = True
            engine = _make_engine(fallback_url)
            SessionLocal = async_sessionmaker(
                bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
            )
            async with engine.begin() as conn:
                await conn.run_sync(_migrate_legacy_schema)
                await conn.run_sync(Base.metadata.create_all)
        else:
            raise


def _migrate_legacy_schema(connection) -> None:
    """Conserve les anciennes tables incompatibles sous leur nom et crée le schéma courant."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    expected_tables = Base.metadata.tables

    legacy_chat = False
    chat_table = expected_tables["chat_messages"]
    if "chat_messages" in tables:
        actual = {column["name"] for column in inspector.get_columns("chat_messages")}
        expected = set(chat_table.columns.keys())
        if actual != expected:
            if "legacy_chat_messages" in tables:
                raise RuntimeError(
                    "Les deux schémas de chat sont présents; "
                    "migration manuelle requise pour éviter une perte de données."
                )
            legacy_chat = True

    legacy_tables = []
    for name in ("wounds", "wound_analyses"):
        if name not in tables:
            continue
        actual = {column["name"] for column in inspector.get_columns(name)}
        expected = set(expected_tables[name].columns.keys())
        if actual == expected:
            continue
        legacy_name = f"legacy_{name}"
        if legacy_name in tables:
            raise RuntimeError(
                f"Les tables {name} et {legacy_name} utilisent des schémas différents; "
                "migration manuelle requise pour éviter une perte de données."
            )
        legacy_tables.append((name, legacy_name))

    sequence_renames = []
    if connection.dialect.name == "postgresql":
        sequences = set(inspector.get_sequence_names())
        renamed_tables = list(legacy_tables)
        if legacy_chat:
            renamed_tables.append(("chat_messages", "legacy_chat_messages"))
        for name, legacy_name in renamed_tables:
            sequence = f"{name}_id_seq"
            legacy_sequence = f"{legacy_name}_id_seq"
            if sequence in sequences:
                if legacy_sequence in sequences:
                    raise RuntimeError(
                        f"La séquence {legacy_sequence} existe déjà; "
                        "migration manuelle requise pour éviter une perte de données."
                    )
                sequence_renames.append((sequence, legacy_sequence))

    for sequence, legacy_sequence in sequence_renames:
        old_quoted = connection.dialect.identifier_preparer.quote(sequence)
        legacy_quoted = connection.dialect.identifier_preparer.quote(legacy_sequence)
        connection.execute(
            text(f"ALTER SEQUENCE {old_quoted} RENAME TO {legacy_quoted}")
        )

    if legacy_chat:
        connection.execute(text(
            "ALTER TABLE chat_messages RENAME TO legacy_chat_messages"
        ))

    for name, legacy_name in legacy_tables:
        old_quoted = connection.dialect.identifier_preparer.quote(name)
        legacy_quoted = connection.dialect.identifier_preparer.quote(legacy_name)
        connection.execute(text(f"ALTER TABLE {old_quoted} RENAME TO {legacy_quoted}"))
