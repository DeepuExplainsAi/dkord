"""Global Listen Together hub and Qt adapter; rooms never belong to a song page."""
from __future__ import annotations
import queue
import time

from .qt import (sip, Qt, QObject, QTimer, pyqtSignal, QWidget, QVBoxLayout, QHBoxLayout,
                 QLineEdit, QPushButton, QLabel, QCheckBox, QComboBox, QFrame, QApplication)
from . import room_protocol as wire
from .rooms import RoomSession
from .room_transport import RoomConnection


def plain(value='', style=None):
    result = QLabel(value); result.setTextFormat(Qt.TextFormat.PlainText); result.setWordWrap(True)
    if style:
        result.setObjectName(style)
    return result


def action(caption, callback, primary=False):
    result = QPushButton(caption); result.clicked.connect(callback)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        result.setProperty('primary', True)
    return result


class RoomBridge(QObject):
    changed = pyqtSignal()

    def __init__(self, window, connection_factory=None):
        super().__init__(window)
        self.window = window; self.session = None; self.connection = None
        self.connection_factory = connection_factory or RoomConnection
        self.generation = 0; self.sending = False; self.retry_at = 0
        self.applying = False; self.remote_epoch = None
        self.timer = QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.pump); self.timer.start()

    def snapshot(self):
        window = self.window
        position = window.player.position() if window.loaded_epoch == window.epoch else window.pending_seek
        return wire.snapshot(window.queue, window.index, position, window.desired_playing, time.time_ns()//1_000_000)

    def start(self, owner, code=None, name=''):
        # Invalid input must not tear down a working session.
        if not owner and wire.normalize_code(code) is None:
            raise ValueError(self.window.tr('room_invalid_code'))
        self.leave()
        generation = self.generation
        self.session = RoomSession(owner, code, name, on_sync=lambda frame: self.apply_frame(frame, generation))
        self.connection = self.connection_factory(self.session.code, owner, generation)
        self.connection.start(); self.pump(); self.changed.emit()

    def retry(self):
        if not self.session:
            return
        cursors = dict(self.connection.cursors) if self.connection else {}
        if self.connection:
            self.connection.cancel()
        self.generation += 1; generation = self.generation
        self.session.on_sync = lambda frame: self.apply_frame(frame, generation)
        self.session.retry(); self.sending = False; self.retry_at = 0
        self.connection = self.connection_factory(self.session.code, self.session.owner, generation, cursors=cursors)
        self.connection.start(); self.changed.emit()

    def leave(self):
        self.generation += 1
        if self.session:
            self.session.leave()
        if self.connection:
            self.connection.cancel()
        self.session = None; self.connection = None; self.sending = False; self.retry_at = 0
        self.cancel_remote_prepare()
        self.changed.emit()

    def cancel_remote_prepare(self):
        window = self.window
        if self.remote_epoch is not None and self.remote_epoch == window.epoch and window.loaded_epoch != window.epoch:
            # Do not stop ordinary local audio, but a left room cannot start a late resolver.
            window.epoch += 1; window.desired_playing = False
        self.remote_epoch = None

    def user_intent(self):
        if self.session and not self.applying:
            self.session.command(self.snapshot()); self.changed.emit()

    def set_follow(self, follow):
        if self.session:
            self.session.set_follow(follow)
            if not follow:
                self.cancel_remote_prepare()
            self.changed.emit()

    def sync_now(self):
        if self.session:
            self.session.sync_now(); self.changed.emit()

    def apply_frame(self, frame, generation):
        if generation != self.generation or not self.session or not self.session.active:
            return
        window = self.window
        tracks = wire.state_tracks(frame)
        position = wire.synchronized_position(frame, time.time_ns()//1_000_000)
        current = window.current()
        same_prefix = [t.id for t in window.queue[window.index:window.index+len(tracks)]] == [t.id for t in tracks]
        self.applying = True
        try:
            if current and current.id == tracks[0].id and same_prefix and window.loaded_epoch == window.epoch:
                if abs(window.player.position()-position) > 1500:
                    window.user_seek(position, user=False)
                window.desired_playing = frame['playing']
                (window.player.play if frame['playing'] else window.player.pause)()
                window.save_session()
            else:
                window.queue = tracks; window.index = 0; window.revision += 1
                window.play_index(0, position, user=False, playing=frame['playing'])
                self.remote_epoch = window.epoch
        except Exception:
            self.session.error = 'PLAYBACK'
        finally:
            self.applying = False

    def pump(self):
        session, connection = self.session, self.connection
        if not session or not connection or self.window.closing:
            return
        for _ in range(32):
            try:
                generation, kind, value = connection.events.get_nowait()
            except queue.Empty:
                break
            if generation != self.generation:
                continue
            if kind == 'controls':
                session.receive_control(value)
            elif kind == 'state':
                session.receive_state(value)
            elif kind == 'ack':
                session.acknowledged(value); self.sending = False
            elif kind in ('error', 'send_error'):
                session.connection_error(value)
                if kind == 'send_error':
                    self.sending = False; self.retry_at = time.monotonic() + (60 if value else 5)
            elif kind == 'reconnected':
                session.retry()  # stale unsent co-host clicks are not carried across a reconnect
        session.observe(self.snapshot()); session.tick()
        if not self.sending and time.monotonic() >= self.retry_at:
            publication = session.next_publication()
            if publication:
                try:
                    connection.send(publication); self.sending = True
                except queue.Full:
                    pass
        self.changed.emit()

    def close(self):
        self.timer.stop(); self.leave()


class RoomPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.bridge = window, window.rooms
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(16)
        self.roster_key = None; self.session_key = None; self.member_checks = {}
        self.layout.addWidget(plain(window.tr('room_anywhere_hint'), 'muted'))
        self.idle = QWidget(); idle = QVBoxLayout(self.idle); idle.setContentsMargins(0, 0, 0, 0); idle.setSpacing(12)
        idle.addWidget(plain(window.tr('room_how_to'), 'pageTitle'))
        for key in ('room_step_create', 'room_step_share', 'room_step_join', 'room_step_sync'):
            idle.addWidget(plain(window.tr(key)))
        self.name = QLineEdit(); self.name.setMaxLength(48); self.name.setPlaceholderText(window.tr('room_display_name')); idle.addWidget(self.name)
        create = action(window.tr('room_create'), lambda: self.start(True), True); create.setObjectName('room-create'); idle.addWidget(create)
        self.code = QLineEdit(); self.code.setMaxLength(32); self.code.setPlaceholderText(window.tr('room_join_hint')); self.code.setObjectName('room-code'); idle.addWidget(self.code)
        self.code.returnPressed.connect(lambda: self.start(False))
        join = action(window.tr('room_join'), lambda: self.start(False)); join.setObjectName('room-join'); idle.addWidget(join)
        self.input_error = plain('', 'muted'); idle.addWidget(self.input_error)
        self.layout.addWidget(self.idle)
        self.active = QWidget(); active = QVBoxLayout(self.active); active.setContentsMargins(0, 0, 0, 0); active.setSpacing(12)
        self.role = plain('', 'eyebrow'); active.addWidget(self.role)
        self.room_code = plain('', 'pageTitle'); self.room_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); active.addWidget(self.room_code)
        self.status = plain('', 'muted'); active.addWidget(self.status)
        copy = action(window.tr('room_copy_code'), self.copy_code); copy.setObjectName('room-copy-code'); active.addWidget(copy)
        self.song = plain(''); active.addWidget(self.song)
        row = QHBoxLayout()
        row.addWidget(action(window.tr('room_open_player'), window.show_full_player))
        choose = action(window.tr('room_choose_music'), lambda: window.navigate('Library')); choose.setObjectName('room-choose-music'); row.addWidget(choose)
        active.addLayout(row)
        self.guest = QWidget(); guest = QVBoxLayout(self.guest); guest.setContentsMargins(0, 0, 0, 0)
        self.sync = action(window.tr('room_sync_play'), self.bridge.sync_now, True); self.sync.setObjectName('room-sync'); guest.addWidget(self.sync)
        self.follow = QCheckBox(window.tr('room_follow')); self.follow.setObjectName('room-follow'); self.follow.toggled.connect(self.bridge.set_follow); guest.addWidget(self.follow)
        self.guest_access = plain('', 'muted'); guest.addWidget(self.guest_access); active.addWidget(self.guest)
        self.permissions = QWidget(); permissions = QVBoxLayout(self.permissions); permissions.setContentsMargins(0, 0, 0, 0)
        permissions.addWidget(plain(window.tr('room_controls_title'), 'pageTitle'))
        permissions.addWidget(plain(window.tr('room_controls_hint'), 'muted'))
        self.mode = QComboBox(); self.mode.setObjectName('room-control-mode')
        for mode, key in zip(wire.MODES, ('room_controls_host_only', 'room_controls_selected', 'room_controls_everyone')):
            self.mode.addItem(window.tr(key), mode)
        self.mode.currentIndexChanged.connect(self.set_mode); permissions.addWidget(self.mode)
        self.roster = QWidget(); self.roster_layout = QVBoxLayout(self.roster); self.roster_layout.setContentsMargins(0, 0, 0, 0); permissions.addWidget(self.roster)
        active.addWidget(self.permissions)
        self.member_id = plain('', 'muted'); active.addWidget(self.member_id)
        active.addWidget(plain(window.tr('room_controls_consent'), 'muted'))
        self.error = plain('', 'muted'); active.addWidget(self.error)
        active.addWidget(action(window.tr('retry'), self.bridge.retry))
        leave = action(window.tr('room_leave'), self.bridge.leave); leave.setObjectName('room-leave'); active.addWidget(leave)
        self.layout.addWidget(self.active)
        self.layout.addWidget(plain(window.tr('room_controls_privacy'), 'muted')); self.layout.addStretch()
        self.bridge.changed.connect(self.refresh); self.refresh()

    def start(self, owner):
        try:
            self.bridge.start(owner, self.code.text(), self.name.text()); self.input_error.setText('')
        except ValueError as error:
            self.input_error.setText(str(error))

    def copy_code(self):
        if self.bridge.session:
            QApplication.clipboard().setText(self.bridge.session.code); self.window.notify(self.window.tr('room_code_copied'))

    def set_mode(self, index):
        session = self.bridge.session
        if session and session.owner:
            session.set_mode(self.mode.itemData(index)); self.refresh()

    def refresh(self):
        if sip.isdeleted(self):
            return
        session = self.bridge.session
        self.idle.setVisible(session is None); self.active.setVisible(session is not None)
        if session is None:
            return
        owner = session.owner
        self.role.setText(self.window.tr('room_host' if owner else 'room_cohost' if session.can_control else 'room_guest'))
        self.room_code.setText(session.code)
        status = 'room_following' if session.follow and session.has_synced else 'room_ready' if session.connected else 'room_connecting'
        self.status.setText(self.window.tr(status))
        self.song.setText((session.host['title']+'\n'+session.host['artist']) if session.host else self.window.tr('room_waiting'))
        self.guest.setVisible(not owner); self.permissions.setVisible(owner)
        self.sync.setEnabled(session.host is not None)
        self.follow.blockSignals(True); self.follow.setChecked(session.follow); self.follow.blockSignals(False)
        self.guest_access.setText(self.window.tr('room_cohost_controls' if session.can_control else 'room_controls_listen_only' if session.owner_known else 'room_controls_pending'))
        self.mode.blockSignals(True); self.mode.setCurrentIndex(wire.MODES.index(session.mode)); self.mode.blockSignals(False)
        self.member_id.setText(self.window.tr('room_controls_your_id', session.identity.id[:8]))
        errors = {'NETWORK': 'room_controls_network', 'RATE_LIMIT': 'room_controls_rate_limit', 'LOCAL_AUDIO': 'room_controls_local_audio',
                  'OWNER_OFFLINE': 'room_controls_owner_offline', 'PLAYBACK': 'room_playback_error'}
        self.error.setText(self.window.tr(errors[session.error]) if session.error in errors else '')
        key = (id(session), session.mode, tuple(sorted(session.selected)), tuple((id, value['name']) for id, value in session.members.items()))
        if key != self.roster_key:
            self.roster_key = key
            while self.roster_layout.count():
                item = self.roster_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.member_checks = {}
            if not session.members:
                self.roster_layout.addWidget(plain(self.window.tr('room_controls_empty'), 'muted'))
            for member, info in session.members.items():
                box = QCheckBox(info['name']+' · '+member[:8]); box.setObjectName('room-member-'+member)
                box.setChecked(session.allowed(member)); box.setEnabled(session.mode != 'EVERYONE')
                box.toggled.connect(lambda allow, member=member: self.grant(member, allow))
                self.member_checks[member] = box; self.roster_layout.addWidget(box)

    def grant(self, member, allow):
        if self.bridge.session:
            self.bridge.session.set_member(member, allow); self.refresh()
