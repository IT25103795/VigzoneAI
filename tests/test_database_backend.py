"""Database compatibility tests for SQLite development and PostgreSQL production."""

from __future__ import annotations

from contextlib import contextmanager

import database


def test_postgres_sql_translates_parameters_and_generated_ids():
    sql = """CREATE TABLE example (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT DEFAULT '?',
        owner_id INTEGER
    )"""
    converted = database.postgres_sql(sql)
    assert "SERIAL PRIMARY KEY" in converted
    assert "AUTOINCREMENT" not in converted
    assert "DEFAULT '?'" in converted

    query = database.postgres_sql("SELECT * FROM example WHERE owner_id = ? AND label = '?'")
    assert query == "SELECT * FROM example WHERE owner_id = %s AND label = '?'"
    assert database.postgres_sql("BEGIN IMMEDIATE") == "BEGIN ISOLATION LEVEL SERIALIZABLE"


def test_quota_usage_provider_filter_is_psycopg_safe():
    """A literal percent beside bound params is parsed as a placeholder by Psycopg."""
    from psycopg.adapt import Transformer
    from psycopg._queries import PostgresQuery

    source = open("vigzone_ai.py", encoding="utf-8").read()
    assert "provider LIKE 'groq%'" not in source
    assert "provider IN ('groq', 'gemini', 'groq_audio', 'groq_interrupted')" in source

    sql = database.postgres_sql(
        """SELECT COALESCE(SUM(total_tokens), 0)
             FROM token_usage
            WHERE provider IN ('groq', 'gemini', 'groq_audio', 'groq_interrupted')
              AND ts >= ?"""
    )
    query = PostgresQuery(Transformer())
    query.convert(sql, ("2026-08-09T00:00:00+00:00",))
    assert query.query is not None


def test_database_row_supports_mapping_and_positional_access():
    row = database.DatabaseRow(("id", "name"), (7, "Vigzone"))
    assert row[0] == 7
    assert row["name"] == "Vigzone"
    assert dict(row) == {"id": 7, "name": "Vigzone"}


def test_sqlite_fallback_remains_transactional(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = str(tmp_path / "compat.db")
    with database.connect(path) as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT NOT NULL)")
        inserted = conn.execute("INSERT INTO sample(value) VALUES (?)", ("saved",))
        inserted_id = inserted.lastrowid

    with database.connect(path) as conn:
        row = conn.execute("SELECT id, value FROM sample WHERE id = ?", (inserted_id,)).fetchone()
    assert row[0] == inserted_id
    assert row["value"] == "saved"


def test_postgres_backend_selected_only_when_database_url_exists(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database.backend_name() == "sqlite"
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://vigzone:secret@db.example.com/vigzone?sslmode=require",
    )
    assert database.backend_name() == "postgresql"


def test_application_sql_has_no_unhandled_sqlite_write_syntax():
    for path in ("auth.py", "billing.py", "app.py", "vigzone_ai.py"):
        source = open(path, encoding="utf-8").read()
        assert "INSERT OR IGNORE" not in source
        if path not in {"auth.py", "database.py"}:
            assert "import sqlite3" not in source
        assert "strftime('%s','now')" not in source


def test_full_schema_initialization_translates_to_postgres(monkeypatch):
    import auth

    class FakeCursor:
        rowcount = 0

        def __init__(self, one=None, many=None):
            self._one = one
            self._many = many or []

        def fetchone(self):
            return self._one

        def fetchall(self):
            return self._many

    class FakePostgresConnection:
        backend = "postgresql"

        def __init__(self):
            self.statements = []

        def execute(self, sql, parameters=None):
            converted = database.postgres_sql(sql)
            self.statements.append(converted)
            if "information_schema.columns" in converted:
                return FakeCursor(many=[])
            if converted.lstrip().upper().startswith("SELECT"):
                return FakeCursor(one=None, many=[])
            return FakeCursor()

    fake = FakePostgresConnection()

    @contextmanager
    def fake_connect():
        yield fake

    monkeypatch.setattr(auth, "_connect", fake_connect)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_PASSWORD", raising=False)
    auth.init_db()

    schema_sql = "\n".join(fake.statements)
    assert "SERIAL PRIMARY KEY" in schema_sql
    assert "AUTOINCREMENT" not in schema_sql
    assert "PRAGMA" not in schema_sql
    assert "INSERT OR IGNORE" not in schema_sql
