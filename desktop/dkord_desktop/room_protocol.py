"""Wire-compatible port of Android data/room (v1), NOT a second room protocol.

Public metadata only. P-256 identities are ephemeral, unrelated to release keys.
All canonical JSON defaults/prefixes/UTF-16 truncation match the Kotlin codecs.
No network or Qt imports: desktop/Android cross-language fixtures test this layer.
"""
from __future__ import annotations
import base64
from copy import deepcopy
import hashlib
import json
import re
import secrets
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .models import Track, VIDEO_ID

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
MAX_BYTES = 4000
MAX_QUEUE = 10
MAX_POSITION = 7 * 24 * 60 * 60 * 1000
MAX_MEMBERS = 48
TOKEN = re.compile(r'[A-Za-z0-9_-]+\Z')
NONCE = re.compile(r'[a-f0-9]{32}\Z')
MODES = ('HOST_ONLY', 'SELECTED', 'EVERYONE')
KINDS = ('HELLO', 'POLICY', 'CONTROL')


def normalize_code(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    code = ''.join(c for c in value.strip().upper() if not c.isspace() and c != '-')
    return code if len(code) == 10 and all(c in ALPHABET for c in code) else None


def _short(value: str, limit=96, name=False) -> str:
    if not isinstance(value, str):
        raise ValueError('Invalid room text')
    # Kotlin String.take counts UTF-16 code units, NOT Python Unicode code points.
    value = ''.join(c for c in value if not (ord(c) <= 31 or 127 <= ord(c) <= 159)
                    and not (name and (0x202a <= ord(c) <= 0x202e or 0x2066 <= ord(c) <= 0x2069)))
    if name:
        value = value.strip()
    return value.encode('utf-16-be')[:limit * 2].decode('utf-16-be', errors='ignore')


def display_name(value: str) -> str:
    return _short(value, 48, True)


def _thumbnail(value) -> str | None:
    if not isinstance(value, str) or len(value.encode('utf-16-be')) > 1024:
        return None
    try:
        url = urlsplit(value)
        return value if url.scheme == 'https' and url.hostname and url.username is None and not any(c.isspace() for c in value) else None
    except ValueError:
        return None


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True, allow_nan=False).encode('utf-8')


def _integer(value, minimum=0, maximum=(1 << 63) - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid room integer')
    return value


def _load(text, limit=MAX_BYTES):
    if not isinstance(text, str) or len(text.encode('utf-8')) >= limit:
        raise ValueError('Room message too large')
    value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid number')))
    if not isinstance(value, dict):
        raise ValueError('Invalid room object')
    return value


def _track(row) -> dict:
    if not isinstance(row, dict) or not isinstance(row.get('videoId'), str) or not VIDEO_ID.fullmatch(row['videoId']):
        raise ValueError('Invalid room song')
    title = _short(row['title'])
    if not title.strip():
        raise ValueError('Empty room song')
    return dict(videoId=row['videoId'], title=title, artist=_short(row['artist']), thumbnail=_thumbnail(row.get('thumbnail')))


def normalize_state(value: dict) -> dict:
    track = _track(value)
    if value.get('version', 1) != 1 or type(value.get('version', 1)) is not int or type(value['playing']) is not bool:
        raise ValueError('Unsupported room state')
    queue = value.get('queue', [])
    if not isinstance(queue, list) or len(queue) > MAX_QUEUE:
        raise ValueError('Invalid room queue')
    clean_queue, seen = [], {track['videoId']}
    for row in queue:
        item = _track(row)
        if item['videoId'] not in seen:
            seen.add(item['videoId']); clean_queue.append(item)
    authority = value.get('authority')
    if authority is not None:
        if not isinstance(authority, dict):
            raise ValueError('Invalid room authority')
        authority = {key: authority[key] for key in ('room', 'publicKey', 'session', 'sequence')}
        authority['signature'] = value['authority'].get('signature', '')
        for key in ('room', 'publicKey', 'session', 'signature'):
            if not isinstance(authority[key], str):
                raise ValueError('Invalid room authority')
        _integer(authority['sequence'])
    return dict(**track, positionMs=_integer(value['positionMs'], 0, MAX_POSITION), playing=value['playing'],
                timestamp=_integer(value['timestamp'], 1), queue=clean_queue, version=1, authority=authority)


def encode_state(value: dict, max_bytes=MAX_BYTES) -> str:
    if not 1500 <= max_bytes <= MAX_BYTES:
        raise ValueError('Invalid room budget')
    # Android encoder truncates/deduplicates the queue before decode validation.
    value = deepcopy(value)
    queue, seen = [], {value.get('videoId')}
    for row in value.get('queue', []):
        if (isinstance(row, dict) and isinstance(row.get('videoId'), str) and VIDEO_ID.fullmatch(row['videoId'])
                and isinstance(row.get('title'), str) and _short(row['title']).strip() and row['videoId'] not in seen):
            seen.add(row['videoId']); queue.append(row)
            if len(queue) == MAX_QUEUE:
                break
    value['queue'] = queue
    clean = normalize_state(value)
    result = dumps(clean)
    if len(result.encode('utf-8')) >= max_bytes:
        clean['thumbnail'] = None
        for row in clean['queue']:
            row['thumbnail'] = None
        result = dumps(clean)
    while len(result.encode('utf-8')) >= max_bytes and clean['queue']:
        clean['queue'].pop(); result = dumps(clean)
    if len(result.encode('utf-8')) >= max_bytes:
        raise ValueError('Room message too large')
    return result


def decode_state(text: str) -> dict | None:
    try:
        return normalize_state(_load(text))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return None


def snapshot(tracks: list[Track], index: int, position: int, playing: bool, timestamp: int) -> dict | None:
    if not 0 <= index < len(tracks) or tracks[index].local:
        return None
    def convert(track):
        return dict(videoId=track.id, title=track.title, artist=track.artist, thumbnail=track.thumbnail)
    current = tracks[index]
    state = dict(**convert(current), positionMs=max(0, min(MAX_POSITION, position)), playing=playing,
                 timestamp=timestamp, queue=[convert(t) for t in tracks[index + 1:] if not t.local and t.id != current.id][:MAX_QUEUE])
    return decode_state(encode_state(state))


def state_tracks(value: dict) -> list[Track]:
    return [Track(row['videoId'], row['title'], row['artist'], thumbnail=row['thumbnail']) for row in [value, *value['queue']]]


def synchronized_position(value: dict, now: int) -> int:
    elapsed = max(0, min(MAX_POSITION, now - value['timestamp'])) if value['playing'] else 0
    return min(MAX_POSITION, max(0, value['positionMs']) + elapsed)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')


def _decode(value: str) -> bytes:
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise ValueError('Invalid room token')
    data = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    if _encode(data) != value:
        raise ValueError('Noncanonical room token')
    return data


def member_id(public_key: str) -> str:
    return hashlib.sha256(_decode(public_key)).digest()[:16].hex()


def owner_code(public_key: str) -> str:
    value = int.from_bytes(hashlib.sha256(_decode(public_key)).digest(), 'big')
    return ''.join(ALPHABET[(value >> (256 - 5 * (i + 1))) & 31] for i in range(10))


def _public_key(value: str):
    if not 120 <= len(value) <= 128:
        raise ValueError('Invalid room public key')
    key = serialization.load_der_public_key(_decode(value))
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError('Invalid room key curve')
    return key


def verify(public_key: str, signature: str, content: bytes) -> bool:
    try:
        if not isinstance(signature, str) or not 86 <= len(signature) <= 104:
            return False
        _public_key(public_key).verify(_decode(signature), content, ec.ECDSA(hashes.SHA256()))
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False


def state_bytes(value: dict) -> bytes:
    unsigned = deepcopy(value)
    if unsigned.get('authority'):
        unsigned['authority']['signature'] = ''
    return b'dkord-room-state-v1\n' + canonical(unsigned)


def verify_state(value: dict, code: str) -> bool:
    try:
        auth = value['authority']
        return bool(auth and auth['room'] == code and type(auth['sequence']) is int and auth['sequence'] > 0
                    and NONCE.fullmatch(auth['session']) and owner_code(auth['publicKey']) == code
                    and verify(auth['publicKey'], auth['signature'], state_bytes(value)))
    except (ValueError, TypeError, KeyError):
        return False


def control_frame(room: str, kind: str, public_key: str, timestamp: int, sequence=1, **extra) -> dict:
    return dict(room=room, kind=kind, publicKey=public_key, timestamp=timestamp, sequence=sequence,
                session=extra.get('session', ''), name=extra.get('name', ''), mode=extra.get('mode', 'HOST_ONLY'),
                revision=extra.get('revision', 0), selected=extra.get('selected', []), snapshot=extra.get('snapshot'),
                signature=extra.get('signature', ''), version=extra.get('version', 1))


def control_bytes(value: dict) -> bytes:
    return b'dkord-room-controls-v1\n' + canonical({**value, 'signature': ''})


def verify_control(value: dict, code: str) -> bool:
    try:
        if (value['version'] != 1 or type(value['version']) is not int or normalize_code(code) != code
                or value['room'] != code or value['kind'] not in KINDS or value['mode'] not in MODES
                or value['name'] != display_name(value['name'])):
            return False
        _integer(value['timestamp'], 1); _integer(value['sequence'], 1); _integer(value['revision'])
        selected = value['selected']
        if (not isinstance(selected, list) or len(selected) > MAX_MEMBERS or len(set(selected)) != len(selected)
                or any(not isinstance(s, str) or not NONCE.fullmatch(s) for s in selected)):
            return False
        if value['kind'] == 'HELLO':
            if value['snapshot'] is not None or not isinstance(value['session'], str) or (value['session'] and not NONCE.fullmatch(value['session'])):
                return False
        else:
            if value['revision'] <= 0 or not isinstance(value['session'], str) or not NONCE.fullmatch(value['session']):
                return False
            if value['kind'] == 'POLICY':
                if value['snapshot'] is not None or owner_code(value['publicKey']) != code:
                    return False
            else:
                state = value['snapshot']
                if (not state or state.get('authority') is not None or state['timestamp'] != value['timestamp']
                        or decode_state(encode_state(state, 2200)) != state):
                    return False
        return len(dumps(value).encode('utf-8')) < MAX_BYTES and verify(value['publicKey'], value['signature'], control_bytes(value))
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return False


def encode_control(value: dict) -> str:
    if not verify_control(value, value.get('room', '')):
        raise ValueError('Invalid room control message')
    return dumps(value)


def decode_control(text: str) -> dict | None:
    try:
        raw = _load(text)
        value = control_frame(raw['room'], raw['kind'], raw['publicKey'], raw['timestamp'], raw['sequence'],
                              **{k: v for k, v in raw.items() if k not in ('room', 'kind', 'publicKey', 'timestamp', 'sequence')})
        if value['snapshot'] is not None:
            value['snapshot'] = normalize_state(value['snapshot'])
        return value if verify_control(value, value['room']) else None
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return None


def relay_line(line: str, controls=False):
    try:
        value = _load(line, 16_385)
        if value.get('event') != 'message':
            return None
        message = (decode_control if controls else decode_state)(value['message'])
        cursor = value.get('id')
        if not isinstance(cursor, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', cursor):
            cursor = None
        return (message, cursor) if message else None
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return None


class RoomIdentity:
    def __init__(self, key=None, session=None):
        self._key = key or ec.generate_private_key(ec.SECP256R1())
        if not isinstance(self._key, ec.EllipticCurvePrivateKey) or not isinstance(self._key.curve, ec.SECP256R1):
            raise ValueError('Expected P-256 identity')
        self.public_key = _encode(self._key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.id = member_id(self.public_key)
        self.code = owner_code(self.public_key)
        self.session = session or secrets.token_hex(16)
        if not NONCE.fullmatch(self.session):
            raise ValueError('Invalid room session')
        self.sequence = 0

    def _next(self):
        self.sequence += 1
        return _integer(self.sequence, 1)

    def _sign(self, content: bytes):
        return _encode(self._key.sign(content, ec.ECDSA(hashes.SHA256())))

    def sign_control(self, value: dict) -> dict:
        value = {**deepcopy(value), 'publicKey': self.public_key, 'sequence': self._next(), 'signature': ''}
        value['signature'] = self._sign(control_bytes(value))
        return value

    def sign_state(self, value: dict) -> dict:
        clean = decode_state(encode_state({**value, 'authority': None}, 3000))
        clean['authority'] = dict(room=self.code, publicKey=self.public_key, session=self.session, sequence=self._next(), signature='')
        clean['authority']['signature'] = self._sign(state_bytes(clean))
        # Encoding signed data must never trim it AFTER signing.
        encoded = encode_state(clean)
        if decode_state(encoded) != clean:
            raise ValueError('Signed room state changed during encoding')
        return clean
