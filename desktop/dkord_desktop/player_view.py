"""The phone full-player experience: artwork, timed lyrics and the actual queue."""
from __future__ import annotations
import time

from .qt import (sip, Qt, QTimer, QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                 QWidget, QListWidget, QListWidgetItem, QLabel, QPushButton, QSlider,
                 QAbstractItemView, QSize, QFont, QColor)
from .artwork import Cover
from .experience import text, palette
from .lyrics import index_at
from .models import clock
from .widgets import icon


def plain(value, style=None):
    widget = QLabel(value); widget.setTextFormat(Qt.TextFormat.PlainText); widget.setWordWrap(True)
    if style:
        widget.setObjectName(style)
    return widget


def action(caption, callback, primary=False):
    widget = QPushButton(caption); widget.clicked.connect(callback); widget.setIconSize(QSize(24,24))
    if not caption: widget.setProperty('iconOnly',True);widget.setFixedSize(44,44)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        widget.setProperty('primary', True)
    return widget


class FullPlayer(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle('dKORD'); self.setObjectName('full-player')
        self.setMinimumSize(380, 590); self.resize(min(980, max(420, owner.width()-100)), min(840, owner.height()))
        self.track_id = None; self.lyrics_task = None; self.lyrics_value = None; self.lyric_index = -2
        self.pause_scroll_until = 0
        outer = QVBoxLayout(self); outer.setContentsMargins(20, 12, 20, 16); outer.setSpacing(12)
        top = QHBoxLayout(); top.addWidget(action('⌄', self.hide)); top.addStretch()
        top.addWidget(plain(owner.tr('now_playing'))); top.addStretch()
        top.addWidget(action('⋮', self.more)); outer.addLayout(top)
        self.tabs = QTabWidget(); self.tabs.setObjectName('full-player-tabs')
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        art_page = QWidget(); art = QVBoxLayout(art_page); art.setContentsMargins(0, 8, 0, 8)
        self.cover = Cover(owner.artwork_cache, side=300)
        art.addStretch(); art.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter); art.addStretch()
        self.tabs.addTab(art_page, owner.tr('artwork') if owner.tr('artwork') != 'artwork' else 'Artwork')
        lyrics_page = QWidget(); lyrics_layout = QVBoxLayout(lyrics_page)
        self.lyrics_hint = plain(owner.tr('loading'), 'muted'); lyrics_layout.addWidget(self.lyrics_hint)
        self.lyrics_view = QListWidget(); self.lyrics_view.setObjectName('synced-lyrics')
        self.lyrics_view.setWordWrap(True); self.lyrics_view.itemClicked.connect(self.seek_lyric)
        self.lyrics_view.verticalScrollBar().sliderPressed.connect(self.pause_scroll)
        lyrics_layout.addWidget(self.lyrics_view, 1)
        self.retry_lyrics = action(owner.tr('retry'), self.load_lyrics); lyrics_layout.addWidget(self.retry_lyrics); self.retry_lyrics.hide()
        self.tabs.addTab(lyrics_page, owner.tr('lyrics'))
        queue_page = QWidget(); queue_layout = QVBoxLayout(queue_page)
        self.queue_view = QListWidget(); self.queue_view.setObjectName('full-player-queue')
        self.queue_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.queue_view.model().rowsMoved.connect(lambda *args: QTimer.singleShot(0, self.reorder_queue))
        self.queue_view.itemDoubleClicked.connect(lambda item: owner.play_index(self.queue_view.row(item)))
        self.queue_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_view.customContextMenuRequested.connect(lambda point: owner.queue_menu(point, self.queue_view))
        queue_layout.addWidget(self.queue_view)
        self.tabs.addTab(queue_page, owner.tr('queue'))
        self.tabs.currentChanged.connect(lambda index: self.load_lyrics() if index == 1 and self.lyrics_value is None else None)
        outer.addWidget(self.tabs, 1)
        self.title = plain('', 'player-title'); self.title.setStyleSheet('font-size:23px;font-weight:700;')
        self.artist = plain('', 'muted'); outer.addWidget(self.title); outer.addWidget(self.artist)
        actions = QHBoxLayout()
        for caption, key, callback in (
            ('♡', 'like', self.like), ('↓', 'download', lambda: owner.choose_download([owner.current()]) if owner.current() else None),
            ('↗', 'share', self.share), ('♬', 'listen_together', lambda: (self.hide(), owner.navigate('Listen Together'))),
            ('▸', 'play_video', lambda: owner.show_video() if owner.current() else None),
        ):
            widget = action('', callback); widget.setIcon(icon({'like':'favorite_border','download':'file_download','share':'share','listen_together':'groups','play_video':'videocam'}[key])); widget.setFixedWidth(44); widget.setToolTip(owner.tr(key)); widget.setAccessibleName(owner.tr(key)); actions.addWidget(widget)
            if key == 'like': self.like_button = widget
            if key == 'play_video': self.video_button = widget
        actions.addStretch(); outer.addLayout(actions)
        transport = QHBoxLayout(); transport.addStretch()
        for key, symbol, callback in (
            ('previous', 'skip_previous', lambda: owner.next_track(-1)),
            ('play', 'play_arrow', owner.toggle), ('next', 'skip_next', lambda: owner.next_track(1)),
        ):
            widget = action('', callback); side=72 if key=='play' else 56; widget.setFixedSize(side,side); widget.setIcon(icon(symbol,'#000000' if key=='play' else palette(owner.effective_theme())['onSurface'])); widget.setIconSize(QSize(40,40) if key=='play' else QSize(36,36)); widget.setAccessibleName(owner.tr(key))
            if key == 'play': self.play_toggle = widget; widget.setObjectName('full-play-toggle')
            transport.addWidget(widget)
        transport.addStretch(); outer.addLayout(transport)
        # These are the same functional controls as the old client, not dead copies.
        outer.addWidget(owner.player_controls)
        self.timer = QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.refresh)
        self.refresh(force=True)

    def showEvent(self, event):
        self.timer.start(); self.refresh(force=True)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop(); super().hideEvent(event)

    def resizeEvent(self, event):
        side = max(140, min(360, self.width()-64, self.height()-410))
        if hasattr(self, 'cover'):
            self.cover.setFixedSize(side, side)
        super().resizeEvent(event)

    def more(self):
        if self.owner.current():
            self.owner.track_menu(self.owner.current(), self.mapToGlobal(self.rect().topRight()))

    def share(self):
        from .qt import QApplication
        track = self.owner.current()
        if track and not track.local:
            QApplication.clipboard().setText('https://www.youtube.com/watch?v='+track.id)
            self.owner.notify(self.owner.tr('copied'))

    def like(self):
        track = self.owner.current()
        if track:
            liked = any(t.id == track.id for t in self.owner.store.library('liked'))
            self.owner.store.like(track, not liked); self.refresh(force=True)

    def refresh(self, force=False):
        track = self.owner.current()
        if not track:
            return
        self.play_toggle.setIcon(icon('pause' if self.owner.desired_playing else 'play_arrow', '#000000', 40))
        self.play_toggle.setAccessibleName(self.owner.tr('pause' if self.owner.desired_playing else 'play'))
        changed = track.id != self.track_id
        if changed:
            self.track_id = track.id; self.lyrics_value = None; self.lyric_index = -2
            self.lyrics_view.clear(); self.lyrics_hint.setText(self.owner.tr('loading'))
            self.retry_lyrics.hide()
            if self.lyrics_task:
                self.lyrics_task.cancel.set()
            self.cover.set_url(track.thumbnail)
            if self.tabs.currentIndex() == 1:
                self.load_lyrics()
        if changed or force:
            self.title.setText(track.title); self.artist.setText(track.artist)
            liked = any(t.id == track.id for t in self.owner.store.library('liked'))
            self.like_button.setText(''); self.like_button.setIcon(icon('favorite' if liked else 'favorite_border', palette(self.owner.effective_theme())['primary' if liked else 'onSurface']))
            self.video_button.setEnabled(not track.local and self.owner.store.setting('video_enabled', False))
            self.refresh_queue()
        if self.lyrics_value and self.lyrics_value.synced:
            index = index_at(self.lyrics_value.synced, self.owner.player.position())
            if index != self.lyric_index:
                self.lyric_index = index
                p = palette(self.owner.effective_theme())
                for row in range(self.lyrics_view.count()):
                    item = self.lyrics_view.item(row); font = item.font(); font.setPointSize(16 if row == index else 14); font.setBold(row == index)
                    item.setFont(font); item.setForeground(QColor(p['onSurface'] if row == index else p['onSurfaceVariant']))
                if index >= 0 and time.monotonic() >= self.pause_scroll_until:
                    self.lyrics_view.scrollToItem(self.lyrics_view.item(index), QAbstractItemView.ScrollHint.PositionAtCenter)

    def refresh_queue(self):
        self.queue_view.clear()
        for index, track in enumerate(self.owner.queue):
            item = QListWidgetItem(('▶  ' if index == self.owner.index else '') + track.title+'\n'+track.artist)
            item.setData(Qt.ItemDataRole.UserRole, index); item.setSizeHint(QSize(240, 64)); self.queue_view.addItem(item)

    def reorder_queue(self):
        order = [self.queue_view.item(row).data(Qt.ItemDataRole.UserRole) for row in range(self.queue_view.count())]
        if sorted(order) != list(range(len(self.owner.queue))) or order == list(range(len(order))):
            return
        old = self.owner.queue
        self.owner.queue = [old[index] for index in order]; self.owner.index = order.index(self.owner.index)
        self.owner.revision += 1; self.owner.refresh_queue(); self.owner.save_session(); self.owner.room_local_intent()

    def pause_scroll(self):
        self.pause_scroll_until = time.monotonic()+8

    def seek_lyric(self, item):
        value = item.data(Qt.ItemDataRole.UserRole)
        if type(value) is int:
            self.owner.user_seek(value)

    def load_lyrics(self):
        track = self.owner.current()
        if not track:
            return
        if self.lyrics_task:
            self.lyrics_task.cancel.set()
        owner_id = track.id
        self.lyrics_hint.setText(self.owner.tr('loading')); self.retry_lyrics.hide(); self.lyrics_view.clear()
        def ready(value):
            if sip.isdeleted(self) or self.owner.current() is None or self.owner.current().id != owner_id:
                return
            self.lyrics_value = value; self.lyric_index = -2
            self.lyrics_hint.setText('' if value else self.owner.tr('no_lyrics'))
            self.lyrics_view.clear()
            if value:
                if value.synced:
                    for line in value.synced:
                        item = QListWidgetItem(line.text or '♪'); item.setData(Qt.ItemDataRole.UserRole, line.time_ms)
                        self.lyrics_view.addItem(item)
                elif value.plain:
                    for line in value.plain.splitlines():
                        self.lyrics_view.addItem(QListWidgetItem(line))
            self.refresh()
        def failed(_):
            if not sip.isdeleted(self) and self.owner.current() and self.owner.current().id == owner_id:
                self.lyrics_hint.setText(self.owner.tr('err_network')); self.retry_lyrics.show()
        self.lyrics_task = self.owner.run(lambda cancel, progress: self.owner.lyrics_repository.load(track, cancel), ready, failed=failed)
