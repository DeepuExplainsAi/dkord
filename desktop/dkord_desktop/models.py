from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


@dataclass(frozen=True)
class Track:
    # Same public metadata keys as Android playlist JSON; no signed URLs or private search intent.
    id: str
    title: str
    artist: str
    album: str | None = None
    durationSec: int = 0
    thumbnail: str | None = None

    @property
    def local(self) -> bool:
        return self.id.startswith("studio:")

    def validate(self) -> Track:
        if self.local:
            if str(UUID(self.id[7:])) != self.id[7:]:
                raise ValueError("Invalid local audio ID")
        elif not VIDEO_ID.fullmatch(self.id):
            raise ValueError("Not a supported YouTube audio ID")
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 2000:
            raise ValueError("Invalid song title")
        if not isinstance(self.artist, str) or len(self.artist) > 2000 or not isinstance(self.durationSec, int) or self.durationSec < 0:
            raise ValueError("Invalid song metadata")
        return self

    def json(self) -> dict:
        return asdict(self)

    @classmethod
    def parse(cls, value: dict) -> Track:
        if not isinstance(value, dict):
            raise ValueError("Expected song metadata")
        return cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value}).validate()


def safe_name(track: Track, suffix: str) -> str:
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", f"{track.artist} - {track.title}").strip(" .")[:160] or "Dkord audio"
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "Dkord " + name
    suffix = suffix.lstrip(".")
    if not re.fullmatch(r"[A-Za-z0-9]{1,8}", suffix):
        raise ValueError("Invalid audio extension")
    # Linux/Android limit filename components in bytes, not Unicode characters.
    # Keep metadata intact and leave space for public-copy collision suffixes.
    name = name.encode("utf-8")[:220].decode("utf-8", errors="ignore").rstrip(" .") or "Dkord audio"
    return name + "." + suffix


def owned_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if path.parent != root.resolve():
        raise ValueError("Path is not an owned media file")
    return path


def clock(ms: int) -> str:
    seconds = max(0, int(ms)) // 1000
    h, seconds = divmod(seconds, 3600)
    m, s = divmod(seconds, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def milliseconds(text: str) -> int:
    value = text.strip()
    if not re.fullmatch(r"\d+(?::\d{1,2}){0,2}(?:\.\d{1,3})?", value):
        raise ValueError("Use seconds, mm:ss or hh:mm:ss (up to three decimal places)")
    pieces = value.split(":")
    if any(float(x) >= 60 for x in pieces[1:]):
        raise ValueError("Minutes/seconds must be below 60")
    result = 0.0
    for item in pieces:
        result = result * 60 + float(item)
    return round(result * 1000)


def public_error(error: BaseException) -> str:
    return re.sub(r"https?://\S+", "[provider URL]", str(error)).strip()[:700] or type(error).__name__
