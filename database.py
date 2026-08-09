"""Database compatibility for local SQLite and production PostgreSQL.

Vigzone keeps SQLite as a zero-setup local/test backend. When ``DATABASE_URL``
is configured, every call uses a small Psycopg connection pool instead. The
wrapper preserves the narrow DB-API surface used by the existing application
while translating SQLite ``?`` parameters and generated-id DDL to PostgreSQL.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any


logger = logging.getLogger("vigzone.database")

_POOL: Any = None
_POOL_URL = ""
_POOL_LOCK = threading.Lock()
_UNSET = object()


def configured_database_url() -> str:
    """Return the current server-side PostgreSQL URL without logging it."""

    return os.getenv("DATABASE_URL", "").strip()


def using_postgres() -> bool:
    return bool(configured_database_url())


def backend_name() -> str:
    return "postgresql" if using_postgres() else "sqlite"


class DatabaseRow(Mapping[str, Any]):
    """Row supporting both ``row['name']`` and legacy ``row[0]`` access."""

    __slots__ = ("_names", "_values", "_lookup")

    def __init__(self, names: Sequence[str], values: Sequence[Any]):
        self._names = tuple(names)
        self._values = tuple(values)
        self._lookup = dict(zip(self._names, self._values))

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._lookup[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def keys(self):
        return self._lookup.keys()


def _postgres_row_factory(cursor: Any):
    names = tuple(column.name for column in (cursor.description or ()))

    def make_row(values: Sequence[Any]) -> DatabaseRow:
        return DatabaseRow(names, values)

    return make_row


def _qmark_to_postgres(sql: str) -> str:
    """Translate DB-API qmarks while leaving quoted SQL text untouched."""

    output: list[str] = []
    quote = ""
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            output.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = ""
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif char == "?":
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def postgres_sql(sql: str) -> str:
    """Return the PostgreSQL equivalent of Vigzone's portable SQL subset."""

    statement = sql.strip()
    if statement.upper() == "BEGIN IMMEDIATE":
        return "BEGIN ISOLATION LEVEL SERIALIZABLE"
    converted = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "SERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    return _qmark_to_postgres(converted)


class DatabaseCursor:
    def __init__(self, connection: "DatabaseConnection", raw: Any):
        self._connection = connection
        self._raw = raw
        self._lastrowid: Any = _UNSET

    @property
    def rowcount(self) -> int:
        return int(self._raw.rowcount)

    @property
    def lastrowid(self) -> Any:
        if self._connection.backend == "sqlite":
            return self._raw.lastrowid
        if self._lastrowid is _UNSET:
            row = self._connection.execute("SELECT LASTVAL()").fetchone()
            self._lastrowid = row[0] if row else None
        return self._lastrowid

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()

    def __iter__(self):
        return iter(self._raw)

    def __getattr__(self, name: str):
        return getattr(self._raw, name)


class DatabaseConnection:
    def __init__(self, raw: Any, backend: str):
        self._raw = raw
        self.backend = backend

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> DatabaseCursor:
        statement = postgres_sql(sql) if self.backend == "postgresql" else sql
        params = tuple(parameters or ())
        raw_cursor = self._raw.execute(statement, params)
        return DatabaseCursor(self, raw_cursor)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def __getattr__(self, name: str):
        return getattr(self._raw, name)


def _postgres_pool():
    global _POOL, _POOL_URL

    url = configured_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    with _POOL_LOCK:
        if _POOL is not None and _POOL_URL == url:
            return _POOL
        if _POOL is not None:
            _POOL.close()
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL is configured but Psycopg is not installed. "
                "Install the production requirements before starting Vigzone."
            ) from exc
        minimum = max(0, int(os.getenv("DATABASE_POOL_MIN", "0")))
        maximum = max(1, min(int(os.getenv("DATABASE_POOL_MAX", "5")), 20))
        minimum = min(minimum, maximum)
        timeout = max(3.0, min(float(os.getenv("DATABASE_POOL_TIMEOUT", "15")), 60.0))
        _POOL = ConnectionPool(
            conninfo=url,
            min_size=minimum,
            max_size=maximum,
            timeout=timeout,
            max_idle=300.0,
            open=False,
            kwargs={
                "row_factory": _postgres_row_factory,
                "connect_timeout": min(int(timeout), 30),
                "application_name": "vigzone-ai",
                # Neon's pooled endpoint may operate in transaction-pooling
                # mode, where client-side prepared statement reuse is unsafe.
                "prepare_threshold": None,
            },
            check=ConnectionPool.check_connection,
            name="vigzone-postgres",
        )
        _POOL.open(wait=minimum > 0, timeout=timeout)
        _POOL_URL = url
        logger.info("PostgreSQL connection pool initialized")
        return _POOL


@contextmanager
def connect(sqlite_path: str):
    """Yield a transactional connection for the configured backend."""

    if using_postgres():
        pool = _postgres_pool()
        timeout = max(3.0, min(float(os.getenv("DATABASE_POOL_TIMEOUT", "15")), 60.0))
        with pool.connection(timeout=timeout) as raw:
            yield DatabaseConnection(raw, "postgresql")
        return

    os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)
    raw = sqlite3.connect(sqlite_path, timeout=15.0)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    raw.execute("PRAGMA busy_timeout = 15000")
    raw.execute("PRAGMA journal_mode = WAL")
    raw.execute("PRAGMA synchronous = NORMAL")
    try:
        yield DatabaseConnection(raw, "sqlite")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def table_columns(conn: DatabaseConnection, table: str) -> set[str]:
    safe_table = re.sub(r"[^A-Za-z0-9_]", "", table)
    if not safe_table or safe_table != table:
        raise ValueError("Invalid table name")
    if conn.backend == "postgresql":
        rows = conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = current_schema() AND table_name = ?""",
            (safe_table,),
        ).fetchall()
        return {str(row[0]) for row in rows}
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({safe_table})").fetchall()}


def close_pool() -> None:
    global _POOL, _POOL_URL
    with _POOL_LOCK:
        if _POOL is not None:
            _POOL.close()
        _POOL = None
        _POOL_URL = ""
