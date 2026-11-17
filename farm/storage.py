"""SQLite-backed flag queue.

A flag is stored once (UNIQUE on value). Statuses:
    QUEUED    - waiting to be submitted
    ACCEPTED  - gameserver gave us points
    REJECTED  - permanently dead (duplicate/own/invalid/expired)
    SKIPPED   - dropped locally before submit (too old / nop)

The queue is safe to share between the runner and submitter processes/threads
because every connection opens with WAL mode and a busy timeout.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterable, Iterator

QUEUED, ACCEPTED, REJECTED, SKIPPED = "QUEUED", "ACCEPTED", "REJECTED", "SKIPPED"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flags (
    flag        TEXT PRIMARY KEY,
    target      TEXT,
    exploit     TEXT,
    status      TEXT NOT NULL DEFAULT 'QUEUED',
    response    TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flags_status ON flags(status, created_at);
"""


class Storage:
    def __init__(self, path: str):
        self.path = path
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_flags(self, flags: Iterable[tuple[str, str, str]]) -> int:
        """flags: iterable of (flag, target, exploit). Returns #newly inserted."""
        now = time.time()
        rows = [(f, t, e, QUEUED, now, now) for (f, t, e) in flags]
        if not rows:
            return 0
        with self._conn() as c:
            before = c.total_changes
            c.executemany(
                "INSERT OR IGNORE INTO flags"
                "(flag,target,exploit,status,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?)",
                rows,
            )
            return c.total_changes - before

    def take_queued(self, limit: int, max_age: float | None = None) -> list[str]:
        """Return up to `limit` queued flags, skipping ones older than max_age.
        Flags that are too old are marked SKIPPED as a side effect."""
        now = time.time()
        with self._conn() as c:
            if max_age is not None:
                cutoff = now - max_age
                c.execute(
                    "UPDATE flags SET status=?, response='expired', updated_at=?"
                    " WHERE status=? AND created_at < ?",
                    (SKIPPED, now, QUEUED, cutoff),
                )
            rows = c.execute(
                "SELECT flag FROM flags WHERE status=? ORDER BY created_at LIMIT ?",
                (QUEUED, limit),
            ).fetchall()
        return [r[0] for r in rows]

    def mark(self, results: Iterable[tuple[str, str, str]]) -> None:
        """results: iterable of (flag, new_status, response)."""
        now = time.time()
        rows = [(st, resp, now, fl) for (fl, st, resp) in results]
        with self._conn() as c:
            c.executemany(
                "UPDATE flags SET status=?, response=?, updated_at=? WHERE flag=?",
                rows,
            )

    def requeue_stale(self, older_than: float = 120) -> int:
        """(Reserved) nothing stays 'in flight' in this design; kept for symmetry."""
        return 0

    def stats(self) -> dict[str, int]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT status, COUNT(*) FROM flags GROUP BY status"
            ).fetchall()
        return {status: n for status, n in rows}
