from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

from .platforms import WINDOWS_X86
if not WINDOWS_X86:
    import av
from .codec import ffmpeg_exe, ffprobe_exe
from yt_dlp import YoutubeDL

from .models import Track, owned_path, safe_name, public_error
from .provider import Provider
from .store import Store

MAX_AUDIO_BYTES = 512 * 1024 * 1024


class Cancelled(Exception):
    pass


def check_cancel(event: threading.Event | None) -> None:
    if event and event.is_set():
        raise Cancelled("Cancelled; existing audio and project were kept")


def probe(file: Path) -> int:
    if not file.is_file() or file.stat().st_size <= 0 or file.stat().st_size > MAX_AUDIO_BYTES:
        raise ValueError("Audio must be readable and below 512 MiB")
    if WINDOWS_X86:
        return probe_ffmpeg(file)
    with av.open(str(file)) as audio:
        streams = list(audio.streams.audio)
        if not streams:
            raise ValueError("No readable, non-DRM audio stream")
        stream = streams[0]
        seconds = stream.duration * stream.time_base if stream.duration is not None else (audio.duration or 0) / av.time_base
        # Actually decode a frame: an extension/container header alone is not proof of usable audio.
        if next(audio.decode(stream), None) is None:
            raise ValueError("Audio contains no decodable frames")
        ms = int(float(seconds) * 1000)
        if ms <= 0 or ms > 24 * 3600 * 1000:
            raise ValueError("Invalid audio duration")
        return ms


def probe_ffmpeg(file: Path) -> int:
    """Real Win32 FFmpeg decoding; PyAV has no Windows32 wheels. No extension-only probe."""
    command = [ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'info',
               '-protocol_whitelist', 'file,pipe', '-i', str(file), '-map', '0:a:0', '-t', '0.1',
               '-ac', '1', '-ar', '8000', '-c:a', 'pcm_s16le', '-f', 's16le', 'pipe:1']
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    details = result.stderr.decode('utf-8', errors='replace')
    duration = re.search(r'(?m)^  Duration: (\d{2,}):(\d{2}):(\d{2}(?:\.\d+)?),', details)
    if result.returncode or len(result.stdout) < 2 or (duration is None and not WINDOWS_X86):
        raise ValueError('No readable, non-DRM audio stream with decodable frames and a known duration')
    if WINDOWS_X86:
        from decimal import Decimal
        metadata=subprocess.check_output([ffprobe_exe(),'-v','error','-protocol_whitelist','file,pipe','-select_streams','a:0',
                                          '-show_entries','stream=duration:format=duration','-of','json',str(file)],
                                         timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        info=json.loads(metadata);streams=info.get('streams',[])
        value=(streams[0].get('duration') if streams else None) or info.get('format',{}).get('duration')
        if value is None:raise ValueError('Audio duration is not known')
        seconds=Decimal(value)
        if not seconds.is_finite():raise ValueError('Invalid audio duration')
        ms=int(seconds*1000)  # ffprobe preserves sub-centisecond precision; human FFmpeg logs do not.
    else:
        hours, minutes, seconds = duration.groups()
        ms = round((int(hours)*3600 + int(minutes)*60 + float(seconds))*1000)
    if not 0 < ms <= 24*3600*1000:
        raise ValueError('Invalid audio duration')
    return ms


def atomic_copy(source: Path, target: Path, event: threading.Event | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Independent short staging leaf: an already-valid long Unicode name must not
    # overflow the filesystem limit when a UUID is appended for atomic publication.
    stage = target.parent / (".dkord-" + str(uuid4()) + ".part")
    try:
        with source.open("rb") as src, stage.open("xb") as dst:
            while data := src.read(256 * 1024):
                check_cancel(event)
                dst.write(data)
            dst.flush()
            os.fsync(dst.fileno())
        check_cancel(event)
        os.replace(stage, target)
    finally:
        stage.unlink(missing_ok=True)


def publish_device(source: Path, folder: Path, name: str) -> Path:
    """Explicit public copy only. Never silently falls back to private, overwrites or removes the source."""
    if source.stat().st_size <= 0:
        raise ValueError("No completed source audio")
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    candidate = owned_path(folder, name)
    for index in range(10000):
        final = candidate if index == 0 else candidate.with_name(f"{candidate.stem} ({index}){candidate.suffix}")
        try:
            # Reserve our NEW name; never overwrite an existing user file/copy.
            with final.open("xb"):
                pass
        except FileExistsError:
            continue
        try:
            atomic_copy(source, final)
            return final
        except BaseException:
            final.unlink(missing_ok=True)
            raise
    raise ValueError("Too many same-named device copies")


class MediaLibrary:
    def __init__(self, store: Store, provider: Provider | None = None):
        self.store = store
        self.provider = provider or Provider()
        self.offline = store.root / "offline"
        self.work = store.root / "work"
        self.exports = store.root / "exports"
        self.sources = store.root / "studio" / "sources"
        self.temporary = store.root / "studio" / "temporary"
        for path in (self.offline, self.work, self.exports, self.sources, self.temporary):
            path.mkdir(parents=True, exist_ok=True)
        self.publication = threading.RLock()
        self.active: dict[str, threading.Event] = {}
        self.remove_after: set[str] = set()
        # Only studio staging is ephemeral. Paused downloader .part files are deliberately retained.
        for path in self.temporary.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()

    def local_file(self, track: Track) -> Path | None:
        row = self.store.download(track.id)
        if row and row["path"]:
            candidate = Path(row["path"])
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        return None

    def fetch(self, track: Track, target: Path, event: threading.Event, progress=lambda done, total: None) -> Path:
        track.validate()
        if track.local:
            raise ValueError("Local audio is missing; it cannot be fetched from YouTube")
        target.mkdir(parents=True, exist_ok=True)
        last = 0.0
        def hook(data):
            nonlocal last
            check_cancel(event)
            done = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if done > MAX_AUDIO_BYTES or total > MAX_AUDIO_BYTES:
                raise ValueError("Audio exceeds the 512 MiB private preparation limit")
            if time.monotonic() - last >= .2 or data.get("status") == "finished":
                last = time.monotonic()
                progress(done, total)
        quality = self.store.setting("quality", "high")
        format = "bestaudio[ext=m4a]/bestaudio"
        if quality in {"low", "medium"}:
            cap = 64 if quality == "low" else 128
            format = f"bestaudio[ext=m4a][abr<={cap}]/bestaudio[abr<={cap}]/worstaudio"
        # Representation ID in the partial filename prevents appending a newly selected itag to old bytes.
        options = self.provider.options(format=format, outtmpl=str(target / "audio.%(format_id)s.%(ext)s"),
                    progress_hooks=[hook], continuedl=True, nopart=False, writeinfojson=False, max_filesize=MAX_AUDIO_BYTES)
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info("https://www.youtube.com/watch?v=" + track.id, download=True)
            check_cancel(event)
            if not info:
                raise ValueError("Provider returned no audio")
            requested = info.get("requested_downloads") or []
            file = Path((requested[0].get("filepath") if requested else None) or info.get("filepath") or ydl.prepare_filename(info)).resolve()
            if file.parent != target.resolve():
                raise ValueError("Provider output escaped its staging directory")
            probe(file)
            return file

    def process_download(self, id: str, progress=lambda done, total: None) -> None:
        with self.publication:
            if id in self.active:
                return
            row = self.store.download(id)
            if not row or row["state"] != "QUEUED":
                return
            event = threading.Event()
            self.active[id] = event
            self.store.update_download(id, state="RUNNING", error=None)
        work = self.work / hashlib.sha256(id.encode()).hexdigest()
        try:
            track = self.store.track(id)
            if not track:
                raise ValueError("Song metadata is missing")
            source = self.local_file(track)
            if not source and row["device_path"] and Path(row["device_path"]).is_file():
                source = Path(row["device_path"])
            if source is None:
                source = self.fetch(track, work, event, lambda done, total: (
                    self.store.update_download(id, bytes=done, total=total), progress(done, total)))
            check_cancel(event)
            with self.publication:
                check_cancel(event)
                if id in self.remove_after:
                    raise Cancelled()
                current = self.store.download(id)
                if not current:
                    return
                private = self.local_file(track)
                if private is None:
                    private = owned_path(self.offline, hashlib.sha256(id.encode()).hexdigest() + source.suffix)
                    atomic_copy(source, private)
                    # Persist the complete private source BEFORE the fallible public save. Retry needs no network.
                    self.store.update_download(id, path=str(private), bytes=private.stat().st_size, total=private.stat().st_size)
                if work.is_dir():
                    shutil.rmtree(work)
                if current["destination"] == "device":
                    existing = current["device_path"]
                    if not existing or not Path(existing).is_file():
                        public = publish_device(private, Path(current["folder"]), safe_name(track, private.suffix))
                        self.store.update_download(id, device_path=str(public))
                self.store.update_download(id, state="DONE", error=None)
        except BaseException as error:
            with self.publication:
                if self.store.download(id):
                    self.store.update_download(id, state="PAUSED" if event.is_set() or isinstance(error, Cancelled) else "FAILED", error=None if event.is_set() else public_error(error)[:500])
            if not event.is_set() and not isinstance(error, Cancelled):
                raise
        finally:
            with self.publication:
                self.active.pop(id, None)
                if id in self.remove_after:
                    self.remove_after.discard(id)
                    self._remove(id)

    def pause(self, id: str) -> None:
        with self.publication:
            if event := self.active.get(id):
                event.set()
            if self.store.download(id):
                self.store.update_download(id, state="PAUSED")

    def remove(self, id: str) -> None:
        with self.publication:
            if event := self.active.get(id):
                self.remove_after.add(id)
                event.set()
            else:
                self._remove(id)

    def _remove(self, id: str) -> None:
        row = self.store.download(id)
        if row and row["path"]:
            file = Path(row["path"]).resolve()
            if file.parent in {self.offline.resolve(), self.exports.resolve()}:
                file.unlink(missing_ok=True)
        # A device copy is the user's file and is NOT deleted with an in-app download.
        self.store.delete_download(id)
        shutil.rmtree(self.work / hashlib.sha256(id.encode()).hexdigest(), ignore_errors=True)

    def import_source(self, project: str, source: Track | Path, event: threading.Event, progress=lambda done, total: None) -> dict:
        self.store.project(project)  # validate ownership before starting any network/file work
        with tempfile.TemporaryDirectory(dir=self.temporary) as temp:
            staging = Path(temp)
            if isinstance(source, Track):
                title = source.title
                file = self.local_file(source)
                if file is None:
                    file = self.fetch(source, staging, event, progress)
            else:
                file = source
                title = source.stem
            check_cancel(event)
            ms = probe(file)
            id = str(uuid4())
            destination = owned_path(self.sources, id + ".audio")
            prepared = staging / "prepared.audio"
            atomic_copy(file, prepared, event)
            item = {"id": id, "fileName": destination.name, "title": title[:200], "durationMs": ms}
            with self.publication:
                try:
                    check_cancel(event)
                    os.replace(prepared, destination)
                    def append(p):
                        if len(p["sources"]) >= 100:
                            raise ValueError("Up to 100 sources per project")
                        p["sources"].append(item)
                        p["clips"].append({"id": str(uuid4()), "sourceId": id, "startMs": 0, "endMs": ms})
                    self.store.change_project(project, append)
                except BaseException:
                    destination.unlink(missing_ok=True)
                    raise
            return item

    def source_file(self, item: dict) -> Path:
        id = str(UUID(item["id"]))
        if item["fileName"] != id + ".audio":
            raise ValueError("Invalid source reference")
        file = owned_path(self.sources, item["fileName"])
        if not file.is_file():
            raise ValueError("Project audio is missing; import it again")
        return file

    def validate_project(self, project: dict) -> None:
        if project.get("version") != 1 or not project.get("clips") or len(project["clips"]) > 500:
            raise ValueError("Add 1–500 clips before exporting")
        sources = {item["id"]: item for item in project["sources"]}
        for clip in project["clips"]:
            source = sources.get(clip["sourceId"])
            if not source or not (0 <= clip["startMs"] < clip["endMs"] <= source["durationMs"]):
                raise ValueError("Clip ranges must stay inside the selected source")
            self.source_file(source)

    def render(self, project: dict, target: Path, event: threading.Event, progress=lambda fraction: None) -> Path:
        self.validate_project(project)
        sources = {item["id"]: item for item in project["sources"]}
        cmd = [ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
        filters = []
        duration = sum(c["endMs"] - c["startMs"] for c in project["clips"])
        for i, clip in enumerate(project["clips"]):
            cmd += ["-i", str(self.source_file(sources[clip["sourceId"]]))]
            filters.append(f"[{i}:a:0]atrim=start={clip['startMs']/1000:.3f}:end={clip['endMs']/1000:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]")
        filters.append("".join(f"[a{i}]" for i in range(len(project["clips"]))) + f"concat=n={len(project['clips'])}:v=0:a=1[out]")
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-filter_complex", ";".join(filters), "-map", "[out]", "-c:a", "aac", "-b:a", "192k", "-metadata", "title=" + project["name"],
                "-movflags", "+faststart", "-progress", "pipe:1", "-f", "mp4", str(target)]
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            def watchdog():
                deadline = time.monotonic() + 3600
                while process.poll() is None:
                    if event.wait(.1) or time.monotonic() > deadline:
                        process.kill()
                        return
            watcher = threading.Thread(target=watchdog, daemon=True)
            watcher.start()
            try:
                for line in process.stdout:
                    if line.startswith(b"out_time_us="):
                        value = line.split(b"=", 1)[1].strip()
                        if value.isdigit():
                            progress(min(1, int(value) / 1000 / duration))
                code = process.wait()
                check_cancel(event)
                if code:
                    errors.seek(0)
                    raise ValueError("Audio rendering failed: " + errors.read(4000).decode(errors="replace"))
                probe(target)
                return target
            except BaseException:
                process.kill() if process.poll() is None else None
                process.wait()
                target.unlink(missing_ok=True)
                raise
            finally:
                process.stdout.close()
                watcher.join(timeout=1)

    def export(self, project_id: str, event: threading.Event, progress=lambda fraction: None) -> Track:
        with self.publication:
            project = self.store.project(project_id)  # immutable, pinned snapshot, not live UI state
            self.validate_project(project)
            id = str(uuid4())
            with self.store.connect() as db:
                db.execute("INSERT INTO renders VALUES (?,?,'RUNNING',NULL)", (id, json.dumps(project, ensure_ascii=False)))
        try:
            with tempfile.TemporaryDirectory(dir=self.temporary) as temp:
                output = self.render(project, Path(temp) / "mix.m4a", event, progress)
                check_cancel(event)
                final = owned_path(self.exports, id + ".m4a")
                atomic_copy(output, final)
                track = Track("studio:" + id, project["name"], "Dkord Mashup Studio", durationSec=probe(final) // 1000)
                self.store.put_track(track)
                self.store.queue_download(track, "app")
                self.store.update_download(track.id, state="DONE", path=str(final), bytes=final.stat().st_size, total=final.stat().st_size)
                with self.store.connect() as db:
                    db.execute("UPDATE renders SET state='DONE' WHERE id=?", (id,))
                return track
        except BaseException as error:
            with self.store.connect() as db:
                db.execute("UPDATE renders SET state=?,error=? WHERE id=?", ("CANCELLED" if event.is_set() else "FAILED", public_error(error)[:500], id))
            raise

    def delete_project(self, id: str) -> None:
        with self.publication:
            # Validate all pin metadata BEFORE committing deletion/doing any filesystem garbage collection.
            self._source_pins(excluding=id)
            with self.store.connect() as db:
                db.execute("DELETE FROM projects WHERE id=?", (id,))
            self.gc_sources()

    def _source_pins(self, excluding: str | None = None) -> set[str]:
        with self.store.connect() as db:
            projects = [json.loads(row[0]) for row in db.execute("SELECT data FROM projects WHERE id != ?", (excluding or "",))]
            projects += [json.loads(row[0]) for row in db.execute("SELECT data FROM renders WHERE state='RUNNING'")]
        pinned = set()
        for project in projects:
            if project.get("version") != 1:
                raise ValueError("Unknown project metadata; source recovery is required")
            for source in project["sources"]:
                if source["fileName"] != str(UUID(source["id"])) + ".audio":
                    raise ValueError("Invalid source metadata; no files were garbage-collected")
                pinned.add(source["fileName"])
        return pinned

    def gc_sources(self) -> None:
        with self.publication:
            pinned = self._source_pins()
            for source in self.sources.glob("*.audio"):
                if source.name not in pinned:
                    try:
                        if str(UUID(source.stem)) == source.stem:
                            source.unlink(missing_ok=True)
                    except (ValueError, OSError):
                        pass
