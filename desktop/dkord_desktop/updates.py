from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives import hashes, serialization

from . import __version__
from .media import check_cancel
from .platforms import platform_key, TARGETS

REPO = "DeepuExplainsAi/dkord"
API = f"https://api.github.com/repos/{REPO}"
MAX_MANIFEST = 128 * 1024
UPDATE_DOMAIN = b"DKORD-DESKTOP-UPDATE-V2\x00"
MAX_PACKAGE = 1024 * 1024 * 1024
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")


def version(value: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError("Only stable three-component desktop versions are accepted")
    return tuple(map(int, match.groups()))


def trusted_url(url: str, tag: str, name: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.netloc == "github.com" and not parsed.query and not parsed.fragment
            and parsed.path == f"/{REPO}/releases/download/{tag}/{name}")


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Update:
    version: str
    tag: str
    name: str
    url: str
    size: int
    sha256: str
    kind: str
    platform: str
    manifest: bytes


def verify_manifest(raw: bytes, trusted_keys: dict[str, str | dict], installed: str = __version__, target: str | None = None, image: bool | None = None) -> Update | None:
    if len(raw) > MAX_MANIFEST:
        raise ValueError("Desktop update manifest is too large")
    envelope = json.loads(raw, object_pairs_hook=no_duplicates)
    if set(envelope) != {"payload", "keyId", "signature"} or envelope["keyId"] not in trusted_keys:
        raise ValueError("Not signed by an installed Dkord desktop update key")
    payload = envelope["payload"]
    root = trusted_keys[envelope["keyId"]]
    signature = base64.b64decode(envelope["signature"], validate=True)
    if isinstance(root, str):
        # Preserve verification of legacy owner-controlled Ed25519 channels. They
        # remain disjoint from Android's latest tag and cannot opt into format 2.
        if payload.get("format") != 1:
            raise ValueError("Legacy update key cannot authorize a different format")
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(root, validate=True))
        key.verify(signature, canonical(payload))
        prefix = "desktop-v"
    elif isinstance(root, dict):
        if (set(root) != {"algorithm", "publicKey", "certificateSha256"} or payload.get("format") != 2
                or not isinstance(root["certificateSha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", root["certificateSha256"])):
            raise ValueError("Invalid installed update identity")
        key = serialization.load_der_public_key(base64.b64decode(root["publicKey"], validate=True))
        message = UPDATE_DOMAIN + canonical(payload)  # never an APK/room/other signing protocol
        if root["algorithm"] == "rsa-pkcs1-sha256" and isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048:
            key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        elif root["algorithm"] == "ecdsa-p256-sha256" and isinstance(key, ec.EllipticCurvePublicKey) and isinstance(key.curve, ec.SECP256R1):
            key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        else:
            raise ValueError("Unsupported pinned update key algorithm")
        prefix = "v"
    else:
        raise ValueError("Invalid installed update root")
    if payload.get("channel") != "desktop":
        raise ValueError("Not a supported desktop update channel")
    current = payload["version"]
    version(current)
    if version(current) <= version(installed):
        return None
    tag = prefix + current
    if payload.get("tag") != tag:
        raise ValueError("Update version/tag mismatch")
    target = target or platform_key()
    if target not in TARGETS:
        return None
    artifact = payload.get("assets", {}).get(target)
    if artifact is None:
        return None  # never substitute another OS or architecture
    if image is None:
        image = bool(os.environ.get("APPIMAGE"))
    if target.startswith("linux"):
        artifact = artifact.get("appimage" if image else "deb")
        if artifact is None:
            return None
    kind = artifact["kind"]
    extension = {"windows": ("exe", ".exe"), "macos": ("pkg", ".pkg"), "linux": ("appimage", ".AppImage") if image else ("deb", ".deb")}[target.split("-")[0]]
    name = artifact["name"]
    if kind != extension[0] or not name.endswith(extension[1]) or not re.fullmatch(r"Dkord-desktop-v[0-9.]+-(windows|macos|linux)-(x64|arm64|x86)\.(exe|pkg|deb|AppImage)", name):
        raise ValueError("Wrong platform installer type/name")
    expected = f"Dkord-desktop-v{current}-{target}{extension[1]}"
    if name != expected or not trusted_url(artifact["url"], tag, name):
        raise ValueError("Installer origin or OS/CPU filename mismatch")
    size = artifact["size"]
    digest = artifact["sha256"]
    if type(size) is not int or not 1024 <= size <= MAX_PACKAGE or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid bounded size/digest")
    return Update(current, tag, name, artifact["url"], size, digest, kind, target, raw)


class Updater:
    """Consent-based platform/architecture-correct desktop channel, disjoint from the APK latest feed.

    Format 2 pins the previously published APK signing identity and domain-separates
    its desktop manifest signatures. Never accepts an APK as a desktop installer.
    This is application update verification, not OS Authenticode/notarization.
    """
    def __init__(self, cache: Path, keys: dict[str, str | dict] | None = None):
        self.cache = cache
        self.keys = keys if keys is not None else self.production_keys()

    @staticmethod
    def production_keys() -> dict[str, str | dict]:
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        return json.loads((root / "assets" / "update-keys.json").read_text())

    def check(self) -> Update | None:
        if not self.keys:
            raise ValueError("Desktop preview: no official signed desktop update channel is published/configured yet. No APK or untrusted installer will be offered.")
        with requests.Session() as session:
            session.headers.update({"Accept": "application/vnd.github+json", "User-Agent": f"Dkord-Desktop/{__version__}"})
            for page in range(1, 4):
                response = session.get(API + f"/releases?per_page=100&page={page}", timeout=20)
                response.raise_for_status()
                releases = response.json()
                for release in releases:
                    tag = release.get("tag_name", "")
                    if release.get("draft") or release.get("prerelease"):
                        continue
                    candidate = tag[9:] if tag.startswith("desktop-v") else tag[1:] if tag.startswith("v") else ""
                    try:
                        if version(candidate) <= version(__version__):
                            continue
                    except (TypeError, ValueError):
                        continue
                    name = f"Dkord-desktop-v{candidate}-manifest.json"
                    asset = next((a for a in release.get("assets", []) if a.get("name") == name), None)
                    if not asset or not trusted_url(asset["browser_download_url"], tag, name) or asset.get("size", MAX_MANIFEST + 1) > MAX_MANIFEST:
                        continue
                    with session.get(asset["browser_download_url"], stream=True, timeout=20) as body:
                        body.raise_for_status()
                        raw = bytearray()
                        for chunk in body.iter_content(8192):
                            raw.extend(chunk)
                            if len(raw) > MAX_MANIFEST:
                                raise ValueError("Desktop update manifest is too large")
                    update = verify_manifest(bytes(raw), self.keys)
                    if update and update.tag == tag:
                        return update
                if len(releases) < 100:
                    break
        return None

    @staticmethod
    def validate_file(path: Path, update: Update, *, require_name: bool = True) -> None:
        if (require_name and path.name != update.name) or path.stat().st_size != update.size:
            raise ValueError("Installer size/name mismatch")
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != update.sha256:
            raise ValueError("Installer SHA-256 verification failed")
        with path.open("rb") as file:
            header = file.read(32)
        magic = {"exe": b"MZ", "pkg": b"xar!", "deb": b"!<arch>\n", "appimage": b"\x7fELF"}[update.kind]
        if not header.startswith(magic):
            raise ValueError("Package content is not the expected native installer type")
        if update.kind == "appimage":
            expected = 62 if update.platform.endswith("-x64") else 183
            if header[5] != 1 or int.from_bytes(header[18:20], "little") != expected:
                raise ValueError("AppImage ELF architecture does not match this application")

    def verify_plan(self, update: Update) -> None:
        verified = verify_manifest(update.manifest, self.keys)
        if verified is None or verified != update:
            raise ValueError("Update plan no longer matches a newer trusted manifest")

    def download(self, update: Update, event, progress=lambda done, total: None) -> Path:
        self.verify_plan(update)
        if update.platform != platform_key():
            raise ValueError("This update is not for the running application's OS/CPU")
        self.cache.mkdir(parents=True, exist_ok=True)
        final = self.cache / update.name
        if final.exists():
            try:
                self.validate_file(final, update)
                return final
            except ValueError:
                final.unlink()
        partial = final.with_suffix(final.suffix + ".part")
        try:
            total = 0
            with requests.get(update.url, stream=True, timeout=(15, 30)) as response, partial.open("wb") as file:
                response.raise_for_status()
                for block in response.iter_content(256 * 1024):
                    check_cancel(event)
                    total += len(block)
                    if total > update.size:
                        raise ValueError("Installer exceeds the signed size")
                    file.write(block)
                    progress(total, update.size)
                file.flush()
                os.fsync(file.fileno())
            if total != update.size:
                raise ValueError("Installer is incomplete")
            os.replace(partial, final)
            self.validate_file(final, update)
            return final
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

    def install(self, update: Update, file: Path) -> Callable[[], None] | None:
        self.verify_plan(update)
        if update.platform != platform_key() or version(update.version) <= version(__version__):
            raise ValueError("Wrong-platform or downgrade installation refused")
        self.validate_file(file, update)  # recheck immediately before native installer launch
        if update.kind == "exe" and sys.platform == "win32":
            subprocess.Popen([str(file)], shell=False)
        elif update.kind == "pkg" and sys.platform == "darwin":
            subprocess.Popen(["open", str(file)], shell=False)
        elif update.kind == "deb" and sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(file)], shell=False)
        elif update.kind == "appimage" and os.environ.get("APPIMAGE"):
            from .media import atomic_copy
            target = Path(os.environ["APPIMAGE"]).resolve()
            if not target.is_file() or not os.access(target.parent, os.W_OK):
                raise ValueError("Installed AppImage location is not writable. Move it to a user-owned applications folder first.")
            # Linux keeps the running inode mounted; atomic replace changes only the executable, never user data.
            atomic_copy(file, target)
            target.chmod(target.stat().st_mode | 0o111)
            # Do not race the old process's QLockFile: main calls this only after Qt
            # has exited, cancelled workers have drained and the data lock is released.
            def relaunch():
                self.verify_plan(update)
                self.validate_file(target, update, require_name=False)  # installed AppImages may be user-renamed
                env = os.environ.copy()
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                subprocess.Popen([str(target)], shell=False, env=env)
            return relaunch
        else:
            raise ValueError("Unsupported native installer for this running distribution")
