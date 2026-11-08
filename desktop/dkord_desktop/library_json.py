"""Android-compatible Dkord library JSON. Metadata only; never claim this embeds offline files."""
import json
from pathlib import Path
from uuid import uuid4
from .models import Track
from .store import Store

MAX_JSON = 8 * 1024 * 1024


def import_library(store: Store, file: Path) -> None:
    if file.stat().st_size > MAX_JSON:
        raise ValueError("Playlist JSON exceeds 8 MiB")
    doc = json.loads(file.read_text(encoding="utf-8"))
    if doc.get("app") != "dkord" or doc.get("version") != 1:
        raise ValueError("Not a supported Dkord library export; existing data was not changed")
    playlists=[]
    for playlist in doc.get("playlists",[]):
        name=playlist["name"].strip() or "Imported"
        tracks=[Track.parse(t) for t in playlist["tracks"]]
        if len(name)>160 or len(tracks)>10000:
            raise ValueError("Invalid playlist size/name")
        playlists.append((str(uuid4()),name,json.dumps([t.json() for t in tracks],ensure_ascii=False)))
    likes=[Track.parse(t) for t in doc.get("liked",[])]
    # Validate the complete file before one atomic import; no partially overwritten library on errors.
    with store.connect() as db:
        for record in playlists:db.execute("INSERT INTO playlists VALUES (?,?,?)",record)
        for index,track in enumerate(likes):
            db.execute("INSERT INTO tracks VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",(track.id,json.dumps(track.json(),ensure_ascii=False)))
            db.execute("INSERT OR IGNORE INTO likes VALUES (?,?)",(track.id,index))


def export_library(store: Store, file: Path, playlist=None) -> None:
    from .media import atomic_copy
    import tempfile
    playlists=[playlist] if playlist else store.playlists()
    doc={"app":"dkord","version":1,"playlists":[{"name":p["name"],"tracks":[t for t in p["data"] if not Track.parse(t).local]} for p in playlists],
         "liked":[t.json() for t in store.library("liked") if not t.local] if playlist is None else []}
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)/"export.json";source.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8");atomic_copy(source,file)
