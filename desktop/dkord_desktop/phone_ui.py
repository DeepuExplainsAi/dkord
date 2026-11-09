"""Responsive native rendering of Dkord's PHONE experience.

Same five destinations, red/near-black Material palette, shelf/track components,
Library tools, mini-player and full-player tabs. Only the layout changes: rail on
PC, bottom navigation at compact widths. Qt5/real Win32 and Qt6 share this tree.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import random
import sys
import time

from .qt import (sip, Qt, QtCore, QtWidgets, QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
                 QScrollArea, QLineEdit, QComboBox, QDockWidget, QListWidget, QListWidgetItem,
                 QPushButton, QLabel, QCheckBox, QDoubleSpinBox, QSlider, QFormLayout, QDialog,
                 QMenu, QMessageBox, QInputDialog, QFileDialog, QFont, QFontDatabase, QIcon, QSize, QTimer, QThreadPool)
from . import __version__
from .experience import contract, text, branding, stylesheet, palette
from .widgets import label, button, icon, ElideLabel
from .artwork import ArtworkCache, Cover
from .catalogue import Page, Shelf
from .models import Track
from .provider import Entry, Provider
from .lyrics import LyricsRepository
from .releases import NewReleasesRepository, ReleaseDatesUnavailable, CATEGORIES, WINDOWS
from .room_view import RoomBridge, RoomPanel

PAGES = {'HOME': 'Home', 'SEARCH': 'Search', 'LISTEN': 'Listen Again', 'LIBRARY': 'Library', 'DOWNLOADS': 'Downloads'}
NAV_ICONS = {'HOME': 'home', 'SEARCH': 'search', 'LISTEN': 'history', 'LIBRARY': 'library_music', 'DOWNLOADS': 'file_download'}


class PhoneExperience:
    def tr(self, key, *args):
        return text(key, self.store.setting('language', 'en'), *args)

    def effective_theme(self):
        mode = self.store.setting('theme', 'dark')
        if mode == 'system':
            return 'dark' if QApplication.instance().palette().window().color().lightness() < 128 else 'light'
        return mode

    def apply_theme(self, mode):
        self.store.set_setting('theme', mode)
        self._applied_theme = self.effective_theme()
        self.setStyleSheet(stylesheet(self._applied_theme))
        self.refresh_icons()
        self.update()

    def refresh_icons(self):
        if not hasattr(self, 'nav_buttons'):
            return
        p = palette(self.effective_theme())
        for item in contract()['navigation']:
            page = PAGES[item['id']]
            for widget in (self.nav_buttons[page], self.bottom_buttons[page]):
                widget.setIcon(icon(NAV_ICONS[item['id']], p['onSurface']))
        for widget, name in ((self.settings_button, 'settings'), (self.together_button, 'groups'), (self.back_button, 'arrow_back'),
                             (self.previous_button, 'skip_previous'), (self.next_button, 'skip_next')):
            widget.setIcon(icon(name, p['onSurface']))
        self.play_button.setIcon(icon('pause' if self.desired_playing else 'play_arrow', p['onSurface']))
        for widget in self.findChildren(QPushButton,'track-more'):
            if widget.property('iconOnly'):widget.setIcon(icon('more_vert',p['onSurface']))

    def build_shell(self):
        app = QApplication.instance(); app.setProperty('dkord-language', self.store.setting('language', 'en'))
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
        for path in (root/'assets/fonts').glob('*.ttf'):
            QFontDatabase.addApplicationFont(str(path))
        self.setFont(QFont('Roboto', 11))
        self.artwork_cache = ArtworkCache(self)
        self.lyrics_repository = LyricsRepository(); self.full_player = None; self.video_window = None
        self.releases_repository = NewReleasesRepository.from_provider(self.provider)
        self.release_expanded = False; self.release_window = 'LAST_7_DAYS'; self.release_category = 'ALL'
        self.release_task = None; self.release_epoch = 0; self.release_tracks = None; self.release_error = None
        self.home_pool = QThreadPool(self); self.home_pool.setMaxThreadCount(2)
        self.home_tasks = set(); self.home_epoch = 0; self.home_data = None; self.home_error = None
        self.home_extras = {}; self.home_chip = None; self.home_loaded_at = 0
        self.collection_tracks = []; self.collection_page = None; self.collection_entry = None; self.collection_loading = False
        self.back_stack = []; self._going_back = False
        self.setWindowTitle(f'Dkord — {__version__}')
        self.setWindowIcon(QIcon(str(root/'assets/dkord.svg')))
        self.resize(1360, 850); self.setMinimumSize(420, 640)
        container = QWidget(); self.setCentralWidget(container)
        self.outer_layout = outer = QVBoxLayout(container); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        body = QWidget(); row = QHBoxLayout(body); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0); outer.addWidget(body, 1)
        self.sidebar = QFrame(); self.sidebar.setObjectName('sidebar')
        nav = QVBoxLayout(self.sidebar); nav.setContentsMargins(12, 20, 12, 16); nav.setSpacing(8)
        self.brand = label('Dkord', 'brand'); nav.addWidget(self.brand); nav.addSpacing(14)
        self.nav_buttons = {}; self.bottom_buttons = {}
        for item in contract()['navigation']:
            page = PAGES[item['id']]
            b = button(self.tr(item['label']), lambda checked=False, page=page: self.navigate(page)); b.setObjectName('nav')
            b.setCheckable(True); b.setIconSize(QSize(24, 24)); b.setAccessibleName(self.tr(item['label']))
            self.nav_buttons[page] = b; nav.addWidget(b)
        nav.addStretch(); row.addWidget(self.sidebar)
        self.middle = QWidget(); self.center = center = QVBoxLayout(self.middle)
        center.setContentsMargins(24, 16, 24, 12); center.setSpacing(12); row.addWidget(self.middle, 1)
        top = QHBoxLayout()
        self.back_button = button('', self.go_back); self.back_button.setFixedSize(40, 40); self.back_button.setAccessibleName(self.tr('back')); top.addWidget(self.back_button)
        self.heading = label(self.tr('tab_home'), 'pageTitle'); top.addWidget(self.heading, 1)
        self.together_button = button('', lambda: self.navigate('Listen Together')); self.together_button.setObjectName('global-listen-together'); self.together_button.setFixedSize(42, 42)
        self.together_button.setToolTip(self.tr('listen_together')); self.together_button.setAccessibleName(self.tr('listen_together')); top.addWidget(self.together_button)
        self.settings_button = button('', lambda: self.navigate('Settings')); self.settings_button.setFixedSize(42, 42)
        self.settings_button.setToolTip(self.tr('settings')); self.settings_button.setAccessibleName(self.tr('settings')); top.addWidget(self.settings_button); center.addLayout(top)
        self.search_box = QWidget(); search = QVBoxLayout(self.search_box); search.setContentsMargins(0, 0, 0, 0); search.setSpacing(6)
        query_row = QHBoxLayout()
        self.query = QLineEdit(); self.query.setObjectName('global-search'); self.query.setPlaceholderText(self.tr('search_hint')); self.query.returnPressed.connect(self.search)
        self.scope = QComboBox(self.search_box); self.scope.addItems(list(Provider.scopes)); self.scope.hide()
        query_row.addWidget(self.query, 1); query_row.addWidget(button(self.tr('search_submit'), self.search, True)); search.addLayout(query_row)
        self.scope_labels = dict(zip(Provider.scopes, ('songs','albums','artists','playlists','search_music_videos','search_videos','search_all')))
        self.scope_buttons = {}
        filters = QScrollArea(); filters.setWidgetResizable(True); filters.setFixedHeight(54)
        filters.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); filters.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        filter_content = QWidget(); filter_row = QHBoxLayout(filter_content); filter_row.setContentsMargins(0,0,0,0)
        for value in Provider.scopes:
            chip = button(self.tr(self.scope_labels[value]), lambda checked=False,value=value:self.choose_scope(value))
            chip.setCheckable(True); chip.setChecked(value == self.scope.currentText()); chip.setObjectName('search-filter'); self.scope_buttons[value] = chip; filter_row.addWidget(chip)
        filter_row.addStretch(); filters.setWidget(filter_content); search.addWidget(filters); center.addWidget(self.search_box)
        self.scope.currentTextChanged.connect(lambda value: [widget.setChecked(name == value) for name,widget in self.scope_buttons.items()])
        self.subtitle = label('', 'muted'); center.addWidget(self.subtitle)
        self.content_scroll = QScrollArea(); self.content_scroll.setWidgetResizable(True)
        self.content = QWidget(); self.content_layout = QVBoxLayout(self.content); self.content_layout.setContentsMargins(0, 0, 0, 0); self.content_layout.setSpacing(16)
        self.content_scroll.setWidget(self.content); center.addWidget(self.content_scroll, 1)
        self.build_player(outer)
        self.bottom_nav = QFrame(); self.bottom_nav.setObjectName('bottom-navigation'); bottom = QHBoxLayout(self.bottom_nav); bottom.setContentsMargins(4, 0, 4, 0); bottom.setSpacing(0)
        for item in contract()['navigation']:
            page = PAGES[item['id']]
            b = QtWidgets.QToolButton(); b.setText(self.tr(item['label'])); b.setObjectName('bottom-nav'); b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon); b.setIconSize(QSize(24, 24)); b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
            b.clicked.connect(lambda checked=False, page=page: self.navigate(page)); self.bottom_buttons[page] = b; bottom.addWidget(b, 1)
        outer.addWidget(self.bottom_nav)
        self.queue_dock = QDockWidget(self.tr('queue'), self); self.queue_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.queue_list = QListWidget(); self.queue_list.itemDoubleClicked.connect(lambda item: self.play_index(self.queue_list.row(item)))
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.queue_list.customContextMenuRequested.connect(self.queue_menu)
        self.queue_dock.setWidget(self.queue_list); self.queue_dock.setMinimumWidth(240)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.queue_dock); self.queue_dock.hide()
        self.rooms = RoomBridge(self)
        self.setup_suggestions()
        self.adjust_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bottom_nav'):
            self.adjust_layout()

    def adjust_layout(self):
        compact = self.width() < 800
        rail = 800 <= self.width() < 1120
        self.sidebar.setVisible(not compact); self.sidebar.setFixedWidth(84 if rail else 208)
        self.bottom_nav.setVisible(compact); self.brand.setVisible(not rail)
        self.center.setContentsMargins(16 if compact or rail else 24, 16, 16 if compact or rail else 24, 12)
        for item in contract()['navigation']:
            widget = self.nav_buttons[PAGES[item['id']]]
            widget.setText('' if rail else self.tr(item['label'])); widget.setToolTip(self.tr(item['label']))
        if compact and hasattr(self, 'queue_dock'):
            self.queue_dock.hide()
        self.scope.setMinimumWidth(88 if compact else 120)

    def update_play_button(self):
        if hasattr(self, 'play_button'):
            self.play_button.setText('')
            self.play_button.setIcon(icon('pause' if self.desired_playing else 'play_arrow', palette(self.effective_theme())['onSurface']))
            self.play_button.setAccessibleName(self.tr('pause' if self.desired_playing else 'play'))

    def select_navigation(self, page):
        parent = page if page in self.nav_buttons else 'Library' if page in ('Library', 'Playlists', 'Liked songs', 'Mashup Studio', 'Listen Together', 'Catalogue') else None
        for name, widget in self.nav_buttons.items():
            widget.setChecked(name == parent); self.bottom_buttons[name].setChecked(name == parent)
        self.search_box.setVisible(page == 'Search'); self.back_button.setVisible(page not in PAGES.values())

    def navigate(self, page, fetch=True):
        previous = self.page
        if previous != page and not self._going_back:
            self.back_stack.append(previous)
            self.back_stack = self.back_stack[-30:]
        if previous == 'Search' and page != 'Search':
            self.search_epoch += 1; self.suggestion_epoch += 1; self.suggestion_timer.stop()
            if self.search_task: self.search_task.cancel.set()
            if self.more_task: self.more_task.cancel.set(); self.more_task = None
        self.route_epoch += 1; self.page = page; self.collection_tracks = []
        if previous == 'Home' and page != 'Home':
            self.cancel_home()
        self.select_navigation(page)
        if page == 'Home':
            self.home_page(fetch)
        elif page in ('Library', 'Playlists'):
            self.library_page()
        elif page == 'Search':
            self.reset_content(self.tr('tab_search')); self.saved_queries()
        elif page == 'Listen Together':
            self.reset_content(self.tr('listen_together')); self.content_layout.addWidget(RoomPanel(self))
        elif page == 'Settings':
            self.settings_page()
        else:
            self._legacy_navigate(page, fetch)

    def choose_scope(self, value):
        self.scope.setCurrentText(value)
        if self.query.text().strip() and self.page == 'Search':
            self.search()

    def focus_search(self):
        self.navigate('Search'); self.query.setFocus()

    def go_back(self):
        target = self.back_stack.pop() if self.back_stack else 'Home'
        self._going_back = True
        try:
            self.navigate(target)
        finally:
            self._going_back = False

    def cancel_home(self):
        self.home_epoch += 1
        for task in tuple(self.home_tasks):
            task.cancel.set()
        self.home_tasks.clear()
        self.cancel_releases()

    def home_page(self, fetch=True, refresh=False):
        if refresh or (self.home_loaded_at and time.monotonic()-self.home_loaded_at > 900):
            self.cancel_home(); self.home_data = None; self.home_extras = {}; self.home_error = None
        self.render_home()
        if not fetch:
            return
        if self.release_expanded:
            self.load_releases(refresh)
        owner = self.home_epoch
        if self.home_data is None:
            def ready(page):
                if owner == self.home_epoch and self.page == 'Home':
                    self.home_data = page; self.home_loaded_at = time.monotonic(); self.home_error = None; self.render_home()
            def failed(_):
                if owner == self.home_epoch and self.page == 'Home':
                    self.home_error = self.tr('err_network'); self.render_home()
            def load(cancel, progress):
                if hasattr(self.provider, 'home_page'):
                    return self.provider.home_page(self.home_chip)
                return Page(shelves=(Shelf(self.tr('tab_home'), tuple(self.provider.home())),))
            self.home_tasks.add(self.run(load, ready, failed=failed, background=True))
        if self.home_chip is None:
            for index, section in enumerate(contract()['curated']):
                if index not in self.home_extras:
                    self.load_curated(index, section, owner)

    def load_curated(self, index, section, owner):
        def ready(entries):
            if owner == self.home_epoch and self.page == 'Home':
                self.home_extras[index] = Shelf(section['title'], tuple(entries[:15]), section['query']); self.render_home()
        self.home_tasks.add(self.run(lambda cancel, progress: self.provider.search(section['query'], 'Songs', 20),
                                     ready, failed=lambda _: None, background=True))

    def select_chip(self, chip):
        if chip == self.home_chip:
            return
        self.cancel_home(); self.home_chip = chip; self.home_data = None; self.home_error = None; self.home_page()

    def render_home(self):
        scroll = self.content_scroll.verticalScrollBar().value()
        self.reset_content(self.tr('tab_home'))
        tools = QWidget(); row = QHBoxLayout(tools); row.setContentsMargins(0, 0, 0, 0)
        chips = ((None,) + self.home_data.chips) if self.home_data else (None,)
        chip_scroll = QScrollArea(); chip_scroll.setWidgetResizable(True); chip_scroll.setFixedHeight(54)
        chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chip_content = QWidget(); chip_row = QHBoxLayout(chip_content); chip_row.setContentsMargins(0, 0, 0, 0)
        for chip in chips:
            b = button(branding(chip.title, self.store.setting('language','en')) if chip else self.tr('all'), lambda checked=False, chip=chip: self.select_chip(chip))
            b.setCheckable(True); b.setChecked(chip == self.home_chip); chip_row.addWidget(b)
        chip_row.addStretch(); chip_scroll.setWidget(chip_content); row.addWidget(chip_scroll, 1)
        refresh = button('', lambda: self.home_page(refresh=True)); refresh.setIcon(icon('refresh', palette(self.effective_theme())['onSurface'])); refresh.setToolTip(self.tr('retry')); row.addWidget(refresh)
        self.content_layout.addWidget(tools)
        if self.home_chip is None:
            self.release_section()
            recent = self.store.library('history')[:15]
            if recent:
                self.add_shelf(Shelf(self.tr('recently_played'), tuple(Entry('song', t.id, t.title, t.artist, t, t.thumbnail) for t in recent)))
        if self.home_data:
            for shelf in self.home_data.shelves:
                self.add_shelf(shelf)
        elif self.home_error:
            self.content_layout.addWidget(label(self.home_error, 'muted'))
            self.content_layout.addWidget(button(self.tr('retry'), lambda: self.home_page(refresh=True)))
        else:
            self.content_layout.addWidget(label(self.tr('loading'), 'muted'))
        if self.home_chip is None:
            for index in sorted(self.home_extras):
                if self.home_extras[index].items:
                    self.add_shelf(self.home_extras[index])
        self.content_layout.addStretch()
        QTimer.singleShot(0, lambda: self.content_scroll.verticalScrollBar().setValue(scroll) if self.page == 'Home' else None)

    def add_shelf(self, shelf, target=None):
        group = QWidget(); layout = QVBoxLayout(group); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(10)
        header = QHBoxLayout(); title = label(branding(shelf.title, self.store.setting('language','en')))
        title.setStyleSheet('font-size:21px;font-weight:700;'); header.addWidget(title, 1)
        tracks = [entry.track for entry in shelf.items if entry.track]
        if tracks:
            header.addWidget(button(self.tr('play_all'), lambda: self.play_queue(tracks)))
        layout.addLayout(header)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFixedHeight(212); scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(); row = QHBoxLayout(content); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(16)
        for entry in shelf.items:
            card = QWidget(); card.setFixedWidth(140); body = QVBoxLayout(card); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(6)
            if entry.kind == 'mood':
                b = button(entry.title, lambda checked=False, entry=entry: self.open_entry(entry)); b.setMinimumHeight(64); body.addWidget(b)
            else:
                cover = Cover(self.artwork_cache, entry.thumbnail or (entry.track.thumbnail if entry.track else None), 140, entry.kind == 'artist',
                              lambda entry=entry, hint=shelf.radio_hint: self.shelf_entry(entry, hint)); body.addWidget(cover)
                title = label(entry.title); title.setMaximumHeight(38); body.addWidget(title)
                subtitle = ElideLabel(entry.subtitle); subtitle.setObjectName('muted'); body.addWidget(subtitle)
            body.addStretch()
            if entry.track:
                card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                card.customContextMenuRequested.connect(lambda point, card=card, track=entry.track: self.track_menu(track, card.mapToGlobal(point)))
            row.addWidget(card)
        row.addStretch(); scroll.setWidget(content); layout.addWidget(scroll); (target if target is not None else self.content_layout).addWidget(group)

    def shelf_entry(self, entry, hint):
        if entry.track:
            self.play_track(entry.track, related=True, context_hint=hint)
        else:
            self.open_entry(entry)

    def library_page(self):
        self.reset_content(self.tr('tab_library'))
        self.content_layout.addWidget(label(self.tr('listen_together'), 'pageTitle'))
        room = button(self.tr('room_anywhere_title')+'  ›', lambda: self.navigate('Listen Together')); room.setObjectName('library-listen-together')
        self.content_layout.addWidget(room); self.content_layout.addWidget(label(self.tr('room_anywhere_hint'), 'muted'))
        for key, page, symbol in (('studio_title','Mashup Studio','library_music'), ('liked_songs','Liked songs','favorite'), ('recently_played','Listen Again','history')):
            b = button(self.tr(key), lambda checked=False, page=page: self.navigate(page)); b.setIcon(icon(symbol, palette(self.effective_theme())['primary'])); self.content_layout.addWidget(b)
        header = QWidget(); row = QHBoxLayout(header); row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label(self.tr('my_playlists'), 'pageTitle'), 1)
        row.addWidget(button('+', self.new_playlist)); row.addWidget(button(self.tr('import_playlists'), self.import_library)); row.addWidget(button(self.tr('export_playlists'), self.export_library)); self.content_layout.addWidget(header)
        listing = QListWidget(); listing.setObjectName('library-playlists'); listing.setMinimumHeight(180)
        for playlist in self.store.playlists():
            item = QListWidgetItem(playlist['name']+'\n'+str(len(playlist['data']))+' '+self.tr('songs').lower()); item.setData(Qt.ItemDataRole.UserRole, playlist); item.setSizeHint(QSize(0, 68)); listing.addItem(item)
        listing.itemDoubleClicked.connect(lambda item: self.browse_result(item.data(Qt.ItemDataRole.UserRole)['name'], [Track.parse(t) for t in item.data(Qt.ItemDataRole.UserRole)['data']]))
        listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def context(point):
            item = listing.itemAt(point)
            if not item:
                return
            playlist = item.data(Qt.ItemDataRole.UserRole); menu = QMenu(self)
            def rename():
                name, ok = QInputDialog.getText(self, self.tr('rename'), self.tr('name'), text=playlist['name'])
                if ok and name.strip():
                    self.store.save_playlist(name, [Track.parse(t) for t in playlist['data']], playlist['id']); self.library_page()
            def delete():
                if QMessageBox.question(self, self.tr('delete'), playlist['name']) == QMessageBox.StandardButton.Yes:
                    self.store.delete_playlist(playlist['id']); self.library_page()
            menu.addAction(self.tr('rename'), rename); menu.addAction(self.tr('export_playlists'), lambda: self.export_library(playlist)); menu.addAction(self.tr('delete'), delete)
            menu.exec(listing.mapToGlobal(point))
        listing.customContextMenuRequested.connect(context); self.content_layout.addWidget(listing, 1)

    def playlists_page(self):
        self.library_page()

    def cancel_releases(self):
        self.release_epoch += 1
        if self.release_task:
            self.release_task.cancel.set(); self.release_task = None

    def new_releases_page(self):
        # Phone's inline expandable Home section, not a different raw browse page.
        self.release_expanded = not self.release_expanded
        if self.release_expanded:
            self.load_releases()
        else:
            self.cancel_releases(); self.render_home()

    def select_release(self, value, category=False):
        if category:
            self.release_category = value
        else:
            self.release_window = value
        self.load_releases()

    def load_releases(self, refresh=False):
        self.cancel_releases(); owner = self.release_epoch
        window, category = self.release_window, self.release_category
        self.release_tracks = None; self.release_error = None; self.render_home()
        def load(cancel, progress):
            try:
                return self.releases_repository.songs(window, category, refresh, cancel), None
            except ReleaseDatesUnavailable:
                return [], 'release_dates_unavailable'
        def ready(result):
            if owner == self.release_epoch and self.page == 'Home' and self.release_expanded:
                self.release_task = None; self.release_tracks, self.release_error = result; self.render_home()
        def failed(_):
            if owner == self.release_epoch and self.page == 'Home' and self.release_expanded:
                self.release_task = None; self.release_error = 'err_network'; self.render_home()
        self.release_task = self.run(load, ready, failed=failed)

    def release_section(self):
        toggle = button(self.tr('new_releases') + ('  ⌃' if self.release_expanded else '  ⌄'), self.new_releases_page)
        toggle.setObjectName('new-releases'); toggle.setCheckable(True); toggle.setChecked(self.release_expanded)
        toggle.setAccessibleDescription(self.tr('section_expanded' if self.release_expanded else 'section_collapsed'))
        self.content_layout.addWidget(toggle)
        if not self.release_expanded:
            return
        panel = QWidget(); panel.setObjectName('new-releases-section'); layout = QVBoxLayout(panel); layout.setContentsMargins(0,0,0,0)
        for values, selected, category in ((CATEGORIES, self.release_category, True),(WINDOWS, self.release_window, False)):
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFixedHeight(54)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            content = QWidget(); row = QHBoxLayout(content); row.setContentsMargins(0,0,0,0)
            for value in values:
                key = 'choliwood_name' if value == 'CHOLIWOOD' else ('release_'+value.lower() if category else value.lower())
                choice = button(self.tr(key), lambda checked=False, value=value, category=category:self.select_release(value, category))
                choice.setCheckable(True); choice.setChecked(value == selected); choice.setObjectName('release-'+value.lower()); row.addWidget(choice)
            row.addStretch(); scroll.setWidget(content); layout.addWidget(scroll)
        if self.release_error:
            layout.addWidget(label(self.tr(self.release_error), 'muted'))
            layout.addWidget(button(self.tr('retry'), lambda:self.load_releases(True)))
        elif self.release_tracks is None:
            layout.addWidget(label(self.tr('loading'),'muted'))
        elif not self.release_tracks:
            layout.addWidget(label(self.tr('no_new_songs'),'muted'))
        else:
            self.add_shelf(Shelf('', tuple(Entry('song',t.id,t.title,t.artist,t,t.thumbnail) for t in self.release_tracks)), layout)
        self.content_layout.addWidget(panel)

    def open_catalogue(self, entry):
        self.route_epoch += 1; route = self.route_epoch
        self.page = 'Catalogue'; self.collection_entry = entry; self.collection_page = None; self.collection_tracks = []
        self.select_navigation('Catalogue'); self.reset_content(entry.title, self.tr('loading'))
        if hasattr(self.provider, 'catalogue_page'):
            self.run(lambda cancel, progress: self.provider.catalogue_page(entry),
                     lambda page: self.render_catalogue(page, entry) if route == self.route_epoch else None)
        else:
            self.run(lambda cancel, progress: self.provider.browse(entry), lambda result: self.browse_result(*result) if route == self.route_epoch else None)

    def render_catalogue(self, page, entry):
        self.collection_page, self.collection_entry = page, entry; self.collection_tracks = list(page.tracks)
        self.reset_content(page.title or entry.title, page.subtitle)
        header = QWidget(); row = QHBoxLayout(header); row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(Cover(self.artwork_cache, page.thumbnail or entry.thumbnail, 160, entry.kind == 'artist'))
        tools = QVBoxLayout(); tools.addWidget(label(page.title or entry.title, 'pageTitle'))
        if page.tracks:
            tools.addWidget(button(self.tr('play_all'), lambda: self.play_queue(list(self.collection_tracks)), True))
            tools.addWidget(button(self.tr('shuffle'), lambda: self.play_queue(random.sample(self.collection_tracks, len(self.collection_tracks)))))
            tools.addWidget(button(self.tr('download'), lambda: self.choose_download(list(self.collection_tracks))))
        tools.addStretch(); row.addLayout(tools, 1); self.content_layout.addWidget(header)
        if page.tracks:
            self.song_table([Entry('song', t.id, t.title, t.artist, t, t.thumbnail) for t in page.tracks])
        for shelf in page.shelves:
            self.add_shelf(shelf)
        if page.continuation:
            self.content_layout.addWidget(button(self.tr('search_load_more'), self.more_catalogue))
        if not page.tracks and not page.shelves:
            self.content_layout.addWidget(label(self.tr('nothing_here'), 'muted'))

    def more_catalogue(self):
        page, entry, route = self.collection_page, self.collection_entry, self.route_epoch
        if self.collection_loading or not page or not page.continuation:
            return
        self.collection_loading = True
        def ready(next_page):
            if route != self.route_epoch:
                return
            known = {t.id for t in page.tracks}; tracks = tuple(page.tracks) + tuple(t for t in next_page.tracks if t.id not in known)
            self.render_catalogue(replace(page, tracks=tracks, shelves=page.shelves+next_page.shelves, continuation=next_page.continuation), entry)
        self.run(lambda cancel, progress: self.provider.catalogue_page(continuation=page.continuation), ready,
                 finished=lambda: setattr(self, 'collection_loading', False))

    def build_player(self, outer):
        frame = QFrame(); frame.setObjectName('player'); self.mini_player = frame
        body = QVBoxLayout(frame); body.setContentsMargins(16, 10, 16, 0); body.setSpacing(6)
        top = QHBoxLayout(); top.setSpacing(12)
        self.mini_cover = Cover(self.artwork_cache, side=44, action=self.show_full_player); top.addWidget(self.mini_cover)
        info = QVBoxLayout(); info.setSpacing(3)
        self.now = ElideLabel(self.tr('nothing_playing')); self.now_artist = ElideLabel(''); self.now_artist.setObjectName('muted')
        self.now.setMaximumWidth(10000); self.now_artist.setMaximumWidth(10000); info.addWidget(self.now); info.addWidget(self.now_artist); top.addLayout(info, 1)
        expand = button('', self.show_full_player); expand.setIcon(icon('expand_more')); expand.setToolTip(self.tr('room_open_player')); expand.setAccessibleName(self.tr('room_open_player')); top.addWidget(expand)
        self.previous_button = button('', lambda: self.next_track(-1)); self.previous_button.setFixedSize(40, 40); self.previous_button.setAccessibleName(self.tr('previous'))
        self.play_button = button('', self.toggle); self.play_button.setObjectName('play-toggle'); self.play_button.setFixedSize(44, 44); self.play_button.setAccessibleName(self.tr('play'))
        self.next_button = button('', lambda: self.next_track(1)); self.next_button.setFixedSize(40, 40); self.next_button.setAccessibleName(self.tr('next'))
        top.addWidget(self.previous_button); top.addWidget(self.play_button); top.addWidget(self.next_button); body.addLayout(top)
        self.mini_seek = QSlider(Qt.Orientation.Horizontal); self.mini_seek.setRange(0, 1); self.mini_seek.setMaximumHeight(8)
        self.mini_seek.sliderReleased.connect(lambda: self.user_seek(self.mini_seek.value())); body.addWidget(self.mini_seek); outer.addWidget(frame)
        # Full player controls are created once and reparented into its dialog.
        self.player_controls = QWidget(self); self.player_controls.setObjectName('full-player-controls'); controls = QVBoxLayout(self.player_controls); controls.setContentsMargins(0, 0, 0, 0)
        line = QHBoxLayout(); self.elapsed = label('0:00', 'muted'); self.remaining = label('—', 'muted')
        self.seek = QSlider(Qt.Orientation.Horizontal); self.seek.setObjectName('playback-seek'); self.seek.setRange(0, 1); self.seek.setEnabled(False)
        self.seek.sliderReleased.connect(lambda: self.user_seek(self.seek.value())); line.addWidget(self.elapsed); line.addWidget(self.seek, 1); line.addWidget(self.remaining); controls.addLayout(line)
        options = QHBoxLayout()
        self.shuffle = QCheckBox(self.tr('shuffle')); self.shuffle.setChecked(bool(self.store.setting('shuffle', False))); self.shuffle.toggled.connect(self.shuffle_queue); options.addWidget(self.shuffle)
        self.repeat = QComboBox(); self.repeat.addItems([self.tr('repeat_off'), self.tr('repeat_one'), self.tr('repeat_all')]); self.repeat.setMinimumWidth(116); self.repeat.setCurrentIndex(int(self.store.setting('repeat', 0))); options.addWidget(self.repeat)
        self.speed = QDoubleSpinBox(); self.speed.setRange(.5, 2); self.speed.setSingleStep(.05); self.speed.setSuffix('×'); self.speed.setValue(float(self.store.setting('speed', 1))); self.speed.setFixedWidth(92)
        self.speed.valueChanged.connect(self.player.setPlaybackRate); self.player.setPlaybackRate(self.speed.value()); options.addWidget(self.speed); options.addStretch(); controls.addLayout(options)
        secondary = QHBoxLayout(); self.sleep_button = button(self.tr('sleep_timer'), self.sleep_timer); secondary.addWidget(self.sleep_button); secondary.addStretch()
        volume = QSlider(Qt.Orientation.Horizontal); volume.setRange(0, 100); volume.setValue(int(self.audio.volume()*100)); volume.setFixedWidth(90)
        volume.setAccessibleName(self.tr('volume')); volume.valueChanged.connect(lambda value: self.audio.setVolume(value/100)); secondary.addWidget(volume); controls.addLayout(secondary)
        self.player_controls.hide()

    def show_full_player(self, tab=0):
        if not self.current():
            self.notify(self.tr('room_choose_music')); return
        if self.full_player is None:
            from .player_view import FullPlayer
            self.full_player = FullPlayer(self); self.player_controls.show()
        self.full_player.tabs.setCurrentIndex(tab); self.full_player.show(); self.full_player.raise_(); self.full_player.activateWindow()

    def lyrics(self):
        self.show_full_player(1)

    def user_seek(self, position, user=True):
        position = max(0, int(position))
        if self.loaded_epoch == self.epoch:
            self.player.setPosition(position)
        else:
            self.pending_seek = position
        self.save_session()
        if user:
            self.room_local_intent()

    def room_local_intent(self):
        if hasattr(self, 'rooms') and self.rooms:
            self.rooms.user_intent()

    def settings_page(self):
        self.reset_content(self.tr('settings'))
        panel = QWidget(); form = QFormLayout(panel)
        language = QComboBox(); language.addItem(self.tr('language_english'), 'en'); language.addItem(self.tr('language_hindi'), 'hi'); language.setCurrentIndex(1 if self.store.setting('language', 'en') == 'hi' else 0)
        language.currentIndexChanged.connect(lambda index: self.change_language(language.itemData(index))); form.addRow(self.tr('app_language'), language)
        theme = QComboBox()
        for mode in ('system', 'light', 'dark', 'amoled'):
            theme.addItem(self.tr('theme_'+mode), mode)
        theme.setCurrentIndex(max(0, theme.findData(self.store.setting('theme', 'dark')))); theme.currentIndexChanged.connect(lambda index: self.apply_theme(theme.itemData(index))); form.addRow(self.tr('theme'), theme)
        quality = QComboBox(); quality.addItems(['high','medium','low']); quality.setCurrentText(self.store.setting('quality','high')); quality.currentTextChanged.connect(lambda value: self.store.set_setting('quality',value)); form.addRow(self.tr('audio_quality'),quality)
        autoplay = QCheckBox(self.tr('autoplay_hint')); autoplay.setChecked(self.store.setting('autoplay',True)); autoplay.toggled.connect(lambda value: self.store.set_setting('autoplay',value)); form.addRow(self.tr('autoplay'),autoplay)
        video = QCheckBox(self.tr('play_video')); video.setChecked(self.store.setting('video_enabled',False)); video.toggled.connect(lambda value: self.store.set_setting('video_enabled',value)); form.addRow(self.tr('video_playback'),video)
        form.addRow(self.tr('report_broken'),button(self.tr('report_broken'),self.copy_diagnostics))
        form.addRow('',label(self.tr('report_broken_hint'),'muted'))
        form.addRow(self.tr('app_update'),button(self.tr('check_update'),self.check_updates,True))
        form.addRow(self.tr('version'),label(__version__))
        self.content_layout.addWidget(panel)
        self.content_layout.addWidget(label(self.tr('about'),'pageTitle')); self.content_layout.addWidget(label(self.tr('about_text'))); self.content_layout.addStretch()

    def copy_diagnostics(self):
        from .platforms import platform_key
        track = self.current(); source = 'none' if track is None else 'local' if track.local else 'online'
        QApplication.clipboard().setText(self.diagnostics.report(__version__, platform_key(),
            QtCore.QT_VERSION_STR+' '+QtCore.PYQT_VERSION_STR, source))
        self.notify(self.tr('report_copied'))

    def change_language(self, language):
        self.store.set_setting('language', language); QApplication.instance().setProperty('dkord-language',language)
        for item in contract()['navigation']:
            page=PAGES[item['id']];self.nav_buttons[page].setText(self.tr(item['label']));self.bottom_buttons[page].setText(self.tr(item['label']))
        self.query.setPlaceholderText(self.tr('search_hint'))
        for name,widget in self.scope_buttons.items():widget.setText(self.tr(self.scope_labels[name]))
        self.adjust_layout(); self.navigate('Settings')

    def about(self):
        dialog=QDialog(self);dialog.setWindowTitle(self.tr('about'));dialog.resize(460,280);layout=QVBoxLayout(dialog)
        layout.addWidget(label('dKORD','brand'));layout.addWidget(label(self.tr('about_text')));layout.addStretch();layout.addWidget(button(self.tr('close'),dialog.accept));dialog.exec()

    def setup_suggestions(self):
        self.suggestion_epoch = 0
        self.suggestion_timer = QTimer(self); self.suggestion_timer.setSingleShot(True); self.suggestion_timer.setInterval(350)
        self.suggestion_timer.timeout.connect(self.fetch_suggestions)
        self.query.textEdited.connect(lambda _: self.suggestion_timer.start())
        self.suggestions = QtWidgets.QCompleter(self); self.suggestions.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.suggestions.setFilterMode(Qt.MatchFlag.MatchContains); self.query.setCompleter(self.suggestions)
        self.suggestions.activated[str].connect(lambda _: self.search())
        self.suggestion_model = QtCore.QStringListModel(self); self.suggestions.setModel(self.suggestion_model)

    def fetch_suggestions(self):
        query = ' '.join(self.query.text().split()); self.suggestion_epoch += 1; owner = self.suggestion_epoch
        if not query or not hasattr(self.provider,'suggestions'):
            self.suggestion_model.setStringList([]); return
        self.run(lambda cancel, progress: self.provider.suggestions(query),
                 lambda values: self.suggestion_model.setStringList(values) if owner == self.suggestion_epoch and query == ' '.join(self.query.text().split()) and not self.closing else None,
                 failed=lambda _: None)

    def show_video(self):
        if not self.store.setting('video_enabled',False):
            self.notify(self.tr('video_disabled')); return
        from .video_view import VideoPlayer
        if self.current():
            if self.video_window:
                self.video_window.close()
            self.video_window=VideoPlayer(self,self.current());self.video_window.show()
