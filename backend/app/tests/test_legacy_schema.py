from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db.session import Base, _migrate_legacy_schema


def _create_legacy_schema(connection) -> None:
    connection.execute(text(
        "CREATE TABLE wounds (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, name TEXT)"
    ))
    connection.execute(text(
        "CREATE TABLE wound_analyses (id INTEGER PRIMARY KEY, image_id INTEGER NOT NULL)"
    ))
    connection.execute(text(
        "CREATE TABLE chat_sessions (id TEXT PRIMARY KEY)"
    ))
    connection.execute(text(
        "CREATE TABLE chat_messages ("
        "id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at TIMESTAMP)"
    ))
    connection.execute(text(
        "INSERT INTO chat_sessions (id) VALUES ('old-session')"
    ))
    connection.execute(text(
        "INSERT INTO chat_messages (id, session_id, role, content) "
        "VALUES (1, 'old-session', 'user', 'message conservé')"
    ))


def test_migrates_legacy_tables_and_preserves_existing_rows():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            _create_legacy_schema(connection)
            connection.execute(text(
                "INSERT INTO wounds (id, patient_id, name) VALUES (7, 1, 'ancienne plaie')"
            ))
            connection.execute(text(
                "INSERT INTO wound_analyses (id, image_id) VALUES (9, 2)"
            ))
            _migrate_legacy_schema(connection)
            Base.metadata.create_all(connection)

            inspector = inspect(connection)
            assert "legacy_chat_messages" in inspector.get_table_names()
            assert "legacy_wounds" in inspector.get_table_names()
            assert "legacy_wound_analyses" in inspector.get_table_names()
            assert set(Base.metadata.tables["wounds"].columns.keys()) <= {
                column["name"] for column in inspector.get_columns("wounds")
            }
            assert set(Base.metadata.tables["wound_analyses"].columns.keys()) <= {
                column["name"]
                for column in inspector.get_columns("wound_analyses")
            }
            assert connection.execute(
                text("SELECT content FROM legacy_chat_messages WHERE id = 1")
            ).scalar_one() == "message conservé"
            assert connection.execute(
                text("SELECT name FROM legacy_wounds WHERE id = 7")
            ).scalar_one() == "ancienne plaie"
            assert connection.execute(
                text("SELECT image_id FROM legacy_wound_analyses WHERE id = 9")
            ).scalar_one() == 2
    finally:
        engine.dispose()


def test_refuses_to_overwrite_an_existing_legacy_table():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            _create_legacy_schema(connection)
            connection.execute(text("CREATE TABLE legacy_wounds (id INTEGER PRIMARY KEY)"))

        with pytest.raises(RuntimeError, match="migration manuelle requise"):
            with engine.begin() as connection:
                _migrate_legacy_schema(connection)

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT COUNT(*) FROM chat_messages")
            ).scalar_one() == 1
    finally:
        engine.dispose()
