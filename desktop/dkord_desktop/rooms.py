"""Single-threaded Android-compatible room state machine.

Transport and Qt are adapters. A grant never opts a listener in or starts audio;
only explicit player intents become CONTROL frames. The creator alone publishes
canonical state, including accepted co-host commands. Leave/retry drop pending
intents rather than replaying an old click after a reconnect.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import time

from . import room_protocol as wire


@dataclass(frozen=True)
class Publication:
    channel: str
    frame: dict
    marker: int = 0


class RoomSession:
    def __init__(self, owner: bool, code=None, name='', now=None, on_sync=None, identity=None):
        self.now = now or (lambda: time.time_ns() // 1_000_000)
        self.identity = identity or wire.RoomIdentity()
        self.owner = owner
        self.code = self.identity.code if owner else wire.normalize_code(code)
        if not self.code:
            raise ValueError('Invalid 10-character room code')
        self.name = wire.display_name(name) or ('Host ' if owner else 'Listener ') + self.identity.id[:6]
        self.on_sync = on_sync or (lambda state: None)
        self.active = True
        self.connected = False
        self.follow = False
        self.has_synced = False
        self.error = None
        self.mode = 'HOST_ONLY'
        self.selected: set[str] = set()
        self.members: dict[str, dict] = {}
        self.received: dict[str, int] = {}
        self.owner_key = self.identity.public_key if owner else None
        self.owner_session = self.identity.session if owner else None
        self.revision = 1 if owner else 0
        self.last_policy_sequence = 0
        self.last_state_sequence = 0
        self.owner_seen = self.now() if owner else 0
        self.host = None
        self.current = None
        self.shared_override = None
        self.pending_control = None
        self.pending_state = False
        self.policy = owner
        self.hello = not owner
        self.hello_version = 1
        self.last_presence = self.now()
        self.last_publish = 0
        self.state_revision = 0
        self.last_observed = None
        self.last_observed_at = self.now()

    @property
    def owner_known(self):
        return self.owner_key is not None

    def lease_valid(self):
        return self.owner or (self.owner_seen > 0 and self.now() - self.owner_seen <= 180_000)

    def allowed(self, member):
        return self.mode == 'EVERYONE' or (self.mode == 'SELECTED' and member in self.selected)

    @property
    def can_control(self):
        return self.active and (self.owner or (self.connected and self.revision > 0 and self.lease_valid() and self.allowed(self.identity.id)))

    def set_mode(self, mode):
        if not self.active or not self.owner or mode not in wire.MODES or self.mode == mode:
            return
        self.mode = mode
        if mode == 'HOST_ONLY':
            self.selected.clear()
        self.revision += 1
        self.policy = True

    def set_member(self, member, allow):
        if not self.active or not self.owner or member not in self.members:
            return
        if self.mode == 'SELECTED' and (member in self.selected) == allow:
            return
        if allow:
            self.selected.add(member)
        else:
            self.selected.discard(member)
        self.mode = 'SELECTED'
        self.revision += 1
        self.policy = True

    def _prune(self):
        expired = [member for member, info in self.members.items() if self.now() - info['lastSeen'] > 300_000]
        for member in expired:
            self.members.pop(member, None); self.received.pop(member, None)
        if self.selected.intersection(expired):
            self.selected.difference_update(expired)
            self.revision += 1
            self.policy = True

    def tick(self):
        if not self.active:
            return
        now = self.now()
        if now - self.last_presence >= 90_000:
            self.last_presence = now
            if self.owner:
                self._prune(); self.policy = True
            else:
                self.hello = True; self.hello_version += 1
        if not self.owner and self.revision > 0 and not self.lease_valid():
            self.error = 'OWNER_OFFLINE'; self.pending_control = None
        desired = self.shared_override or self.current
        if self.owner and desired and desired['playing'] and now - self.last_publish >= 15_000:
            self.pending_state = True
        if self.pending_control and now - self.pending_control[0]['timestamp'] > 10_000:
            self.pending_control = None

    def observe(self, state):
        """Actual player state, never a guest control intent. Called on the UI thread."""
        if not self.active:
            return
        self.current = state
        if not self.owner:
            return
        now = self.now()
        if self.shared_override:
            target = self.shared_override
            ids = lambda s: [s['videoId']] + [t['videoId'] for t in s['queue']]
            if (state and state['playing'] == target['playing'] and ids(state)[:len(ids(target))] == ids(target)
                    and abs(state['positionMs'] - wire.synchronized_position(target, now)) <= 1500):
                self.shared_override = None
            # Buffering/ack is not another user command or canonical rollback.
            self.last_observed, self.last_observed_at = state, now
            return
        old = self.last_observed
        if state:
            old_position = wire.synchronized_position(old, now) if old else None
            if (not old or state['videoId'] != old['videoId'] or state['playing'] != old['playing']
                    or state['queue'] != old['queue'] or abs(state['positionMs'] - old_position) > 1200):
                self.pending_state = True; self.state_revision += 1
        self.last_observed, self.last_observed_at = state, now

    def command(self, state):
        """Only a deliberate local play/pause/seek/queue action calls this method."""
        if not self.active:
            return
        if self.owner:
            self.shared_override = None
            self.current = state
            self.pending_state = state is not None
            self.state_revision += 1
            if state is None:
                self.error = 'LOCAL_AUDIO'
            return
        if not self.can_control:
            self.pending_control = None
            return
        if state is None:
            self.pending_control = None; self.error = 'LOCAL_AUDIO'
            return
        clean = wire.decode_state(wire.encode_state({**state, 'authority': None}, 2200))
        self.pending_control = (clean, self.revision)

    def set_follow(self, value):
        if self.owner or not self.active:
            return
        self.follow = bool(value)
        if self.follow:
            self.sync_now()

    def sync_now(self):
        if self.active and not self.owner and self.host:
            self.on_sync(deepcopy(self.host))
            self.has_synced = True

    def receive_state(self, state):
        if not self.active or self.owner:
            return False
        now = self.now()
        if (state['timestamp'] > now + 300_000 or state['timestamp'] < now - 43_200_000
                or (self.host and state['timestamp'] <= self.host['timestamp'])):
            return False
        authority = state.get('authority')
        if authority is None:
            if self.owner_known:  # Never downgrade an authenticated session to legacy unsigned state.
                return False
        else:
            if (not wire.verify_state(state, self.code)
                    or (self.owner_key is not None and (self.owner_key != authority['publicKey'] or self.owner_session != authority['session']))
                    or authority['sequence'] <= self.last_state_sequence):
                return False
            self.owner_key, self.owner_session = authority['publicKey'], authority['session']
            self.last_state_sequence = authority['sequence']; self.owner_seen = now
        self.host = deepcopy(state)
        self.error = None
        if self.follow:
            self.sync_now()
        return True

    def receive_control(self, frame):
        if not self.active or not wire.verify_control(frame, self.code) or frame['publicKey'] == self.identity.public_key:
            return False
        now = self.now()
        if frame['timestamp'] > now + 60_000 or frame['timestamp'] < now - 180_000:
            return False
        member = wire.member_id(frame['publicKey'])
        if self.owner:
            if (frame['kind'] == 'POLICY' or (frame['session'] and frame['session'] != self.owner_session)
                    or frame['sequence'] <= self.received.get(member, 0)):
                return False
            self._prune()
            if frame['kind'] == 'HELLO':
                if member not in self.members and len(self.members) >= wire.MAX_MEMBERS:
                    return False
                self.received[member] = frame['sequence']
                self.members[member] = dict(name=frame['name'] or 'Listener ' + member[:6], lastSeen=now)
                self.policy = True
                return True
            if (frame['kind'] != 'CONTROL' or frame['revision'] != self.revision or not self.allowed(member)
                    or frame['timestamp'] < now - 10_000):
                return False
            if member not in self.members and (self.mode != 'EVERYONE' or len(self.members) >= wire.MAX_MEMBERS):
                return False
            self.received[member] = frame['sequence']
            self.members[member] = dict(name=frame['name'] or 'Listener ' + member[:6], lastSeen=now)
            desired = deepcopy(frame['snapshot'])
            desired['positionMs'] = wire.synchronized_position(desired, now)
            desired['timestamp'] = now
            self.shared_override = desired
            self.pending_state = True; self.state_revision += 1
            self.on_sync(deepcopy(desired))
            return True
        if frame['kind'] != 'POLICY':
            return False
        if ((self.owner_key is not None and (self.owner_key != frame['publicKey'] or self.owner_session != frame['session']))
                or frame['sequence'] <= self.last_policy_sequence or frame['revision'] < self.revision):
            return False
        self.owner_key, self.owner_session = frame['publicKey'], frame['session']
        self.last_policy_sequence = frame['sequence']; self.owner_seen = now
        if frame['revision'] != self.revision:
            self.pending_control = None
        self.revision, self.mode, self.selected = frame['revision'], frame['mode'], set(frame['selected'])
        self.connected = True; self.error = None
        return True

    def next_publication(self) -> Publication | None:
        if not self.active:
            return None
        self.tick()
        now = self.now()
        common = dict(session=self.owner_session or '', name=self.name)
        if self.hello:
            frame = wire.control_frame(self.code, 'HELLO', self.identity.public_key, now, **common)
            return Publication('controls', self.identity.sign_control(frame), self.hello_version)
        if self.owner and self.policy:
            frame = wire.control_frame(self.code, 'POLICY', self.identity.public_key, now, **common,
                                       mode=self.mode, revision=self.revision, selected=sorted(self.selected))
            return Publication('controls', self.identity.sign_control(frame), self.revision)
        if not self.owner and self.pending_control:
            state, revision = self.pending_control
            if self.can_control and revision == self.revision and now - state['timestamp'] <= 10_000:
                frame = wire.control_frame(self.code, 'CONTROL', self.identity.public_key, state['timestamp'],
                                           **common, revision=revision, snapshot=state)
                return Publication('controls', self.identity.sign_control(frame), id(state))
            self.pending_control = None
        if self.owner and self.pending_state:
            state = deepcopy(self.shared_override or self.current)
            if not state:
                self.pending_state = False
                return None
            state['positionMs'] = wire.synchronized_position(state, now)
            state['timestamp'] = max(now, (self.host or {}).get('timestamp', 0) + 1)
            return Publication('state', self.identity.sign_state(state), self.state_revision)
        return None

    def acknowledged(self, publication: Publication):
        if not self.active:
            return
        self.connected = True; self.error = None
        frame = publication.frame
        if publication.channel == 'state':
            if publication.marker == self.state_revision:
                self.pending_state = False
            self.host = frame; self.last_publish = self.now()
        elif frame['kind'] == 'HELLO':
            if publication.marker == self.hello_version:
                self.hello = False
        elif frame['kind'] == 'POLICY':
            if publication.marker == self.revision:
                self.policy = False
        elif self.pending_control and publication.marker == id(self.pending_control[0]):
            self.pending_control = None

    def connection_error(self, rate_limited=False):
        if self.active:
            self.connected = False; self.error = 'RATE_LIMIT' if rate_limited else 'NETWORK'

    def retry(self):
        """Retain identity, pinned owner/session, cursors in the adapter; discard old intents."""
        if not self.active:
            return
        self.pending_control = None
        self.connected = False
        self.hello = not self.owner; self.hello_version += 1; self.policy = self.owner

    def leave(self):
        self.active = False
        self.pending_control = None; self.pending_state = False; self.shared_override = None
        self.follow = False; self.connected = False
        # No keys or room codes are written to disk by this layer or its adapters.
