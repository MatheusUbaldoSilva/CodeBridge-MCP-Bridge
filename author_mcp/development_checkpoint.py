"""Bounded, durable checkpoints for a CodeBridge development turn."""
from contextlib import closing
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SESSION_ID = re.compile(r"^codebridge_[a-f0-9]{32}$")
STAGES = {"RUNNING", "PREPARE_WRAP_UP", "WRAP_UP_NOW", "FINISHED"}


class DevelopmentCheckpoints:
    def __init__(self, path=None):
        self.path = Path(path) if path else (
            Path(os.environ.get("LOCALAPPDATA") or Path.home())
            / "CodeBridge-MCP-Bridge" / "development_checkpoints.sqlite3")

    @staticmethod
    def _text(value, label, maximum=1200):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError("invalid " + label)
        return value.strip()

    @classmethod
    def _items(cls, items, label):
        if not isinstance(items, list) or len(items) > 20:
            raise ValueError("invalid " + label)
        return [cls._text(item, label, 500) for item in items]

    def save(self, session_id, summary, next_step, completed=None,
             pending=None, stage="RUNNING"):
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise ValueError("invalid session id")
        if stage not in STAGES:
            raise ValueError("invalid stage")
        data = dict(session_id=session_id, summary=self._text(summary, "summary"),
                    next_step=self._text(next_step, "next_step"),
                    completed=self._items(completed if completed is not None else [], "completed"),
                    pending=self._items(pending if pending is not None else [], "pending"),
                    stage=stage)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.path, timeout=15, isolation_level=None)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS checkpoints "
                       "(session_id TEXT PRIMARY KEY, updated_at TEXT, "
                       "revision INTEGER, payload TEXT)")
            db.execute("INSERT INTO checkpoints VALUES(?,?,1,?) "
                       "ON CONFLICT(session_id) DO UPDATE SET "
                       "updated_at=excluded.updated_at,revision=revision+1,payload=excluded.payload",
                       (session_id, stamp, json.dumps(data, ensure_ascii=False)))
            revision = db.execute("SELECT revision FROM checkpoints WHERE session_id=?",
                                  (session_id,)).fetchone()[0]
        return dict(data, updated_at=stamp, revision=revision)
    def latest(self, session_id=None):
        if session_id is not None and (
                not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id)):
            raise ValueError("invalid session id")
        if not self.path.is_file():
            return None
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            if session_id is not None:
                row = db.execute("SELECT payload,updated_at,revision FROM checkpoints "
                                 "WHERE session_id=?", (session_id,)).fetchone()
            else:
                row = db.execute("SELECT payload,updated_at,revision FROM checkpoints "
                                 "ORDER BY updated_at DESC,rowid DESC LIMIT 1").fetchone()
        return dict(json.loads(row[0]), updated_at=row[1], revision=row[2]) if row else None
