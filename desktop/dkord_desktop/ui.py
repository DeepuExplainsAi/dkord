from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path
import sys
from uuid import uuid4

from PyQt6 import sip
from PyQt6.QtCore import Qt, QThreadPool, QTimer, QUrl, QSize
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStyle, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from . import __version__
from .media import MediaLibrary, check_cancel
from .models import Track, clock, milliseconds
from .provider import Entry, Provider
from .store import Store
from .streaming import AudioProxy
from .tasks import Task
from .updates import Updater

DARK = """
QWidget { background:#101013; color:#eeeeF1; font-family:'Segoe UI','Noto Sans','Arial'; font-size:14px; }
QMainWindow,QDialog { background:#101013; } QFrame#sidebar { background:#17171b; border-right:1px solid #29292f; }
QLabel#brand { font-size:30px; font-weight:800; } QLabel#eyebrow { color:#ff6268; font-size:11px; font-weight:700; }
QLabel#pageTitle { font-size:32px; font-weight:750; } QLabel#muted { color:#a3a3b0; }
QFrame#player { background:#1b1b20; border-top:1px solid #33333b; border-radius:0; }
QPushButton { background:#24242b; padding:9px 14px; border:1px solid #35353f; border-radius:8px; }
QPushButton:hover { background:#34343f; } QPushButton:pressed { background:#454550; }
QPushButton:disabled { color:#686875; border-color:#28282e; } QPushButton[primary="true"] { background:#ed343e; color:white; border-color:#ed343e; font-weight:700; }
QPushButton#nav { text-align:left; padding:12px; background:transparent; border:0; } QPushButton#nav:checked { background:#382026; color:#ff777b; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#202027; border:1px solid #3c3c46; border-radius:8px; padding:9px; selection-background-color:#be2734; }
QLineEdit:focus { border-color:#f44a52; } QComboBox::drop-down { border:0; width:24px; }
QTableWidget,QListWidget,QTextEdit { background:#151519; alternate-background-color:#1b1b20; border:1px solid #2d2d34; border-radius:10px; selection-background-color:#44252b; }
QTableWidget::item { padding:8px; border-bottom:1px solid #25252c; } QHeaderView::section { background:#1b1b21; color:#a4a4b2; border:0; padding:10px; }
QScrollBar:vertical { background:#151519; width:9px; } QScrollBar::handle:vertical { background:#454550; border-radius:4px; min-height:30px; }
QSlider::groove:horizontal { height:4px; background:#43434c; border-radius:2px; } QSlider::handle:horizontal { background:#ff535b; width:12px; margin:-4px 0; border-radius:6px; }
QSlider::sub-page:horizontal { background:#ed343e; } QDockWidget::title { background:#17171c; padding:12px; font-weight:700; }
QToolTip { background:#292932; color:#fff; border:1px solid #444; } QMenu { border:1px solid #454550; padding:5px; } QMenu::item { padding:8px 20px; } QMenu::item:selected { background:#44252b; }
"""


def label(text: str, style: str | None = None) -> QLabel:
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(True)
    if style:
        result.setObjectName(style)
    return result


def button(text: str, action, primary=False) -> QPushButton:
    result = QPushButton(text)
    result.clicked.connect(action)
    if primary:
        result.setProperty("primary", True)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result


class MainWindow(QMainWindow):
    def __init__(self, store: Store, provider: Provider | None = None, autoload=True):
        super().__init__()
        self.store, self.provider = store, provider or Provider()
        self.library = MediaLibrary(store, self.provider)
        self.library.gc_sources()
        self.updater = Updater(store.root / "updates")
        self.tasks: set[Task] = set()
        self.pool = QThreadPool(self); self.pool.setMaxThreadCount(4)
        self.download_pool = QThreadPool(self); self.download_pool.setMaxThreadCount(1)
        self.download_running = False
        self.closing = False
        self.epoch = 0
        self.revision = 0
        self.loaded_epoch = -1
        self.pending_seek = 0
        self.desired_playing = False
        self.search_epoch = 0
        self.search_limit = 20
        self.search_task = None
        self.more_task = None
        self.more_epoch = 0
        self.route_epoch = 0
        self.studio_task = None
        self.studio_id = None
        self.page = "Home"
        self.queue: list[Track] = []
        self.index = 0
        self.sleep_at = None
        self.last_history = 0.0
        self.entries: list[Entry] = []
        self.proxy = AudioProxy()
        self.audio = QAudioOutput(self)
        self.audio.setVolume(float(store.setting("volume", .8)))
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.playback_changed)
        self.player.mediaStatusChanged.connect(self.media_status)
        self.player.errorOccurred.connect(lambda error, text: self.notify("Playback unavailable. " + text) if error != QMediaPlayer.Error.NoError and self.loaded_epoch == self.epoch else None)
        self.preview_player = QMediaPlayer(self); self.preview_audio = QAudioOutput(self)
        self.preview_player.setAudioOutput(self.preview_audio)
        self.preview_end = None
        self.preview_player.positionChanged.connect(lambda position: self.preview_player.stop() if self.preview_end and position >= self.preview_end else None)
        self.setWindowTitle(f"Dkord — Music & Mashup Studio · {__version__} preview")
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        self.setWindowIcon(QIcon(str(root / "assets" / "dkord.svg")))
        self.resize(1360, 850); self.setMinimumSize(940, 640)
        container = QWidget(); self.setCentralWidget(container)
        outer = QVBoxLayout(container); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        body = QWidget(); row = QHBoxLayout(body); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
        outer.addWidget(body, 1)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(212)
        nav = QVBoxLayout(sidebar); nav.setContentsMargins(20, 28, 20, 22); nav.setSpacing(8)
        nav.addWidget(label("Dkord", "brand")); nav.addWidget(label("YOUR MUSIC. YOUR SPACE.", "eyebrow")); nav.addSpacing(28)
        self.nav_buttons = {}
        for name in ("Home", "Search", "Listen Again", "Liked songs", "Playlists", "Downloads", "Mashup Studio"):
            b = button(name, lambda checked=False, name=name: self.navigate(name)); b.setObjectName("nav"); b.setCheckable(True)
            self.nav_buttons[name] = b; nav.addWidget(b)
        nav.addStretch(1)
        nav.addWidget(button("Settings & updates", lambda: self.navigate("Settings")))
        nav.addWidget(button("About Dkord", self.about))
        nav.addWidget(label("DESKTOP PREVIEW · LOCAL FIRST", "muted"))
        row.addWidget(sidebar)
        middle = QWidget(); center = QVBoxLayout(middle); center.setContentsMargins(30, 24, 30, 20); center.setSpacing(16)
        search_row = QHBoxLayout()
        self.query = QLineEdit(); self.query.setObjectName("global-search"); self.query.setPlaceholderText("Search music, artists, Choliwood or a song version…")
        self.query.returnPressed.connect(self.search)
        self.scope = QComboBox(); self.scope.addItems(list(Provider.scopes)); self.scope.setMinimumWidth(132)
        search_row.addWidget(self.query, 1); search_row.addWidget(self.scope); search_row.addWidget(button("Search", self.search, True))
        center.addLayout(search_row)
        self.heading = label("Home", "pageTitle"); center.addWidget(self.heading)
        self.subtitle = label("Discover songs. Keep them close. Make something your own.", "muted"); center.addWidget(self.subtitle)
        self.content = QWidget(); self.content_layout = QVBoxLayout(self.content); self.content_layout.setContentsMargins(0, 0, 0, 0)
        center.addWidget(self.content, 1); row.addWidget(middle, 1)
        self.build_player(outer)
        self.queue_dock = QDockWidget("Up next", self); self.queue_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.queue_list = QListWidget(); self.queue_list.itemDoubleClicked.connect(lambda item: self.play_index(self.queue_list.row(item)))
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.queue_menu)
        self.queue_dock.setWidget(self.queue_list); self.queue_dock.setMinimumWidth(245)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.queue_dock)
        self.statusBar().showMessage("Ready · no account, subscription or custom backend required")
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.query.setFocus)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.navigate("Settings"))
        QShortcut(QKeySequence("Ctrl+J"), self, activated=lambda: self.navigate("Downloads"))
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1000)
        self.apply_theme(store.setting("theme", "dark"))
        self.restore()
        self.navigate("Home", fetch=autoload)
        if autoload:
            self.drain_downloads()

    def run(self, call, done=None, progress=None, failed=None, download=False, finished=None) -> Task:
        task = Task(call); self.tasks.add(task)
        task.signals.result.connect(lambda result: done(result) if done and not self.closing else None)
        task.signals.error.connect(lambda text: (failed or self.notify)(text) if not self.closing else None)
        if progress:
            task.signals.progress.connect(lambda value: progress(value) if not self.closing else None)
        def finish():
            self.tasks.discard(task)
            if finished and not self.closing:
                finished()
        task.signals.finished.connect(finish)
        (self.download_pool if download else self.pool).start(task)
        return task

    def notify(self, text):
        self.statusBar().showMessage(str(text), 12000)

    def apply_theme(self, theme):
        self.store.set_setting("theme", theme)
        if theme == "light":
            self.setStyleSheet(DARK.replace("#101013", "#f6f6f9").replace("#eeeeF1", "#16161c").replace("#17171b", "#eaeaef").replace("#151519", "#ffffff").replace("#1b1b20", "#f1f1f5").replace("#202027", "#ffffff").replace("#24242b", "#e8e8ef").replace("#17171c", "#eaeaef").replace("#1b1b21", "#e8e8ef").replace("#a3a3b0", "#626270"))
        else:
            self.setStyleSheet(DARK.replace("#101013", "#000000") if theme == "amoled" else DARK)

    def reset_content(self, title, subtitle=""):
        self.heading.setText(title); self.subtitle.setText(subtitle)
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.table = None

    def navigate(self, page, fetch=True):
        self.route_epoch += 1
        self.page = page
        for name, b in self.nav_buttons.items():
            b.setChecked(name == page)
        if page == "Home":
            self.reset_content("Good music. Great possibilities.", "A music-first home, powered by the real YouTube Music catalogue.")
            self.content_layout.addWidget(label("Loading music…" if fetch else "Search a song to begin. No demo catalogue or bundled music."))
            self.content_layout.addWidget(button("Explore Hindi & Choliwood", lambda: self.search_for("Choliwood songs")))
            if fetch:
                epoch = self.search_epoch = self.search_epoch + 1
                self.run(lambda event, progress: self.provider.home(), lambda entries: self.show_entries(entries, "Home") if self.page == "Home" and epoch == self.search_epoch else None)
        elif page == "Search":
            self.reset_content("Find your next favourite", "Songs is the default. Other scopes stay explicit; typing does not start playback.")
            self.saved_queries()
        elif page in {"Listen Again", "Liked songs"}:
            self.reset_content(page, "Your local listening library. No network is needed to browse it.")
            toolbar = QWidget(); layout = QHBoxLayout(toolbar); layout.setContentsMargins(0, 0, 0, 0)
            local = QLineEdit(); local.setPlaceholderText("Filter this local library…"); layout.addWidget(local, 1)
            if page == "Listen Again":
                layout.addWidget(button("Resume saved queue", self.resume))
                layout.addWidget(button("Clear history", self.clear_history))
            self.content_layout.addWidget(toolbar)
            songs = self.store.library("history" if page == "Listen Again" else "liked")
            self.song_table([Entry("song", t.id, t.title, t.artist, t) for t in songs])
            local.textChanged.connect(lambda q: self.filter_table(q))
        elif page == "Playlists":
            self.playlists_page()
        elif page == "Downloads":
            self.downloads_page()
        elif page == "Mashup Studio":
            self.studio_page()
        elif page == "Settings":
            self.settings_page()

    def search_for(self, text):
        self.query.setText(text); self.scope.setCurrentText("Songs"); self.search()

    def search(self):
        query = " ".join(self.query.text().split())
        if not query:
            self.navigate("Search"); return
        scope = self.scope.currentText()
        self.store.remember_query(query, scope)
        self.route_epoch += 1
        self.page = "Search"; self.search_limit = 20
        if self.more_task:
            self.more_task.cancel.set()
            self.more_task = None
        self.search_epoch += 1; owner = self.search_epoch
        if self.search_task:
            self.search_task.cancel.set()
        self.reset_content(query, f"{scope} · results keep provider order; different uploads remain separate")
        self.content_layout.addWidget(label("Searching the real catalogue…"))
        self.search_task = self.run(lambda event, progress: self.provider.search(query, scope, 20),
            lambda entries: self.show_entries(entries, "Search", query, scope) if owner == self.search_epoch and self.page == "Search" else None)

    def show_entries(self, entries, page, query=None, scope=None):
        self.entries = entries
        self.reset_content(query or "Discover music", (scope + " · " if scope else "") + "Select one song to play it. Play all is a separate, explicit queue action.")
        controls = QWidget(); row = QHBoxLayout(controls); row.setContentsMargins(0, 0, 0, 0)
        tracks = [e.track for e in entries if e.track]
        row.addWidget(button("Play all shown", lambda: self.play_queue(tracks)))
        row.addWidget(button("Download selected", self.download_selected))
        row.addStretch(1)
        if query and self.search_limit < 200:
            row.addWidget(button("Load more", lambda: self.more(query, scope)))
        self.content_layout.addWidget(controls)
        self.song_table(entries)
        if not entries:
            self.content_layout.addWidget(label("No results were returned. Try another search or an explicit broader scope.", "muted"))

    def more(self, query, scope):
        if self.more_task is not None:
            return
        self.more_epoch += 1
        request = self.more_epoch
        owner = self.search_epoch
        limit = min(200, self.search_limit + 20)
        self.notify("Loading more… Existing results are kept if this page fails.")
        def ready(entries):
            if owner == self.search_epoch and self.page == "Search":
                self.search_limit = limit
                self.show_entries(entries, "Search", query, scope)
        def finished():
            if request == self.more_epoch:
                self.more_task = None
        self.more_task = self.run(lambda event, progress: self.provider.search(query, scope, limit), ready, finished=finished)

    def saved_queries(self):
        listing = QListWidget(); listing.setObjectName("search-history")
        for q in self.store.queries():
            item = QListWidgetItem(("★ " if q["pinned"] else "") + q["query"] + "  ·  " + q["scope"])
            item.setData(Qt.ItemDataRole.UserRole, q); listing.addItem(item)
        listing.itemDoubleClicked.connect(lambda item: self.repeat_query(item.data(Qt.ItemDataRole.UserRole)))
        listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def menu(point):
            item = listing.itemAt(point)
            if not item: return
            q = item.data(Qt.ItemDataRole.UserRole); m = QMenu(self)
            m.addAction("Edit query", lambda: (self.query.setText(q["query"]), self.scope.setCurrentText(q["scope"]), self.query.setFocus()))
            def pin():
                try: self.store.pin_query(q["query"], q["scope"], not q["pinned"]); self.navigate("Search")
                except ValueError as e: self.notify(str(e))
            m.addAction("Unpin" if q["pinned"] else "Pin search", pin)
            m.addAction("Remove search", lambda: (self.store.forget_query(q["query"], q["scope"]), self.navigate("Search")))
            m.exec(listing.mapToGlobal(point))
        listing.customContextMenuRequested.connect(menu)
        self.content_layout.addWidget(label("Recent & pinned searches", "muted")); self.content_layout.addWidget(listing, 1)

    def repeat_query(self, query):
        self.query.setText(query["query"]); self.scope.setCurrentText(query["scope"]); self.search()

    def song_table(self, entries):
        self.entries = entries
        table = QTableWidget(len(entries), 3); table.setObjectName("songs-table")
        table.setHorizontalHeaderLabels(["TITLE / ARTIST", "LENGTH", "SOURCE"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().hide(); table.verticalHeader().setDefaultSectionSize(58)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setAlternatingRowColors(True)
        for row, entry in enumerate(entries):
            table.setItem(row, 0, QTableWidgetItem(entry.title + ("\n" + entry.subtitle if entry.subtitle else "")))
            table.setItem(row, 1, QTableWidgetItem(clock(entry.track.durationSec * 1000) if entry.track and entry.track.durationSec else "—"))
            offline = entry.track and self.library.local_file(entry.track)
            table.setItem(row, 2, QTableWidgetItem("In Dkord" if offline else entry.kind.capitalize()))
        table.cellDoubleClicked.connect(lambda row, column: self.open_entry(entries[row]))
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def context(point):
            item = table.itemAt(point)
            if item and entries[item.row()].track:
                self.track_menu(entries[item.row()].track, table.mapToGlobal(point))
        table.customContextMenuRequested.connect(context)
        self.table = table; self.content_layout.addWidget(table, 1)

    def filter_table(self, query):
        if self.table is not None:
            for row, entry in enumerate(self.entries):
                self.table.setRowHidden(row, query.casefold() not in (entry.title + " " + entry.subtitle).casefold())

    def open_entry(self, entry):
        if entry.track:
            self.play_track(entry.track, related=self.page in {"Home", "Search"})
        else:
            self.notify("Opening catalogue…")
            route = self.route_epoch
            self.run(lambda event, progress: self.provider.browse(entry), lambda result: self.browse_result(*result) if route == self.route_epoch else None)

    def browse_result(self, name, songs):
        self.route_epoch += 1
        self.page = "Catalogue"; self.reset_content(name, "Explicit album/artist/playlist collection")
        self.content_layout.addWidget(button("Play all shown", lambda: self.play_queue(songs), True))
        self.song_table([Entry("song", t.id, t.title, t.artist, t) for t in songs])

    def download_selected(self):
        if self.table is None: return
        rows = {index.row() for index in self.table.selectedIndexes()}
        self.choose_download([self.entries[row].track for row in sorted(rows) if self.entries[row].track])

    def track_menu(self, track, point):
        menu = QMenu(self)
        menu.addAction("Play", lambda: self.play_track(track, related=False))
        menu.addAction("Play next", lambda: self.add_queue(track, next=True))
        menu.addAction("Add to queue", lambda: self.add_queue(track))
        liked = any(t.id == track.id for t in self.store.library("liked"))
        menu.addAction("Unlike" if liked else "Like", lambda: (self.store.like(track, not liked), self.notify("Library updated")))
        menu.addSeparator(); menu.addAction("Download…", lambda: self.choose_download([track]))
        menu.addAction("Add to playlist…", lambda: self.add_playlist(track))
        menu.addAction("Use in Mashup Studio", lambda: self.use_studio(track))
        if not track.local:
            menu.addAction("Copy song link", lambda: QApplication.clipboard().setText("https://www.youtube.com/watch?v=" + track.id))
        if self.page == "Listen Again":
            menu.addAction("Remove from history only", lambda: (self.store.remove_history(track.id), self.navigate("Listen Again")))
        menu.exec(point)

    def choose_download(self, tracks):
        if not tracks:
            self.notify("Select one or more songs first"); return
        dialog = QDialog(self); dialog.setWindowTitle("Download options"); layout = QVBoxLayout(dialog)
        layout.addWidget(label(f"{len(tracks)} song(s) · choose a destination", "pageTitle"))
        layout.addWidget(label("Private offline audio still uses your disk. Existing device copies are never removed.", "muted"))
        def choose(destination):
            folder = None
            if destination == "device":
                default = self.store.setting("device_folder", str(Path.home() / "Music" / "Dkord"))
                folder = QFileDialog.getExistingDirectory(dialog, "Download to device — choose folder", default)
                if not folder: return
                self.store.set_setting("device_folder", folder)
            for track in tracks:
                self.store.queue_download(track, destination, folder)
            dialog.accept(); self.drain_downloads(); self.notify("Request accepted. See Downloads for progress or any folder error.")
        app = button("Download in Dkord\nPrivate offline audio, not a public Music file", lambda: choose("app"), True)
        app.setObjectName("download-in-dkord")
        device = button("Download to device\nAlso save an accessible copy in your chosen folder", lambda: choose("device"))
        device.setObjectName("download-to-device")
        layout.addWidget(app); layout.addWidget(device); layout.addWidget(button("Cancel", dialog.reject))
        dialog.setMinimumWidth(480); dialog.exec()

    def drain_downloads(self):
        if self.download_running or self.closing: return
        self.download_running = True
        def work(event, progress):
            while not event.is_set():
                rows = self.store.downloads(unfinished=True)
                row = next((r for r in rows if r["state"] == "QUEUED"), None)
                if row is None: break
                try:
                    self.library.process_download(row["id"], lambda done, total: progress((row["id"], done, total)))
                except Exception:
                    pass  # per-row FAILED/error is durable; one bad source must not strand other songs
        def finished():
            self.download_running = False
            if self.page == "Downloads": self.downloads_page()
            if any(r["state"] == "QUEUED" for r in self.store.downloads(unfinished=True)): self.drain_downloads()
        self.run(work, progress=lambda value: self.notify(f"Downloading: {value[1]/1024**2:.1f} / {value[2]/1024**2:.1f} MiB"), download=True, finished=finished)

    def downloads_page(self):
        self.reset_content("Your offline space", "In Dkord stays in your user-data folder. Device copies are independent files and survive removing the private copy.")
        toolbar = QWidget(); row = QHBoxLayout(toolbar); row.setContentsMargins(0,0,0,0)
        row.addWidget(button("Refresh", self.downloads_page)); row.addWidget(button("Pause all", self.pause_all)); row.addWidget(button("Resume / retry all", self.retry_all)); row.addStretch()
        self.content_layout.addWidget(toolbar)
        rows = self.store.downloads(); listing = QListWidget()
        for download in rows:
            track = self.store.track(download["id"])
            if not track: continue
            destination = "In Dkord + device copy" if download["device_path"] else "In Dkord"
            item = QListWidgetItem(f"{track.title}\n{download['state']} · {download['bytes']/1024**2:.1f} MiB · {destination}" + ("\n" + download["error"] if download["error"] else ""))
            item.setData(Qt.ItemDataRole.UserRole, download); item.setSizeHint(QSize(0, 80)); listing.addItem(item)
        listing.itemDoubleClicked.connect(lambda item: self.play_track(self.store.track(item.data(Qt.ItemDataRole.UserRole)["id"]), related=False))
        listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def context(point):
            item = listing.itemAt(point)
            if not item: return
            download = item.data(Qt.ItemDataRole.UserRole); id = download["id"]; menu = QMenu(self)
            if download["state"] in {"QUEUED", "RUNNING"}:
                menu.addAction("Pause", lambda: (self.library.pause(id), self.downloads_page()))
            else:
                menu.addAction("Resume / retry", lambda: (self.store.update_download(id, state="QUEUED", error=None), self.drain_downloads()))
            menu.addAction("Choose destination…", lambda: self.choose_download([self.store.track(id)]))
            menu.addAction("Remove in Dkord (device copies kept)", lambda: self.remove_download(id))
            menu.exec(listing.mapToGlobal(point))
        listing.customContextMenuRequested.connect(context); self.content_layout.addWidget(listing,1)

    def remove_download(self, id):
        if self.current() and self.current().id == id:
            self.desired_playing = False; self.player.stop(); self.player.setSource(QUrl()); self.loaded_epoch = -1
        self.run(lambda event, progress: self.library.remove(id), lambda result: self.downloads_page())

    def pause_all(self):
        for row in self.store.downloads(unfinished=True): self.library.pause(row["id"])
        self.downloads_page()

    def retry_all(self):
        for row in self.store.downloads():
            if row["state"] in {"FAILED", "PAUSED"}: self.store.update_download(row["id"], state="QUEUED", error=None)
        self.drain_downloads()

    def playlists_page(self):
        self.reset_content("Made for your moments", "Local playlists, kept through updates. JSON imports/exports are compatible with Android; audio bytes are not included.")
        toolbar = QWidget(); buttons = QHBoxLayout(toolbar); buttons.setContentsMargins(0,0,0,0)
        buttons.addWidget(button("New playlist", self.new_playlist, True)); buttons.addWidget(button("Import JSON", self.import_library)); buttons.addWidget(button("Export library JSON", self.export_library)); buttons.addStretch()
        self.content_layout.addWidget(toolbar)
        listing = QListWidget()
        for playlist in self.store.playlists():
            item = QListWidgetItem(f"{playlist['name']}\n{len(playlist['data'])} songs"); item.setData(Qt.ItemDataRole.UserRole, playlist); item.setSizeHint(QSize(0,64)); listing.addItem(item)
        def open_playlist(item):
            playlist = item.data(Qt.ItemDataRole.UserRole)
            songs = [Track.parse(t) for t in playlist["data"]]
            self.browse_result(playlist["name"], songs)
        listing.itemDoubleClicked.connect(open_playlist)
        listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def context(point):
            item=listing.itemAt(point)
            if not item:return
            playlist=item.data(Qt.ItemDataRole.UserRole); menu=QMenu(self)
            def rename():
                name,ok=QInputDialog.getText(self,"Rename playlist","Name",text=playlist["name"])
                if ok and name.strip():self.store.save_playlist(name,[Track.parse(t) for t in playlist["data"]],playlist["id"]);self.playlists_page()
            menu.addAction("Rename",rename)
            menu.addAction("Export playlist JSON",lambda:self.export_library(playlist))
            menu.addAction("Delete playlist only",lambda:(self.store.delete_playlist(playlist["id"]),self.playlists_page()))
            menu.exec(listing.mapToGlobal(point))
        listing.customContextMenuRequested.connect(context);self.content_layout.addWidget(listing,1)

    def new_playlist(self):
        name, ok = QInputDialog.getText(self, "New playlist", "Name")
        if ok and name.strip(): self.store.save_playlist(name, []); self.navigate("Playlists")

    def add_playlist(self, track):
        playlists=self.store.playlists()
        if not playlists:
            self.new_playlist();playlists=self.store.playlists()
        if not playlists:return
        choice,ok=QInputDialog.getItem(self,"Add to playlist","Playlist",[p["name"] for p in playlists],0,False)
        if ok:
            selected=next(p for p in playlists if p["name"]==choice)
            self.store.save_playlist(selected["name"],[Track.parse(t) for t in selected["data"]]+[track],selected["id"])
            self.notify("Added to playlist")

    def import_library(self):
        name,_=QFileDialog.getOpenFileName(self,"Import Dkord playlist JSON","","Dkord JSON (*.json)")
        if not name:return
        try:
            from .library_json import import_library
            import_library(self.store,Path(name));self.playlists_page();self.notify("Playlists and likes imported. Audio files are not part of JSON exports.")
        except Exception as error:self.notify(str(error))

    def export_library(self, playlist=None):
        name,_=QFileDialog.getSaveFileName(self,"Export Dkord playlist JSON","Dkord-library.json","JSON (*.json)")
        if not name:return
        from .library_json import export_library
        try:export_library(self.store,Path(name),playlist);self.notify("Export saved; local audio is not embedded in this JSON file")
        except Exception as error:self.notify(str(error))

    def build_player(self, layout):
        frame=QFrame();frame.setObjectName("player"); body=QVBoxLayout(frame);body.setContentsMargins(22,12,22,14)
        top=QHBoxLayout(); self.now=label("Nothing playing");self.now.setMaximumWidth(300);self.now.setMinimumWidth(150)
        self.now_artist=label("Choose a song to start", "muted")
        info=QVBoxLayout();info.addWidget(self.now);info.addWidget(self.now_artist);top.addLayout(info,1)
        self.previous_button=button("◀",lambda:self.next_track(-1));self.previous_button.setToolTip("Previous")
        self.play_button=button("Play",self.toggle,True);self.play_button.setObjectName("play-toggle")
        self.next_button=button("▶",lambda:self.next_track(1));self.next_button.setToolTip("Next")
        top.addWidget(self.previous_button);top.addWidget(self.play_button);top.addWidget(self.next_button)
        self.shuffle=QCheckBox("Shuffle");self.shuffle.setChecked(bool(self.store.setting("shuffle",False)));self.shuffle.toggled.connect(self.shuffle_queue);top.addWidget(self.shuffle)
        self.repeat=QComboBox();self.repeat.addItems(["Repeat off","Repeat one","Repeat all"]);self.repeat.setCurrentIndex(int(self.store.setting("repeat",0)));top.addWidget(self.repeat)
        self.speed=QDoubleSpinBox();self.speed.setRange(.5,2);self.speed.setSingleStep(.05);self.speed.setSuffix("×");self.speed.setValue(float(self.store.setting("speed",1)));self.speed.setMaximumWidth(92)
        self.speed.valueChanged.connect(self.player.setPlaybackRate);self.player.setPlaybackRate(self.speed.value());top.addWidget(self.speed)
        top.addWidget(button("Lyrics",self.lyrics));top.addWidget(button("Sleep",self.sleep_timer));top.addWidget(button("Queue",lambda:self.queue_dock.setVisible(not self.queue_dock.isVisible())))
        volume=QSlider(Qt.Orientation.Horizontal);volume.setRange(0,100);volume.setValue(int(self.audio.volume()*100));volume.setFixedWidth(90);volume.setToolTip("Volume")
        volume.valueChanged.connect(lambda v:self.audio.setVolume(v/100));top.addWidget(volume)
        body.addLayout(top);line=QHBoxLayout();self.elapsed=label("0:00","muted");self.remaining=label("—","muted")
        self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.setObjectName("playback-seek");self.seek.setRange(0,1);self.seek.setEnabled(False)
        self.seek.sliderReleased.connect(lambda:self.player.setPosition(self.seek.value()))
        line.addWidget(self.elapsed);line.addWidget(self.seek,1);line.addWidget(self.remaining);body.addLayout(line);layout.addWidget(frame)

    def current(self):
        return self.queue[self.index] if self.queue and 0<=self.index<len(self.queue) else None

    def restore(self):
        self.session_writable=True
        try:
            session=self.store.setting("session",{})
            if session.get("version",1)!=1:raise ValueError("Unknown saved queue version")
            self.queue=[Track.parse(t) for t in session.get("queue",[])]
            self.index=max(0,min(session.get("index",0),len(self.queue)-1))
            self.pending_seek=max(0,int(session.get("position",0)))
            if track:=self.current():self.now.setText(track.title[:90]);self.now_artist.setText(track.artist[:90]);self.elapsed.setText(clock(self.pending_seek))
            self.refresh_queue()
        except Exception:
            self.session_writable=False
            self.notify("Saved queue could not be read. It was not overwritten; the rest of your library is kept.")

    def save_session(self):
        if self.session_writable:
            self.store.set_setting("session",{"version":1,"queue":[t.json() for t in self.queue],"index":self.index,
                "position":self.player.position() if self.loaded_epoch==self.epoch else self.pending_seek})

    def play_track(self, track, related=False):
        if not track:return
        self.play_queue([track])
        if related and self.store.setting("autoplay",True) and not track.local:
            owner,revision=self.epoch,self.revision
            def append(songs):
                if owner==self.epoch and revision==self.revision:
                    known={t.id for t in self.queue};self.queue.extend(t for t in songs if t.id not in known);self.refresh_queue();self.save_session()
            self.run(lambda event,progress:self.provider.related(track,[track]),append,failed=lambda text:self.notify("Music radio unavailable; the selected song is kept."))

    def play_queue(self, tracks):
        if not tracks:return
        self.queue=list(tracks);self.index=0
        if self.shuffle.isChecked() and len(self.queue)>1:
            remaining=self.queue[1:];random.shuffle(remaining);self.queue=self.queue[:1]+remaining
        self.revision+=1;self.play_index(0)

    def play_index(self, index, position=0):
        if not 0<=index<len(self.queue):return
        self.preview_player.stop();self.desired_playing=True;self.player.pause();self.index=index
        self.epoch+=1;owner=self.epoch;self.pending_seek=max(0,position);self.seek.setEnabled(False);self.play_button.setText("Pause")
        track=self.queue[index];self.now.setText(track.title[:90]);self.now.setToolTip(track.title);self.now_artist.setText(track.artist[:90])
        self.refresh_queue();self.save_session();self.notify("Preparing playback…")
        local=self.library.local_file(track)
        if local:self.set_media(QUrl.fromLocalFile(str(local)),owner);return
        if track.local:self.notify("Local export is missing. Export it again; it cannot be resolved online.");self.desired_playing=False;return
        def resolved(result):
            if owner==self.epoch:
                url,headers=result;self.set_media(QUrl(self.proxy.register(url,headers)),owner)
        self.run(lambda event,progress:self.provider.resolve(track),resolved,
                 failed=lambda text:self.notify(text) if owner==self.epoch else None)

    def set_media(self,url,owner):
        if owner!=self.epoch:return
        self.loaded_epoch=owner;self.player.setSource(url)
        if self.desired_playing:self.player.play()

    def media_status(self,status):
        if self.loaded_epoch!=self.epoch:return
        if status==QMediaPlayer.MediaStatus.LoadedMedia:
            if self.pending_seek:self.player.setPosition(self.pending_seek)
            self.pending_seek=0;self.seek.setEnabled(True)
            if self.desired_playing:self.player.play()
        elif status==QMediaPlayer.MediaStatus.EndOfMedia and self.desired_playing:
            if self.repeat.currentIndex()==1:self.play_index(self.index)
            elif self.index+1<len(self.queue):self.next_track(1)
            elif self.repeat.currentIndex()==2:self.play_index(0)
            else:self.desired_playing=False;self.play_button.setText("Play")

    def toggle(self):
        if self.desired_playing and (self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState or self.loaded_epoch!=self.epoch):
            self.desired_playing=False;self.player.pause();self.play_button.setText("Play");self.save_session()
        elif self.current():
            self.desired_playing=True
            if self.loaded_epoch==self.epoch and not self.player.source().isEmpty():self.player.play()
            else:self.play_index(self.index,self.pending_seek)

    def resume(self):
        if self.current():self.play_index(self.index,self.pending_seek if self.loaded_epoch!=self.epoch else self.player.position())
        else:self.notify("No saved queue yet. Choose a song first.")

    def next_track(self, delta):
        if not self.queue:return
        if delta<0 and self.player.position()>3000:self.player.setPosition(0);return
        index=self.index+delta
        if index>=len(self.queue) and self.repeat.currentIndex()==2:index=0
        if 0<=index<len(self.queue):self.play_index(index)

    def shuffle_queue(self, enabled):
        if not enabled or len(self.queue)<2:return
        current=self.current();remaining=[t for i,t in enumerate(self.queue) if i!=self.index]
        random.shuffle(remaining);self.queue=[current]+remaining;self.index=0;self.revision+=1
        self.refresh_queue();self.save_session()

    def add_queue(self,track,next=False):
        track.validate();self.revision+=1
        if next:self.queue.insert(min(self.index+1,len(self.queue)),track)
        else:self.queue.append(track)
        self.refresh_queue();self.save_session();self.notify("Queue updated; playback was not restarted")

    def refresh_queue(self):
        self.queue_list.clear()
        for index,track in enumerate(self.queue):
            item=QListWidgetItem(("▶ " if index==self.index else "")+track.title+"\n"+track.artist);item.setSizeHint(QSize(220,58));self.queue_list.addItem(item)
        self.queue_dock.setWindowTitle(f"Up next · {len(self.queue)}")

    def queue_menu(self,point):
        item=self.queue_list.itemAt(point)
        if not item:return
        index=self.queue_list.row(item);menu=QMenu(self)
        def move(delta):
            to=index+delta
            if not 0<=to<len(self.queue):return
            current=self.current();track=self.queue.pop(index);self.queue.insert(to,track)
            self.index=next(i for i,t in enumerate(self.queue) if t is current);self.revision+=1;self.refresh_queue();self.save_session()
        def remove():
            self.revision+=1
            if index==self.index:
                self.desired_playing=False;self.player.stop();self.player.setSource(QUrl());self.epoch+=1
            self.queue.pop(index)
            if index<self.index:self.index-=1
            self.index=max(0,min(self.index,len(self.queue)-1));self.refresh_queue();self.save_session()
        menu.addAction("Play now",lambda:self.play_index(index));menu.addAction("Move up",lambda:move(-1));menu.addAction("Move down",lambda:move(1));menu.addAction("Remove from queue",remove)
        menu.exec(self.queue_list.mapToGlobal(point))

    def position_changed(self,position):
        if self.loaded_epoch!=self.epoch:return
        if not self.seek.isSliderDown():self.seek.setValue(position)
        self.elapsed.setText(clock(position))
        if self.current() and self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState and time.monotonic()-self.last_history>5:
            self.last_history=time.monotonic();self.store.history(self.current(),position);self.save_session()

    def duration_changed(self,duration):
        self.seek.setRange(0,max(1,duration));self.remaining.setText(clock(duration) if duration>0 else "—")

    def playback_changed(self,state):
        playing=state==QMediaPlayer.PlaybackState.PlayingState;self.play_button.setText("Pause" if playing else "Play")
        if playing and self.current() and self.loaded_epoch==self.epoch:self.store.history(self.current(),self.player.position())

    def tick(self):
        if self.sleep_at is not None and time.monotonic()>=self.sleep_at:
            self.sleep_at=None;self.desired_playing=False;self.player.pause();self.preview_player.stop();self.notify("Sleep timer ended. Playback will not resume automatically.")

    def sleep_timer(self):
        minutes,ok=QInputDialog.getInt(self,"Sleep timer","Minutes (0 cancels the timer)",30,0,1440)
        if ok:self.sleep_at=time.monotonic()+minutes*60 if minutes else None;self.notify(f"Sleep timer: {minutes} minutes" if minutes else "Sleep timer cancelled")

    def lyrics(self):
        track=self.current()
        if not track:return
        dialog=QDialog(self);dialog.setWindowTitle("Lyrics — "+track.title);dialog.resize(650,650);layout=QVBoxLayout(dialog)
        text=QTextEdit();text.setReadOnly(True);text.setPlainText("Loading LRCLIB lyrics…");layout.addWidget(text)
        def fetch(event,progress):
            import requests
            response=requests.get("https://lrclib.net/api/get",params={"track_name":track.title,"artist_name":track.artist,"duration":track.durationSec},timeout=15)
            response.raise_for_status();data=response.json();return data.get("syncedLyrics") or data.get("plainLyrics") or "No lyrics returned for this track."
        self.run(fetch,lambda value:text.setPlainText(value) if not sip.isdeleted(text) else None,failed=lambda value:text.setPlainText(value) if not sip.isdeleted(text) else None)
        dialog.exec()

    def clear_history(self):
        if QMessageBox.question(self,"Clear listening history?","Remove history entries only? Likes, playlists, queue and downloads remain.")==QMessageBox.StandardButton.Yes:
            self.store.remove_history();self.navigate("Listen Again")

    def studio_page(self):
        self.reset_content("Mashup Studio", "Online song → private project source → precise clips → one real M4A. No manual download prerequisite.")
        projects=self.store.projects()
        if self.studio_id not in {p["id"] for p in projects}:self.studio_id=projects[0]["id"] if projects else None
        toolbar=QWidget();row=QHBoxLayout(toolbar);row.setContentsMargins(0,0,0,0)
        projects_box=QComboBox();projects_box.setMinimumWidth(180)
        for p in projects:projects_box.addItem(p["name"],p["id"])
        if self.studio_id:projects_box.setCurrentIndex(next(i for i,p in enumerate(projects) if p["id"]==self.studio_id))
        projects_box.setEnabled(self.studio_task is None)
        projects_box.currentIndexChanged.connect(lambda index:self.select_project(projects_box.itemData(index)))
        row.addWidget(projects_box,1);row.addWidget(button("New project",self.new_project,True));row.addWidget(button("Rename",self.rename_project));row.addWidget(button("Delete",self.delete_project))
        self.content_layout.addWidget(toolbar)
        if not self.studio_id:self.content_layout.addWidget(label("Create a project, then choose online songs, offline downloads or audio files from your computer."));self.content_layout.addStretch();return
        p=self.store.project(self.studio_id)
        actions=QWidget();tools=QHBoxLayout(actions);tools.setContentsMargins(0,0,0,0)
        for text,fn in (("Search online songs",self.online_picker),("Import audio files",self.import_files),("Use a Dkord download",self.import_download)):
            b=button(text,fn);b.setEnabled(self.studio_task is None);tools.addWidget(b)
        self.content_layout.addWidget(actions)
        self.studio_status=label("Preparing audio…" if self.studio_task else "Sources are private project copies. Original files are unchanged.","muted")
        self.content_layout.addWidget(self.studio_status)
        if self.studio_task:self.content_layout.addWidget(button("Cancel preparation / export",lambda:self.studio_task.cancel.set() if self.studio_task else None))
        lists=QWidget();side=QHBoxLayout(lists);side.setContentsMargins(0,0,0,0)
        left=QWidget();a=QVBoxLayout(left);a.setContentsMargins(0,0,0,0);a.addWidget(label(f"SOURCES · {len(p['sources'])}","eyebrow"));sources=QListWidget()
        for source in p["sources"]:
            item=QListWidgetItem(f"{source['title']}\n{clock(source['durationMs'])}");item.setSizeHint(QSize(0,58));item.setData(Qt.ItemDataRole.UserRole,source);sources.addItem(item)
        sources.itemDoubleClicked.connect(lambda item:self.edit_clip(item.data(Qt.ItemDataRole.UserRole)))
        a.addWidget(sources,1);a.addWidget(button("Add range from selected source",lambda:self.edit_clip(sources.currentItem().data(Qt.ItemDataRole.UserRole)) if sources.currentItem() else None))
        side.addWidget(left,1)
        right=QWidget();b=QVBoxLayout(right);b.setContentsMargins(0,0,0,0);b.addWidget(label(f"ARRANGEMENT · {len(p['clips'])} CLIPS","eyebrow"));clips=QListWidget()
        indexed={s["id"]:s for s in p["sources"]}
        for index,clip in enumerate(p["clips"]):
            source=indexed[clip["sourceId"]];item=QListWidgetItem(f"{index+1}. {source['title']}\n{clip['startMs']/1000:.3f} → {clip['endMs']/1000:.3f} s · {clock(clip['endMs']-clip['startMs'])}")
            item.setData(Qt.ItemDataRole.UserRole,clip);item.setSizeHint(QSize(0,62));clips.addItem(item)
        clips.itemDoubleClicked.connect(lambda item:self.edit_clip(indexed[item.data(Qt.ItemDataRole.UserRole)["sourceId"]],item.data(Qt.ItemDataRole.UserRole)))
        b.addWidget(clips,1)
        buttons=QHBoxLayout()
        buttons.addWidget(button("↑ Move up",lambda:self.move_clip(clips.currentRow(),-1)));buttons.addWidget(button("↓ Move down",lambda:self.move_clip(clips.currentRow(),1)));buttons.addWidget(button("Remove clip",lambda:self.remove_clip(clips.currentRow())))
        b.addLayout(buttons);side.addWidget(right,2);self.content_layout.addWidget(lists,1)
        export_row=QWidget();e=QHBoxLayout(export_row);e.setContentsMargins(0,0,0,0)
        e.addWidget(label("Total · "+clock(sum(c["endMs"]-c["startMs"] for c in p["clips"])),"muted"));e.addStretch()
        render=button("Merge & save M4A",self.export_project,True);render.setEnabled(bool(p["clips"]) and self.studio_task is None);e.addWidget(render);self.content_layout.addWidget(export_row)

    def select_project(self,id):
        if id:self.studio_id=id;self.studio_page()

    def new_project(self):
        name,ok=QInputDialog.getText(self,"New Studio project","Project name")
        if ok and name.strip():
            try:self.studio_id=self.store.create_project(name);self.navigate("Mashup Studio")
            except ValueError as e:self.notify(str(e))

    def rename_project(self):
        if not self.studio_id:return
        p=self.store.project(self.studio_id);name,ok=QInputDialog.getText(self,"Rename project","Project name",text=p["name"])
        if ok and 0<len(name.strip())<=160:self.store.change_project(self.studio_id,lambda p:p.update(name=name.strip()));self.studio_page()

    def delete_project(self):
        if self.studio_id and QMessageBox.question(self,"Delete project?","Delete private project sources and clips? Exported audio and original files are kept.")==QMessageBox.StandardButton.Yes:
            id=self.studio_id;self.preview_player.stop();self.run(lambda event,progress:self.library.delete_project(id),lambda value:self.studio_page())

    def import_source(self,source):
        if self.studio_task or not self.studio_id:return
        target=self.studio_id
        def finished():
            self.studio_task=None
            if self.page=="Mashup Studio":self.studio_page()
        self.studio_task=self.run(lambda event,progress:self.library.import_source(target,source,event,lambda done,total:progress((done,total))),
            lambda value:self.notify("Audio is ready in this project; no manual Downloads entry was needed."),
            progress=lambda value:self.studio_status.setText(f"Preparing privately · {value[0]/1024**2:.1f} / {value[1]/1024**2:.1f} MiB") if self.page=="Mashup Studio" and not sip.isdeleted(self.studio_status) else None,finished=finished)
        self.studio_page()

    def use_studio(self,track):
        self.navigate("Mashup Studio")
        if not self.studio_id:self.new_project()
        if self.studio_id:self.import_source(track)

    def import_files(self):
        files,_=QFileDialog.getOpenFileNames(self,"Import non-DRM audio files","","Audio (*.m4a *.mp3 *.wav *.flac *.ogg *.opus *.aac *.webm);;All files (*)")
        if not files or not self.studio_id or self.studio_task:return
        target=self.studio_id
        def work(event,progress):
            for file in files:check_cancel(event);self.library.import_source(target,Path(file),event)
        def finished():
            self.studio_task=None
            if self.page=="Mashup Studio":self.studio_page()
        self.studio_task=self.run(work,lambda result:self.notify("Audio files imported; original files were not changed."),finished=finished);self.studio_page()

    def import_download(self):
        songs=[s for s in self.store.library("downloads") if self.library.local_file(s)]
        if not songs:self.notify("No completed offline audio. Use online search or a file instead; downloading first is not required.");return
        title,ok=QInputDialog.getItem(self,"Use a Dkord download","Song",[t.title for t in songs],0,False)
        if ok:self.import_source(next(t for t in songs if t.title==title))

    def online_picker(self):
        if self.studio_task or not self.studio_id:return
        dialog=QDialog(self);dialog.setWindowTitle("Choose an online Studio source");dialog.resize(820,600);layout=QVBoxLayout(dialog)
        layout.addWidget(label("Choose a song. Start creating.","pageTitle"));layout.addWidget(label("Audio is prepared privately for your project — not added to Downloads or public Music.","muted"))
        controls=QHBoxLayout();query=QLineEdit();query.setObjectName("studio-song-query");query.setPlaceholderText("Search songs, including Hindi or Choliwood…");controls.addWidget(query,1)
        listing=QListWidget();listing.setObjectName("studio-song-results");owner={"epoch":0,"task":None}
        def submit():
            text=" ".join(query.text().split())
            if not text:return
            owner["epoch"]+=1;epoch=owner["epoch"]
            if owner["task"]:owner["task"].cancel.set()
            listing.clear();listing.addItem("Searching…")
            def results(entries):
                if sip.isdeleted(listing) or epoch!=owner["epoch"]:return
                listing.clear()
                for entry in entries:
                    if entry.track:
                        item=QListWidgetItem(entry.track.title+"\n"+entry.track.artist);item.setData(Qt.ItemDataRole.UserRole,entry.track);item.setSizeHint(QSize(0,58));listing.addItem(item)
            owner["task"]=self.run(lambda event,progress:self.provider.search(text,"Songs",40),results)
        query.returnPressed.connect(submit);controls.addWidget(button("Search",submit,True));layout.addLayout(controls);layout.addWidget(listing,1)
        def selected():
            item=listing.currentItem()
            if item and (track:=item.data(Qt.ItemDataRole.UserRole)):dialog.accept();self.import_source(track)
        listing.itemDoubleClicked.connect(lambda item:selected());actions=QHBoxLayout();actions.addStretch();actions.addWidget(button("Cancel",dialog.reject));actions.addWidget(button("Add to project",selected,True));layout.addLayout(actions)
        dialog.exec()
        if owner["task"]:owner["task"].cancel.set()

    def edit_clip(self,source,clip=None):
        if not self.studio_id:return
        id=self.studio_id;dialog=QDialog(self);dialog.setWindowTitle("Edit clip range");layout=QVBoxLayout(dialog);layout.addWidget(label(source["title"],"pageTitle"))
        form=QFormLayout();start=QLineEdit(f"{clip['startMs']/1000:.3f}" if clip else "0.000");end=QLineEdit(f"{clip['endMs']/1000:.3f}" if clip else f"{source['durationMs']/1000:.3f}")
        start.setObjectName("studio-start");end.setObjectName("studio-end");form.addRow("Start · seconds / mm:ss",start);form.addRow("End · seconds / mm:ss",end);layout.addLayout(form)
        error=label("Source ends at "+f"{source['durationMs']/1000:.3f}"+" seconds.","muted");layout.addWidget(error)
        def values():
            a,b=milliseconds(start.text()),milliseconds(end.text())
            if not 0<=a<b<=source["durationMs"]:raise ValueError("Start must precede end; both must stay inside the source.")
            return a,b
        def preview():
            try:
                a,b=values();self.desired_playing=False;self.player.pause();self.preview_end=b
                self.preview_player.setSource(QUrl.fromLocalFile(str(self.library.source_file(source))));self.preview_player.setPosition(a);self.preview_player.play()
            except Exception as e:error.setText(str(e))
        def save():
            try:
                a,b=values();new={"id":clip["id"] if clip else str(uuid4()),"sourceId":source["id"],"startMs":a,"endMs":b}
                def update(p):
                    p["clips"]=[new if c["id"]==new["id"] else c for c in p["clips"]] if clip else p["clips"]+[new]
                self.store.change_project(id,update);dialog.accept();self.studio_page()
            except Exception as e:error.setText(str(e))
        actions=QHBoxLayout();actions.addWidget(button("Preview range",preview));actions.addStretch();actions.addWidget(button("Cancel",dialog.reject));actions.addWidget(button("Save clip",save,True));layout.addLayout(actions)
        dialog.setMinimumWidth(520);dialog.exec();self.preview_player.stop();self.preview_end=None

    def move_clip(self,index,delta):
        if index<0 or not self.studio_id:return
        def change(p):
            to=max(0,min(index+delta,len(p["clips"])-1));p["clips"].insert(to,p["clips"].pop(index))
        self.store.change_project(self.studio_id,change);self.studio_page()

    def remove_clip(self,index):
        if index>=0 and self.studio_id:self.store.change_project(self.studio_id,lambda p:p["clips"].pop(index));self.studio_page()

    def export_project(self):
        if not self.studio_id or self.studio_task:return
        target=self.studio_id
        def finished():
            self.studio_task=None
            if self.page=="Mashup Studio":self.studio_page()
        self.studio_task=self.run(lambda event,progress:self.library.export(target,event,progress),
            lambda track:self.notify("Real M4A saved in Downloads. Play it or choose Download to device for an accessible copy."),
            progress=lambda value:self.studio_status.setText(f"Merging audio · {value*100:.0f}% · original snapshot") if self.page=="Mashup Studio" and not sip.isdeleted(self.studio_status) else None,finished=finished)
        self.studio_page()

    def settings_page(self):
        self.reset_content("Make Dkord yours", "Local settings, clear storage choices and platform-matched updates. Your library is outside the application installation folder.")
        panel=QWidget();form=QFormLayout(panel)
        theme=QComboBox();theme.addItems(["dark","light","amoled"]);theme.setCurrentText(self.store.setting("theme","dark"));theme.currentTextChanged.connect(self.apply_theme);form.addRow("Appearance",theme)
        quality=QComboBox();quality.addItems(["high","medium","low"]);quality.setCurrentText(self.store.setting("quality","high"));quality.currentTextChanged.connect(lambda v:self.store.set_setting("quality",v));form.addRow("Download quality",quality)
        autoplay=QCheckBox("Use music-only radio after a chosen Search/Home song");autoplay.setChecked(self.store.setting("autoplay",True));autoplay.toggled.connect(lambda v:self.store.set_setting("autoplay",v));form.addRow("Autoplay",autoplay)
        data=QLineEdit(str(self.store.root));data.setReadOnly(True);form.addRow("Private user-data folder",data)
        form.addRow("Version",label(__version__+" · desktop preview · "+sys.platform))
        form.addRow("Update channel",label("Desktop only · signed manifest · OS + CPU matched · no APK substitution"))
        check=button("Check for desktop updates",self.check_updates,True);form.addRow(check)
        form.addRow(label("Preview installers are not official trusted/notarized releases. The production update key/channel is not configured yet; untrusted installers are refused.","muted"))
        self.content_layout.addWidget(panel);self.content_layout.addStretch()

    def check_updates(self):
        self.notify("Checking the desktop release channel…")
        def checked(update):
            if update is None:self.notify("No newer compatible signed desktop release was found.");return
            if QMessageBox.question(self,"Dkord desktop update",f"Download version {update.version} for {update.platform}?\n{update.size/1024**2:.1f} MiB. Your user-data folder is retained.")!=QMessageBox.StandardButton.Yes:return
            def ready(file):
                if QMessageBox.question(self,"Verified update ready","Open the matching native installer now? No release-page browsing is required.")==QMessageBox.StandardButton.Yes:
                    try:self.updater.install(update,file);self.close()
                    except Exception as e:self.notify(str(e))
            self.run(lambda event,progress:self.updater.download(update,event,lambda done,total:progress((done,total))),ready,
                     progress=lambda value:self.notify(f"Desktop update · {value[0]/1024**2:.1f}/{value[1]/1024**2:.1f} MiB"))
        self.run(lambda event,progress:self.updater.check(),checked)

    def about(self):
        dialog=QDialog(self);dialog.setWindowTitle("About Dkord");dialog.resize(640,560);layout=QVBoxLayout(dialog)
        layout.addWidget(label("Dkord", "brand"));layout.addWidget(label("YOUR MUSIC. YOUR MIX. YOUR SPACE.","eyebrow"))
        layout.addWidget(label("An open-source music player and audio Mashup Studio by DeepuGupta. Search the real music catalogue, keep a private offline library and turn your selected audio into precise, playable mixes."))
        layout.addWidget(label(f"Desktop {__version__} preview · GPL-3.0-only · native Qt multimedia + FFmpeg", "muted"))
        layout.addWidget(label("This is a desktop preview, not a finished Android-parity release. Account sign-in, Listen Together, enhanced Android radio ranking, synchronized lyric highlighting and all native signing/notarization remain acceptance gaps. Android v0.9.1 stays the official stable release."))
        layout.addWidget(label("No cloud media synchronization or automatic phone-download transfer is included. Ordinary updates keep this device's user-data folder; JSON can transfer playlists/likes, not audio bytes."))
        layout.addWidget(label("Public providers: YouTube / YouTube Music and LRCLIB. Guest/provider restrictions are not bypassed. Only download, import or edit audio you have permission to use. No demo songs, invented search statistics or custom paid backend."))
        layout.addStretch();layout.addWidget(button("Close",dialog.accept));dialog.exec()

    def closeEvent(self,event):
        self.closing=True;self.timer.stop();self.desired_playing=False
        self.save_session();self.store.set_setting("volume",self.audio.volume());self.store.set_setting("speed",self.speed.value());self.store.set_setting("repeat",self.repeat.currentIndex());self.store.set_setting("shuffle",self.shuffle.isChecked())
        for task in list(self.tasks):task.cancel.set()
        for id in list(self.library.active):self.library.pause(id)
        self.player.stop();self.player.setSource(QUrl());self.preview_player.stop();self.proxy.close();event.accept()
