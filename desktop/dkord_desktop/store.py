from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .models import Track

SCHEMA = 1


class Store:
    """Stable per-user SQLite/WAL storage. Never replaces a corrupt/unknown database with an empty one."""
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if __import__("os").name != "nt":
            self.root.chmod(0o700)
        self.path = self.root / "library.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA:
                raise ValueError("This library needs a newer Dkord version. Existing data was not changed.")
            if version == 0:
                # A nonempty unknown database is not an empty first-run library.
                if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                    raise ValueError("Unknown library schema; recovery is required, not a reset")
                db.executescript("""
                    CREATE TABLE tracks(id TEXT PRIMARY KEY NOT NULL, data TEXT NOT NULL);
                    CREATE TABLE likes(id TEXT PRIMARY KEY REFERENCES tracks(id), added INTEGER NOT NULL);
                    CREATE TABLE history(id TEXT PRIMARY KEY REFERENCES tracks(id), played INTEGER NOT NULL, position INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE playlists(id TEXT PRIMARY KEY, name TEXT NOT NULL, data TEXT NOT NULL);
                    CREATE TABLE downloads(id TEXT PRIMARY KEY REFERENCES tracks(id), state TEXT NOT NULL, path TEXT,
                        destination TEXT NOT NULL, folder TEXT, device_path TEXT, bytes INTEGER NOT NULL DEFAULT 0,
                        total INTEGER NOT NULL DEFAULT 0, error TEXT, created INTEGER NOT NULL);
                    CREATE TABLE settings(key TEXT PRIMARY KEY, data TEXT NOT NULL);
                    CREATE TABLE queries(query TEXT NOT NULL, scope TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0,
                        used INTEGER NOT NULL, PRIMARY KEY(query,scope));
                    CREATE TABLE projects(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                    CREATE TABLE renders(id TEXT PRIMARY KEY, data TEXT NOT NULL, state TEXT NOT NULL, error TEXT);
                    PRAGMA user_version=1;
                """)
            db.execute("UPDATE downloads SET state='QUEUED' WHERE state='RUNNING'")
            db.execute("UPDATE renders SET state='INTERRUPTED' WHERE state='RUNNING'")

    @contextmanager
    def connect(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            try:
                with db:
                    yield db
            finally:
                db.close()

    def put_track(self, track: Track) -> None:
        track.validate()
        with self.connect() as db:
            db.execute("INSERT INTO tracks VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (track.id, json.dumps(track.json(), ensure_ascii=False)))

    def track(self, id: str) -> Track | None:
        with self.connect() as db:
            row = db.execute("SELECT data FROM tracks WHERE id=?", (id,)).fetchone()
            return Track.parse(json.loads(row[0])) if row else None

    def setting(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute("SELECT data FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data", (key, json.dumps(value, ensure_ascii=False)))

    def like(self, track: Track, liked: bool) -> None:
        self.put_track(track)
        with self.connect() as db:
            if liked:
                db.execute("INSERT OR REPLACE INTO likes VALUES (?,?)", (track.id, time.time_ns()))
            else:
                db.execute("DELETE FROM likes WHERE id=?", (track.id,))

    def history(self, track: Track, position: int = 0) -> None:
        self.put_track(track)
        with self.connect() as db:
            db.execute("INSERT INTO history VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET played=excluded.played,position=excluded.position", (track.id, time.time_ns(), max(0, position)))

    def library(self, category: str) -> list[Track]:
        queries = {
            "liked": "SELECT t.data FROM tracks t JOIN likes l ON t.id=l.id ORDER BY l.added DESC",
            "history": "SELECT t.data FROM tracks t JOIN history h ON t.id=h.id ORDER BY h.played DESC",
            "downloads": "SELECT t.data FROM tracks t JOIN downloads d ON t.id=d.id WHERE d.path IS NOT NULL ORDER BY d.created DESC",
        }
        if category not in queries:
            raise ValueError("Unknown library view")
        with self.connect() as db:
            return [Track.parse(json.loads(row[0])) for row in db.execute(queries[category])]

    def remove_history(self, id: str | None = None) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM history WHERE id=?", (id,)) if id else db.execute("DELETE FROM history")

    def playlists(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) | {"data": json.loads(row["data"])} for row in db.execute("SELECT * FROM playlists ORDER BY name")]

    def save_playlist(self, name: str, tracks: list[Track], id: str | None = None) -> str:
        if not name.strip() or len(name) > 160 or len(tracks) > 10000:
            raise ValueError("Invalid playlist name or size")
        for track in tracks:
            track.validate()
        id = id or str(uuid4())
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO playlists VALUES (?,?,?)", (id, name.strip(), json.dumps([t.json() for t in tracks], ensure_ascii=False)))
        return id

    def delete_playlist(self, id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM playlists WHERE id=?", (id,))

    def remember_query(self, query: str, scope: str) -> None:
        query = " ".join(query.split())[:500]
        if not query:
            return
        with self.connect() as db:
            db.execute("INSERT INTO queries VALUES (?,?,0,?) ON CONFLICT(query,scope) DO UPDATE SET used=excluded.used", (query, scope, time.time_ns()))
            db.execute("DELETE FROM queries WHERE rowid IN (SELECT rowid FROM queries ORDER BY pinned DESC, used DESC LIMIT -1 OFFSET 50)")

    def queries(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM queries ORDER BY pinned DESC,used DESC")]

    def pin_query(self, query: str, scope: str, pinned: bool) -> None:
        with self.connect() as db:
            if pinned and db.execute("SELECT COUNT(*) FROM queries WHERE pinned=1").fetchone()[0] >= 10:
                raise ValueError("Up to 10 pinned searches")
            db.execute("UPDATE queries SET pinned=? WHERE query=? AND scope=?", (pinned, query, scope))

    def forget_query(self, query: str | None = None, scope: str | None = None) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM queries WHERE query=? AND scope=?", (query, scope)) if query else db.execute("DELETE FROM queries")

    def download(self, id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM downloads WHERE id=?", (id,)).fetchone()
            return dict(row) if row else None

    def downloads(self, unfinished: bool = False) -> list[dict]:
        with self.connect() as db:
            where = "WHERE state IN ('QUEUED','RUNNING')" if unfinished else ""
            return [dict(row) for row in db.execute(f"SELECT * FROM downloads {where} ORDER BY created")]

    def queue_download(self, track: Track, destination: str, folder: str | None = None) -> None:
        if destination not in {"app", "device"} or (destination == "device" and not folder):
            raise ValueError("Choose an explicit download destination")
        self.put_track(track)
        with self.connect() as db:
            row = db.execute("SELECT * FROM downloads WHERE id=?", (track.id,)).fetchone()
            if row and row["path"] and Path(row["path"]).is_file():
                if destination == "app" or (row["device_path"] and Path(row["device_path"]).is_file()):
                    db.execute("UPDATE downloads SET state='DONE',error=NULL WHERE id=?", (track.id,))
                    return
            if row:
                db.execute("UPDATE downloads SET state='QUEUED',destination=?,folder=?,error=NULL WHERE id=?", (destination, folder, track.id))
            else:
                db.execute("INSERT INTO downloads(id,state,destination,folder,created) VALUES (?,'QUEUED',?,?,?)", (track.id, destination, folder, time.time_ns()))

    def update_download(self, id: str, **fields) -> None:
        allowed = {"state", "path", "device_path", "bytes", "total", "error"}
        if not fields or not set(fields) <= allowed:
            raise ValueError("Invalid download update")
        with self.connect() as db:
            db.execute("UPDATE downloads SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?", (*fields.values(), id))

    def delete_download(self, id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM downloads WHERE id=?", (id,))

    def projects(self) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM projects")]

    def project(self, id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (id,)).fetchone()
            if not row:
                raise ValueError("Project no longer exists")
            return json.loads(row[0])

    def change_project(self, id: str, change: Callable[[dict], None]) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (id,)).fetchone()
            if not row:
                raise ValueError("Project no longer exists")
            project = json.loads(row[0])
            change(project)
            db.execute("UPDATE projects SET data=? WHERE id=?", (json.dumps(project, ensure_ascii=False), id))
            return project

    def create_project(self, name: str) -> str:
        if not name.strip() or len(name) > 160:
            raise ValueError("Use a project name of 1–160 characters")
        id = str(uuid4())
        project = {"version": 1, "id": id, "name": name.strip(), "sources": [], "clips": []}
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES (?,?)", (id, json.dumps(project, ensure_ascii=False)))
        return id
