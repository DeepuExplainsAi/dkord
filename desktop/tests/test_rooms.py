"""Executed natively on all six profiles, including Win32 cryptography/Qt5 hosts."""
from copy import deepcopy
import json
from pathlib import Path
import queue
import threading
import time
import unittest

from dkord_desktop import room_protocol as wire
from dkord_desktop.models import Track
from dkord_desktop.rooms import RoomSession, Publication
from dkord_desktop.room_transport import NtfyTransport, RoomTransportError, RoomConnection


class RoomProtocolTest(unittest.TestCase):
    def setUp(self):
        self.clock = [1_800_000_000_000]
        self.now = lambda: self.clock[0]
        self.syncs = [[], [], []]
        self.host = RoomSession(True, now=self.now, on_sync=self.syncs[0].append)
        self.guests = [RoomSession(False, self.host.code, name=name, now=self.now, on_sync=self.syncs[i+1].append)
                       for i, name in enumerate(('Asha', 'रवि 🎵'))]
        self.all = [self.host, *self.guests]
        self.track = Track('abcdefghijk', 'गाना 🎵', 'Singer')
        self.state = wire.snapshot([self.track, Track('lmnopqrstuv', 'Second', 'Artist')], 0, 1234, True, self.now())

    def drain(self):
        for _ in range(30):
            any_sent = False
            for sender in self.all:
                publication = sender.next_publication()
                if publication:
                    any_sent = True
                    encoded = (wire.encode_control if publication.channel == 'controls' else wire.encode_state)(publication.frame)
                    decoded = (wire.decode_control if publication.channel == 'controls' else wire.decode_state)(encoded)
                    self.assertIsNotNone(decoded)
                    for recipient in self.all:
                        (recipient.receive_control if publication.channel == 'controls' else recipient.receive_state)(decoded)
                    sender.acknowledged(publication)
            if not any_sent:
                return
        self.fail('Publication loop/echo did not quiesce')

    def test_room_codes_match_android_alphabet_normalization_and_owner_commitment(self):
        self.assertEqual('ABCDEFGHJK', wire.normalize_code(' abcd-ef ghjk\n'))
        for bad in ('ABCDEFGHIJ', 'ABCD0FGHJK', '../danger', None):
            self.assertIsNone(wire.normalize_code(bad))
        self.assertEqual(self.host.code, wire.owner_code(self.host.identity.public_key))
        self.assertEqual(10, len(self.host.code)); self.assertEqual(32, len(self.host.identity.id))

    def test_state_round_trip_clock_compensation_and_private_studio_filter(self):
        self.assertEqual(self.state, wire.decode_state(wire.encode_state(self.state)))
        self.assertEqual(3234, wire.synchronized_position(self.state, self.now()+2000))
        self.assertEqual(1234, wire.synchronized_position(self.state, self.now()-2000))
        self.assertEqual(wire.MAX_POSITION, wire.synchronized_position({**self.state, 'positionMs': wire.MAX_POSITION}, self.now()+1000))
        from uuid import uuid4
        self.assertIsNone(wire.snapshot([Track('studio:'+str(uuid4()), 'Private', 'Me')], 0, 0, True, self.now()))

    def test_utf16_unicode_budgets_queue_dedup_and_thumbnail_safety(self):
        state = deepcopy(self.state)
        state.update(title='🎵'*70, artist='अ'*150, thumbnail='http://not-https/image')
        state['queue'] = state['queue'] * 20 + [dict(videoId='12345678901', title='Third', artist='A', thumbnail=None)]
        result = wire.decode_state(wire.encode_state(state))
        self.assertEqual('🎵'*48, result['title']); self.assertEqual('अ'*96, result['artist'])
        self.assertIsNone(result['thumbnail']); self.assertEqual(2, len(result['queue']))
        self.assertLess(len(wire.encode_state(result).encode('utf-8')), 4000)
        self.assertEqual('Asha', wire.display_name('\u202eAsha\u2069\n'))

    def test_signed_owner_state_rejects_modified_fields_wrong_room_and_downgrade(self):
        value = self.host.identity.sign_state(self.state)
        self.assertTrue(wire.verify_state(wire.decode_state(wire.encode_state(value)), self.host.code))
        for field, changed in (('playing', False), ('positionMs', 9876), ('title', 'Forged')):
            self.assertFalse(wire.verify_state({**value, field: changed}, self.host.code))
        self.assertTrue(self.guests[0].receive_state(value))
        self.clock[0] += 1
        self.assertFalse(self.guests[0].receive_state({**self.state, 'timestamp': self.now()}))
        self.assertFalse(wire.verify_state(value, self.guests[0].identity.code))

    def test_invalid_json_types_versions_and_unbounded_relay_lines_fail_closed(self):
        for patch in ({'version': 2}, {'positionMs': True}, {'playing': 1}, {'timestamp': 0}, {'videoId': 'local:/secret'}, {'queue': [None]}):
            self.assertIsNone(wire.decode_state(wire.dumps({**self.state, **patch})))
        self.assertIsNone(wire.decode_state(' '*4000))
        self.assertIsNone(wire.decode_state('{"timestamp": NaN}'))
        self.assertIsNone(wire.relay_line('x'*16385))
        self.assertIsNone(wire.relay_line('{"event":"keepalive"}'))
        self.assertEqual((self.state, 'opaque_12'), wire.relay_line(json.dumps(dict(event='message', message=wire.encode_state(self.state), id='opaque_12'))))

    def test_host_only_default_and_permission_changes_never_start_any_listener(self):
        self.host.observe(self.state); self.drain()
        self.assertEqual('HOST_ONLY', self.host.mode)
        self.assertFalse(self.guests[0].can_control)
        self.host.set_member(self.guests[0].identity.id, True); self.drain()
        self.assertTrue(self.guests[0].can_control); self.assertFalse(self.guests[1].can_control)
        self.assertEqual([[], [], []], self.syncs)
        self.assertFalse(self.guests[0].follow); self.assertFalse(self.guests[1].follow)
        self.host.set_member(self.guests[1].identity.id, True); self.drain()
        self.assertTrue(all(guest.can_control for guest in self.guests))
        self.assertEqual([[], [], []], self.syncs)

    def test_selected_cohost_intent_is_canonical_for_opted_in_followers_without_echo(self):
        self.host.observe(self.state); self.drain()
        self.host.set_member(self.guests[0].identity.id, True); self.drain()
        self.guests[1].set_follow(True)
        initial = len(self.syncs[2])
        self.clock[0] += 1000
        desired = wire.snapshot([Track('12345678901', 'New playlist song', 'Singer'), self.track], 0, 4000, True, self.now())
        self.guests[0].command(desired); self.drain()
        self.assertEqual('12345678901', self.syncs[0][-1]['videoId'])
        self.assertEqual('12345678901', self.syncs[2][-1]['videoId'])
        self.assertEqual(initial+1, len(self.syncs[2])); self.assertEqual([], self.syncs[1])
        self.assertEqual('12345678901', self.host.host['videoId'])
        self.host.observe({**desired, 'playing': False})  # transient host buffering is not a rollback/echo
        self.assertIsNone(self.host.next_publication())

    def test_everyone_includes_new_members_but_only_owner_can_administer(self):
        self.drain(); self.host.set_mode('EVERYONE'); self.drain()
        self.assertTrue(all(guest.can_control for guest in self.guests))
        revision = self.host.revision
        self.guests[0].set_mode('HOST_ONLY'); self.guests[0].set_member(self.guests[1].identity.id, False)
        self.assertEqual(revision, self.host.revision); self.assertEqual('EVERYONE', self.guests[0].mode)
        self.host.set_mode('HOST_ONLY'); self.drain()
        self.assertFalse(any(guest.can_control for guest in self.guests)); self.assertEqual(set(), self.host.selected)

    def test_revoke_revision_and_retry_discard_unsent_intents(self):
        self.drain(); self.host.set_mode('EVERYONE'); self.drain()
        self.guests[0].command(self.state); old = self.guests[0].next_publication()
        self.host.set_mode('HOST_ONLY'); self.drain()
        self.assertFalse(self.host.receive_control(old.frame)); self.assertEqual([], self.syncs[0])
        self.host.set_mode('EVERYONE'); self.drain()
        self.guests[0].command(self.state); self.guests[0].retry()
        self.assertIsNone(self.guests[0].pending_control)
        self.drain(); self.assertEqual([], self.syncs[0])

    def test_stale_replayed_forged_and_other_owner_session_commands_are_rejected(self):
        self.drain(); self.host.set_mode('EVERYONE'); self.drain()
        self.guests[0].command(self.state); publication = self.guests[0].next_publication()
        self.assertTrue(self.host.receive_control(publication.frame))
        self.assertFalse(self.host.receive_control(publication.frame))
        forged = deepcopy(publication.frame); forged['snapshot']['playing'] = False
        self.assertFalse(self.host.receive_control(forged))
        self.clock[0] += 10_001
        self.assertFalse(self.host.receive_control(publication.frame))
        self.guests[0].command({**self.state, 'timestamp': self.now()})
        wrong = self.guests[0].next_publication()
        frame = self.guests[0].identity.sign_control({**wrong.frame, 'session': 'f'*32})
        self.assertFalse(self.host.receive_control(frame))

    def test_leaving_and_expired_owner_lease_never_replay_controls_or_sync(self):
        self.host.observe(self.state); self.drain(); self.host.set_mode('EVERYONE'); self.drain()
        self.clock[0] += 180_001; self.guests[0].tick()
        self.assertFalse(self.guests[0].can_control); self.assertEqual('OWNER_OFFLINE', self.guests[0].error)
        self.guests[0].leave(); self.guests[0].set_follow(True)
        self.assertFalse(self.guests[0].receive_state(self.host.identity.sign_state({**self.state, 'timestamp': self.now()})))
        self.assertIsNone(self.guests[0].next_publication()); self.assertEqual([], self.syncs[1])

    def test_presence_roster_is_bounded_and_pruned_grants_revoke(self):
        self.drain(); self.host.set_member(self.guests[0].identity.id, True)
        self.clock[0] += 300_001; self.host.tick()
        self.assertEqual({}, self.host.members); self.assertEqual(set(), self.host.selected)
        for i in range(50):
            identity = wire.RoomIdentity()
            hello = identity.sign_control(wire.control_frame(self.host.code, 'HELLO', identity.public_key, self.now(), name=str(i)))
            accepted = self.host.receive_control(hello)
            self.assertEqual(i < wire.MAX_MEMBERS, accepted)
        self.assertEqual(wire.MAX_MEMBERS, len(self.host.members))

    def test_transport_uses_separate_exact_topics_and_refuses_redirects_cookies_auth(self):
        calls = []
        class Response:
            status = 302
            def read(self, n): return b''
        class Connection:
            sock = None
            def __init__(self, host, **kwargs): calls.append((host, kwargs))
            def request(self, *args, **kwargs): calls.append((args, kwargs))
            def getresponse(self): return Response()
            def close(self): pass
        transport = NtfyTransport(Connection)
        self.assertEqual('/dkord-ABCDEFGHJK-controls/json?since=30s', transport.path('ABCDEFGHJK', True, True, since='30s'))
        publication = self.host.next_publication()
        with self.assertRaises(RoomTransportError): transport.publish(self.host.code, publication)
        self.assertEqual('ntfy.sh', calls[0][0]); self.assertIsNotNone(calls[0][1]['context'])
        headers = calls[1][1]['headers']
        self.assertNotIn('Cookie', headers); self.assertNotIn('Authorization', headers)
        with self.assertRaises(ValueError): transport.path('../evil')
        transport.cancel()

    def test_network_workers_cancel_bounded_reads_and_tag_generations(self):
        class Relay:
            def __init__(self): self.cancelled = threading.Event()
            def latest(self, code): return None
            def subscribe(self, code, controls, cursor):
                self.cancelled.wait(2)
                return iter(())
            def publish(self, code, publication): pass
            def cancel(self): self.cancelled.set()
        relay = Relay(); connection = RoomConnection(self.host.code, False, 81, relay)
        connection.start(); connection.send(self.host.next_publication())
        generation, kind, _ = connection.events.get(timeout=2)
        self.assertEqual((81, 'ack'), (generation, kind))
        connection.cancel(); self.assertTrue(connection.wait_closed())
        self.assertEqual(128, connection.events.maxsize); self.assertEqual(1, connection.outgoing.maxsize)


if __name__ == '__main__':
    unittest.main()
