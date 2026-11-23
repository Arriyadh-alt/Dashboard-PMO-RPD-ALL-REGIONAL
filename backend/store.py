"""Append-only operational history, separate from immutable imported customer records."""

import json
import sqlite3
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL,
                    ref TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS event_ref ON events(kind, ref, id);
                CREATE TRIGGER IF NOT EXISTS event_no_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT, 'Append-only history'); END;
                CREATE TRIGGER IF NOT EXISTS event_no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'Append-only history'); END;
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def append(self, kind, ref, actor, payload):
        with self.connect() as db:
            cur = db.execute("INSERT INTO events(kind,ref,actor,at,payload) VALUES(?,?,?,?,?)",
                             (kind, ref, actor, now_iso(), json.dumps(payload, ensure_ascii=False)))
            return cur.lastrowid

    def history(self, kind=None, ref=None, limit=100, before=None):
        clauses, params = [], []
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        if ref is not None:
            clauses.append("ref=?")
            params.append(ref)
        if before is not None:
            clauses.append("id<?")
            params.append(before)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events" + where + " ORDER BY id DESC LIMIT ?", (*params, limit)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def append_if_current(self, kind, ref, actor, payload, expected):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT MAX(id) AS id FROM events WHERE kind=? AND ref=?',(kind,ref)).fetchone()
            if (row['id'] or 0)!=expected:
                raise ValueError('State changed since it was loaded')
            cursor=db.execute('INSERT INTO events(kind,ref,actor,at,payload) VALUES(?,?,?,?,?)',
                              (kind,ref,actor,now_iso(),json.dumps(payload,ensure_ascii=False)))
            return cursor.lastrowid

    def latest(self, kind):
        with self.connect() as db:
            rows = db.execute("""SELECT e.* FROM events e JOIN
                (SELECT ref,MAX(id) id FROM events WHERE kind=? GROUP BY ref) last
                ON e.id=last.id""", (kind,)).fetchall()
        return {row["ref"]: json.loads(row["payload"]) for row in rows}
