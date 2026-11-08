"""Opt-in ntfy transport matching Android's two public, non-E2EE topics.

No cookies, account auth, redirects or configurable URL. Lines, queues and HTTP
responses are bounded. Cancelling shuts down in-flight sockets, including reads;
all worker output carries a generation so a left room cannot touch a new one.
"""
from __future__ import annotations
import http.client
import json
import queue
import socket
import ssl
import threading
from urllib.parse import urlencode

from . import room_protocol as wire


class RoomTransportError(IOError):
    def __init__(self, rate_limited=False):
        self.rate_limited = rate_limited
        super().__init__('Room relay rate limited' if rate_limited else 'Room relay connection failed')


class NtfyTransport:
    def __init__(self, connection_factory=None):
        self.cancelled = threading.Event()
        self._factory = connection_factory or http.client.HTTPSConnection
        self._connections = set()
        self._lock = threading.Lock()

    def cancel(self):
        self.cancelled.set()
        with self._lock:
            connections = tuple(self._connections)
        for connection in connections:
            sock = connection.sock
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()

    @staticmethod
    def path(code, controls=False, stream=False, **params):
        if wire.normalize_code(code) != code:
            raise ValueError('Invalid room code')
        result = '/dkord-' + code + ('-controls' if controls else '') + ('/json' if stream else '')
        return result + ('?' + urlencode(params) if params else '')

    def _execute(self, method, path, body=None):
        if self.cancelled.is_set():
            raise RoomTransportError()
        connection = self._factory('ntfy.sh', timeout=45, context=ssl.create_default_context())
        with self._lock:
            if self.cancelled.is_set():
                connection.close(); raise RoomTransportError()
            self._connections.add(connection)
        try:
            headers = {'User-Agent': 'Dkord (https://github.com/DeepuExplainsAi/dkord)', 'Accept-Encoding': 'identity'}
            if body is not None:
                headers['Content-Type'] = 'text/plain; charset=utf-8'
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                raise RoomTransportError(response.status == 429)
            return connection, response
        except Exception:
            self._close(connection)
            raise

    def _close(self, connection):
        with self._lock:
            self._connections.discard(connection)
        connection.close()

    def publish(self, code, publication):
        controls = publication.channel == 'controls'
        text = (wire.encode_control if controls else wire.encode_state)(publication.frame)
        if controls and publication.frame['room'] != code:
            raise ValueError('Room control destination mismatch')
        connection, response = self._execute('POST', self.path(code, controls), text.encode('utf-8'))
        try:
            # A relay response is an acknowledgement, not unbounded user content.
            if len(response.read(16_385)) > 16_384:
                raise RoomTransportError()
        finally:
            self._close(connection)

    def _events(self, code, controls, **params):
        connection, response = self._execute('GET', self.path(code, controls, True, **params))
        try:
            while not self.cancelled.is_set():
                line = response.readline(16_385)
                if not line:
                    return
                if len(line) > 16_384:
                    raise RoomTransportError()
                event = wire.relay_line(line.decode('utf-8').rstrip('\r\n'), controls)
                if event:
                    yield event
        finally:
            self._close(connection)

    def latest(self, code):
        last = None
        for count, event in enumerate(self._events(code, False, poll='1', since='12h')):
            if count >= 8192:
                raise RoomTransportError()
            last = event
        return last

    def subscribe(self, code, controls, cursor=None):
        if cursor is not None and (not isinstance(cursor, str) or not __import__('re').fullmatch(r'[A-Za-z0-9_-]{1,64}', cursor)):
            raise ValueError('Invalid relay cursor')
        return self._events(code, controls, since=cursor or ('30s' if controls else '12h'))


class RoomConnection:
    """Network-only workers. Never touches Qt, playback, SQLite or session state."""
    def __init__(self, code, owner, generation, transport=None, cursors=None):
        self.code, self.owner, self.generation = code, owner, generation
        self.transport = transport or NtfyTransport()
        self.cancelled = threading.Event()
        self.events = queue.Queue(maxsize=128)
        self.outgoing = queue.Queue(maxsize=1)
        self.cursors = dict(cursors or {})
        self._threads = []

    def _put(self, kind, value):
        while not self.cancelled.is_set():
            try:
                self.events.put((self.generation, kind, value), timeout=.2)
                return
            except queue.Full:
                continue

    def start(self):
        jobs = [lambda: self._receive(True), self._send]
        if not self.owner:
            jobs.append(lambda: self._receive(False))
        for job in jobs:
            thread = threading.Thread(target=job, name='Dkord room relay', daemon=True)
            self._threads.append(thread); thread.start()

    def _receive(self, controls):
        channel = 'controls' if controls else 'state'
        while not self.cancelled.is_set():
            try:
                if not controls and self.cursors.get(channel) is None:
                    latest = self.transport.latest(self.code)
                    if latest:
                        state, cursor = latest
                        self.cursors[channel] = cursor
                        self._put(channel, state)
                for state, cursor in self.transport.subscribe(self.code, controls, self.cursors.get(channel)):
                    if self.cancelled.is_set():
                        return
                    if cursor:
                        self.cursors[channel] = cursor
                    self._put(channel, state)
                raise RoomTransportError()
            except Exception as error:
                if self.cancelled.is_set():
                    return
                limited = isinstance(error, RoomTransportError) and error.rate_limited
                self._put('error', limited)
                if self.cancelled.wait(60 if limited else 5):
                    return
                self._put('reconnected', None)

    def _send(self):
        while not self.cancelled.is_set():
            try:
                publication = self.outgoing.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                self.transport.publish(self.code, publication)
                if not self.cancelled.is_set():
                    self._put('ack', publication)
            except Exception as error:
                limited = isinstance(error, RoomTransportError) and error.rate_limited
                self._put('send_error', limited)

    def send(self, publication):
        if not self.cancelled.is_set():
            self.outgoing.put_nowait(publication)

    def cancel(self):
        self.cancelled.set()
        self.transport.cancel()
        # The GUI never blocks waiting for a remote relay or thread.join().

    def wait_closed(self, timeout=2):
        import time
        deadline = time.monotonic() + timeout
        for thread in self._threads:
            thread.join(max(0, deadline - time.monotonic()))
        return all(not thread.is_alive() for thread in self._threads)
