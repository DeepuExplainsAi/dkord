from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path
import sys
from uuid import uuid4

from .qt import (sip, Qt, QThreadPool, QTimer, QUrl, QSize, QAction, QColor, QFont, QIcon, QKeySequence, QShortcut, QAudioOutput, QMediaPlayer)
from .qt import (
    QApplication, QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStyle, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from . import __version__
from .platforms import WINDOWS_X86
from .media import MediaLibrary, check_cancel
from .models import Track, clock, milliseconds
from .provider import Entry, Provider
from .store import Store
from .streaming import AudioProxy
from .tasks import Task
from .updates import Updater
from .diagnostics import Diagnostics

from .phone_ui import PhoneExperience
from .widgets import label, button, icon, translated
from .experience import palette


class MainWindow(PhoneExperience, QMainWindow):
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
        self.diagnostics = Diagnostics()
        self.restart_after_close = None
        self.epoch = 0
        self.revision = 0
        self.loaded_epoch = -1
        self.pending_seek = 0
        self.desired_playing = False
        self.search_epoch = 0
        self.search_limit = 20
        self.search_task = None
        self.search_supports_cursor = False; self.search_cursor = None; self.search_result = None
        self.more_task = None
        self.more_epoch = 0
        self.route_epoch = 0
        self.studio_task = None
        self.studio_id = None
        self.page = "Home"
        self.queue: list[Track] = []
        self.index = 0
        self.sleep_at = None; self.sleep_end_of_track = False; self.sleep_original_volume = None
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
        self.player.errorOccurred.connect(lambda error, text: self.playback_failed(text, self.epoch) if error != QMediaPlayer.Error.NoError and self.loaded_epoch == self.epoch else None)
        self.preview_player = QMediaPlayer(self); self.preview_audio = QAudioOutput(self)
        self.preview_player.setAudioOutput(self.preview_audio)
        self.preview_end = None
        self.preview_player.positionChanged.connect(lambda position: self.preview_player.stop() if self.preview_end and position >= self.preview_end else None)
        self.build_shell()
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.navigate("Settings"))
        QShortcut(QKeySequence("Ctrl+J"), self, activated=lambda: self.navigate("Downloads"))
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1000)
        self.apply_theme(store.setting("theme", "dark"))
        self.restore()
        self.navigate("Home", fetch=autoload)
        if autoload:
            self.drain_downloads()

    def run(self, call, done=None, progress=None, failed=None, download=False, finished=None, background=False) -> Task:
        task = Task(call); self.tasks.add(task)
        task.signals.result.connect(lambda result: done(result) if done and not self.closing else None)
        task.signals.error.connect(lambda _: self.diagnostics.record('download' if download else 'background', 'failed') if not self.closing else None)
        task.signals.error.connect(lambda text: (failed or self.notify)(text) if not self.closing else None)
        if progress:
            task.signals.progress.connect(lambda value: progress(value) if not self.closing else None)
        def finish():
            self.tasks.discard(task)
            if hasattr(self, "home_tasks"): self.home_tasks.discard(task)
            if finished and not self.closing:
                finished()
        task.signals.finished.connect(finish)
        (self.download_pool if download else self.home_pool if background else self.pool).start(task)
        return task

    def notify(self, text):
        self.statusBar().showMessage(str(text), 12000)

    def reset_content(self, title, subtitle=""):
        self.heading.setText(translated(title)); self.subtitle.setText(translated(subtitle)); self.subtitle.setVisible(bool(subtitle))
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.table = None

    def _legacy_navigate(self, page, fetch=True):
        self.route_epoch += 1
        self.page = page
        if page in {"Listen Again", "Liked songs"}:
            self.reset_content(self.tr("listen_title") if page=="Listen Again" else self.tr("liked_songs"))
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

    def search(self, exact=False):
        query = " ".join(self.query.text().split())
        if not query:
            self.navigate("Search"); return
        scope = self.scope.currentText()
        self.cancel_home(); self.select_navigation("Search")
        self.store.remember_query(query, scope)
        self.route_epoch += 1
        self.page = "Search"; self.search_limit = 20
        if self.more_task:
            self.more_task.cancel.set()
            self.more_task = None
        self.search_epoch += 1; owner = self.search_epoch
        if self.search_task:
            self.search_task.cancel.set()
        self.search_supports_cursor = callable(getattr(self.provider, 'search_page', None)) and scope not in {'Videos','All YouTube'}
        self.search_cursor = None; self.search_result = None
        supports_cursor = self.search_supports_cursor
        self.reset_content(query, self.tr(self.scope_labels.get(scope,'songs')))
        self.content_layout.addWidget(label(self.tr('loading')))
        route = self.route_epoch
        def ready(result):
            if owner == self.search_epoch and self.page == "Search" and route == self.route_epoch:
                if self.search_supports_cursor:
                    self.search_result = result; self.search_cursor = result.cursor; entries = list(result.entries)
                else:
                    entries = result
                self.show_entries(entries, "Search", query, scope)
        self.search_task = self.run(lambda event, progress: self.provider.search_page(query,scope,bool(exact)) if supports_cursor else self.provider.search(query,scope,20),ready)

    def show_entries(self, entries, page, query=None, scope=None):
        self.entries = entries
        titles = {'Listen Again':'recently_played','Liked songs':'liked_songs','Search':'tab_search'}
        self.reset_content(query or self.tr(titles.get(page,'tab_home')), self.tr('search_scope_uploads' if scope in {'Videos','All YouTube'} else 'search_scope_music_catalogue') if query else '')
        if query and self.search_result and self.search_result.suggested_query:
            result = self.search_result
            self.content_layout.addWidget(label(self.tr('search_showing_results_for' if result.corrected else 'search_did_you_mean',result.suggested_query),'muted'))
            def original():
                self.query.setText(query);self.search(exact=True)
            self.content_layout.addWidget(button(query if result.corrected else result.suggested_query,original if result.corrected else lambda:self.search_for(result.suggested_query)))
        controls = QWidget(); row = QHBoxLayout(controls); row.setContentsMargins(0, 0, 0, 0)
        tracks = [e.track for e in entries if e.track]
        row.addWidget(button("Play all shown", lambda: self.play_queue(tracks)))
        row.addWidget(button("Download selected", self.download_selected))
        row.addStretch(1)
        if query and (self.search_cursor is not None if self.search_supports_cursor else self.search_limit < 200):
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
        cursor = self.search_cursor; route = self.route_epoch; supports_cursor = self.search_supports_cursor
        if self.search_supports_cursor and cursor is None:
            return
        limit = min(200, self.search_limit + 20)
        self.notify("Loading more… Existing results are kept if this page fails.")
        def ready(result):
            if owner == self.search_epoch and self.page == "Search" and route == self.route_epoch:
                if self.search_supports_cursor:
                    self.search_cursor = result.cursor; entries = self.entries + list(result.entries)
                else:
                    entries = result
                self.search_limit = limit
                self.show_entries(entries, "Search", query, scope)
        def finished():
            if request == self.more_epoch:
                self.more_task = None
        self.more_task = self.run(lambda event, progress: self.provider.search_more(cursor) if supports_cursor else self.provider.search(query, scope, limit), ready, finished=finished)

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
        table = QTableWidget(len(entries), 4); table.setObjectName("songs-table")
        table.setHorizontalHeaderLabels(["TITLE / ARTIST", "LENGTH", "SOURCE", ""])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().hide(); table.verticalHeader().setDefaultSectionSize(72)
        table.horizontalHeader().hide(); table.setIconSize(QSize(52,52))
        table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Fixed); table.setColumnWidth(3,48)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.setAlternatingRowColors(False)
        for row, entry in enumerate(entries):
            item=QTableWidgetItem(entry.title + ("\n" + entry.subtitle if entry.subtitle else ""))
            item.setIcon(icon("library_music", palette(self.effective_theme())["onSurfaceVariant"], 52)); table.setItem(row,0,item)
            if row<40 and (image:=entry.thumbnail or (entry.track.thumbnail if entry.track else None)):
                def art_ready(pixmap, table=table, row=row):
                    if not sip.isdeleted(table) and table.item(row,0):table.item(row,0).setIcon(QIcon(pixmap))
                self.artwork_cache.request(image,art_ready)
            more=button("" if entry.track else "›",lambda checked=False,entry=entry,row=row:self.track_menu(entry.track,table.mapToGlobal(table.visualItemRect(table.item(row,0)).bottomRight())) if entry.track else self.open_entry(entry))
            if entry.track:more.setIcon(icon('more_vert',palette(self.effective_theme())['onSurface']))
            more.setObjectName("track-more");more.setAccessibleName(self.tr("more"));table.setCellWidget(row,3,more)
            table.setItem(row, 1, QTableWidgetItem(clock(entry.track.durationSec * 1000) if entry.track and entry.track.durationSec else "—"))
            offline = entry.track and self.library.local_file(entry.track)
            table.setItem(row, 2, QTableWidgetItem("In Dkord" if offline else entry.kind.capitalize()))
        table.cellDoubleClicked.connect(lambda row, column: self.open_entry(entries[row],row))
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

    def open_entry(self, entry, row=None):
        if entry.track:
            if self.page=="Catalogue" and self.collection_tracks:
                selected=row if row is not None and 0<=row<len(self.collection_tracks) and self.collection_tracks[row].id==entry.track.id else next((i for i,t in enumerate(self.collection_tracks) if t.id==entry.track.id),0)
                self.play_queue(self.collection_tracks,index=selected)
            else:self.play_track(entry.track, related=self.page in {"Home", "Search"})
        else:
            self.open_catalogue(entry)

    def browse_result(self, name, songs):
        self.route_epoch += 1
        self.page = "Catalogue"; self.select_navigation("Catalogue"); self.collection_tracks=list(songs); self.reset_content(name)
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
            if track:=self.current():
                self.now.setText(track.title);self.now_artist.setText(track.artist);self.mini_cover.set_url(track.thumbnail);self.elapsed.setText(clock(self.pending_seek))
                for slider in (self.seek,self.mini_seek):slider.setRange(0,max(1,track.durationSec*1000));slider.setValue(self.pending_seek)
            self.refresh_queue()
        except Exception:
            self.session_writable=False
            self.notify("Saved queue could not be read. It was not overwritten; the rest of your library is kept.")

    def save_session(self):
        if self.session_writable:
            self.store.set_setting("session",{"version":1,"queue":[t.json() for t in self.queue],"index":self.index,
                "position":self.player.position() if self.loaded_epoch==self.epoch else self.pending_seek})

    def play_track(self, track, related=False, context_hint=""):
        if not track:return
        self.play_queue([track])
        if related and self.store.setting("autoplay",True) and not track.local:
            owner,revision=self.epoch,self.revision
            def append(songs):
                if owner==self.epoch and revision==self.revision:
                    known={t.id for t in self.queue};self.queue.extend(t for t in songs if t.id not in known);self.refresh_queue();self.save_session()
            self.run(lambda event,progress:self.provider.related_context(track,[track],context_hint) if hasattr(self.provider,"related_context") else self.provider.related(track,[track]),append,failed=lambda text:self.notify("Music radio unavailable; the selected song is kept."))

    def play_queue(self, tracks, index=0, user=True):
        if not tracks:return
        self.queue=list(tracks);self.index=max(0,min(index,len(self.queue)-1))
        if self.shuffle.isChecked() and len(self.queue)>1:
            selected=self.queue[self.index];remaining=[t for i,t in enumerate(self.queue) if i!=self.index];random.shuffle(remaining);self.queue=[selected]+remaining;self.index=0
        self.revision+=1;self.play_index(self.index,user=user)

    def play_index(self, index, position=0, user=True, playing=True):
        if not 0<=index<len(self.queue):return
        self.preview_player.stop();self.desired_playing=playing;self.player.pause();self.index=index
        self.epoch+=1;owner=self.epoch;self.pending_seek=max(0,position);self.seek.setEnabled(False);self.update_play_button()
        track=self.queue[index];self.now.setText(track.title);self.now.setToolTip(track.title);self.now_artist.setText(track.artist);self.mini_cover.set_url(track.thumbnail)
        self.refresh_queue();self.save_session();self.notify("Preparing playback…")
        if user:self.room_local_intent()
        if self.full_player:self.full_player.refresh(force=True)
        local=self.library.local_file(track)
        if local:self.set_media(QUrl.fromLocalFile(str(local)),owner);return
        if track.local:self.playback_failed("Local export is missing. Export it again; it cannot be resolved online.",owner);return
        def resolved(result):
            if owner==self.epoch:
                url,headers=result;self.set_media(QUrl(self.proxy.register(url,headers)),owner)
        self.run(lambda event,progress:self.provider.resolve(track),resolved,
                 failed=lambda text:self.playback_failed(text,owner))

    def playback_failed(self, text, owner):
        if owner != self.epoch or self.closing:
            return
        self.desired_playing=False;self.update_play_button();self.diagnostics.record('playback','prepare_failed')
        from .models import public_error
        self.notify(self.tr('room_playback_error') if self.rooms.remote_loading else public_error(Exception(text)))
        self.rooms.playback_failed()

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
            if self.sleep_end_of_track:
                self.cancel_sleep();self.desired_playing=False;self.update_play_button();self.room_local_intent();return
            if self.repeat.currentIndex()==1:self.play_index(self.index,user=False)
            elif self.index+1<len(self.queue):self.next_track(1,user=False)
            elif self.repeat.currentIndex()==2:self.play_index(0,user=False)
            else:self.desired_playing=False;self.update_play_button()

    def toggle(self):
        if self.desired_playing and (self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState or self.loaded_epoch!=self.epoch):
            self.desired_playing=False;self.player.pause();self.update_play_button();self.save_session()
        elif self.current():
            self.desired_playing=True
            if self.loaded_epoch==self.epoch and not self.player.source().isEmpty():self.player.play()
            else:self.play_index(self.index,self.pending_seek,user=False)
        self.room_local_intent();self.update_play_button()

    def resume(self):
        if self.current():self.play_index(self.index,self.pending_seek if self.loaded_epoch!=self.epoch else self.player.position())
        else:self.notify("No saved queue yet. Choose a song first.")

    def next_track(self, delta, user=True):
        if not self.queue:return
        if delta<0 and self.player.position()>3000:self.user_seek(0,user=user);return
        index=self.index+delta
        if index>=len(self.queue) and self.repeat.currentIndex()==2:index=0
        if 0<=index<len(self.queue):self.play_index(index,user=user)

    def shuffle_queue(self, enabled):
        if not enabled or len(self.queue)<2:return
        current=self.current();remaining=[t for i,t in enumerate(self.queue) if i!=self.index]
        random.shuffle(remaining);self.queue=[current]+remaining;self.index=0;self.revision+=1
        self.refresh_queue();self.save_session()

    def add_queue(self,track,next=False):
        track.validate();self.revision+=1
        if next:self.queue.insert(min(self.index+1,len(self.queue)),track)
        else:self.queue.append(track)
        self.refresh_queue();self.save_session();self.room_local_intent();self.notify("Queue updated; playback was not restarted")

    def refresh_queue(self):
        self.queue_list.clear()
        for index,track in enumerate(self.queue):
            item=QListWidgetItem(("▶ " if index==self.index else "")+track.title+"\n"+track.artist);item.setSizeHint(QSize(220,58));self.queue_list.addItem(item)
        self.queue_dock.setWindowTitle(f"{self.tr('queue')} · {len(self.queue)}")
        if self.full_player:self.full_player.refresh_queue()

    def queue_menu(self,point,listing=None):
        listing=listing or self.queue_list
        item=listing.itemAt(point)
        if not item:return
        index=listing.row(item);menu=QMenu(self)
        def move(delta):
            to=index+delta
            if not 0<=to<len(self.queue):return
            current=self.current();track=self.queue.pop(index);self.queue.insert(to,track)
            self.index=next(i for i,t in enumerate(self.queue) if t is current);self.revision+=1;self.refresh_queue();self.save_session();self.room_local_intent()
        def remove():
            self.revision+=1
            if index==self.index:
                self.desired_playing=False;self.player.stop();self.player.setSource(QUrl());self.epoch+=1
            self.queue.pop(index)
            if index<self.index:self.index-=1
            self.index=max(0,min(self.index,len(self.queue)-1));self.refresh_queue();self.save_session();self.room_local_intent()
        menu.addAction("Play now",lambda:self.play_index(index));menu.addAction("Move up",lambda:move(-1));menu.addAction("Move down",lambda:move(1));menu.addAction("Remove from queue",remove)
        menu.exec(listing.mapToGlobal(point))

    def position_changed(self,position):
        if self.loaded_epoch!=self.epoch:return
        if not self.seek.isSliderDown():self.seek.setValue(position)
        self.elapsed.setText(clock(position))
        if not self.mini_seek.isSliderDown():self.mini_seek.setValue(position)
        if self.current() and self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState and time.monotonic()-self.last_history>5:
            self.last_history=time.monotonic();self.store.history(self.current(),position);self.save_session()

    def duration_changed(self,duration):
        self.seek.setRange(0,max(1,duration));self.mini_seek.setRange(0,max(1,duration));self.remaining.setText(clock(duration) if duration>0 else "—")

    def playback_changed(self,state):
        playing=state==QMediaPlayer.PlaybackState.PlayingState;self.update_play_button()
        if playing and self.current() and self.loaded_epoch==self.epoch:self.store.history(self.current(),self.player.position())

    def tick(self):
        if self.store.setting('theme','dark')=='system' and self.effective_theme()!=getattr(self,'_applied_theme',None):
            self.apply_theme('system')
        if self.sleep_at is not None:
            remaining=self.sleep_at-time.monotonic()
            if remaining<=0:
                self.cancel_sleep();self.desired_playing=False;self.player.pause();self.preview_player.stop();self.update_play_button();self.room_local_intent()
            else:
                self.sleep_button.setText(clock(round(remaining*1000)))
                if remaining<8:
                    if self.sleep_original_volume is None:self.sleep_original_volume=self.audio.volume()
                    self.audio.setVolume(self.sleep_original_volume*remaining/8)

    def cancel_sleep(self):
        self.sleep_at=None;self.sleep_end_of_track=False
        if hasattr(self,'sleep_button'):self.sleep_button.setText(self.tr('sleep_timer'))
        if self.sleep_original_volume is not None:
            self.audio.setVolume(self.sleep_original_volume);self.sleep_original_volume=None

    def start_sleep(self,minutes=None,end=False):
        if not end and (type(minutes) is not int or not 1<=minutes<=1440):
            raise ValueError('Sleep minutes must be between 1 and 1440')
        self.cancel_sleep()
        if end:self.sleep_end_of_track=True;self.sleep_button.setText(self.tr('end_of_track'))
        else:self.sleep_at=time.monotonic()+minutes*60;self.sleep_button.setText(clock(minutes*60000))

    def sleep_timer(self):
        dialog=QDialog(self);dialog.setWindowTitle(self.tr('sleep_timer'));layout=QVBoxLayout(dialog)
        for minutes in (5,15,30,45,60):
            layout.addWidget(button(self.tr('minutes_n',minutes),lambda checked=False,minutes=minutes:(self.start_sleep(minutes),dialog.accept())))
        layout.addWidget(button(self.tr('end_of_track'),lambda:(self.start_sleep(end=True),dialog.accept())))
        def custom():
            minutes,ok=QInputDialog.getInt(dialog,self.tr('sleep_timer'),self.tr('minutes_n',1),30,1,1440)
            if ok:self.start_sleep(minutes);dialog.accept()
        layout.addWidget(button(self.tr('custom'),custom))
        if self.sleep_at is not None or self.sleep_end_of_track:
            layout.addWidget(button(self.tr('turn_off'),lambda:(self.cancel_sleep(),dialog.accept())))
        layout.addWidget(button(self.tr('close'),dialog.reject));dialog.exec()

    def clear_history(self):
        if QMessageBox.question(self,"Clear listening history?","Remove history entries only? Likes, playlists, queue and downloads remain.")==QMessageBox.StandardButton.Yes:
            self.store.remove_history();self.navigate("Listen Again")

    def studio_page(self):
        self.reset_content(self.tr("studio_title"),self.tr("studio_intro"))
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
        for text,delta,description in (("↑",-1,"Move selected clip up"),("↓",1,"Move selected clip down")):
            move=button(text,lambda checked=False,delta=delta:self.move_clip(clips.currentRow(),delta));move.setToolTip(description);move.setAccessibleName(description);buttons.addWidget(move)
        buttons.addWidget(button("Remove clip",lambda:self.remove_clip(clips.currentRow())))
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

    def check_updates(self):
        self.notify("Checking the desktop release channel…")
        def checked(update):
            if update is None:self.notify("No newer compatible signed desktop release was found.");return
            if QMessageBox.question(self,"Dkord desktop update",f"Download version {update.version} for {update.platform}?\n{update.size/1024**2:.1f} MiB. Your user-data folder is retained.")!=QMessageBox.StandardButton.Yes:return
            def ready(file):
                if QMessageBox.question(self,"Verified update ready","Open the matching native installer now? No release-page browsing is required.")==QMessageBox.StandardButton.Yes:
                    try:self.restart_after_close=self.updater.install(update,file);self.close()
                    except Exception as e:self.notify(str(e))
            self.run(lambda event,progress:self.updater.download(update,event,lambda done,total:progress((done,total))),ready,
                     progress=lambda value:self.notify(f"Desktop update · {value[0]/1024**2:.1f}/{value[1]/1024**2:.1f} MiB"))
        self.run(lambda event,progress:self.updater.check(),checked)

    def closeEvent(self,event):
        self.closing=True;self.timer.stop();self.desired_playing=False;self.cancel_sleep()
        self.rooms.close();self.artwork_cache.close();self.cancel_home()
        if self.full_player:self.full_player.hide()
        if self.video_window:self.video_window.close()
        self.save_session();self.store.set_setting("volume",self.audio.volume());self.store.set_setting("speed",self.speed.value());self.store.set_setting("repeat",self.repeat.currentIndex());self.store.set_setting("shuffle",self.shuffle.isChecked())
        for task in list(self.tasks):task.cancel.set()
        for id in list(self.library.active):self.library.pause(id)
        self.player.stop();self.player.setSource(QUrl());self.preview_player.stop();self.proxy.close();event.accept()
