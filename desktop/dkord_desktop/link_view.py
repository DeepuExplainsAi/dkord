"""Native counterpart of the phone's explicit YouTube-link page; never a browser embed."""
from __future__ import annotations

from .qt import sip, Qt, QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLineEdit
from .artwork import Cover
from .experience import palette
from .models import Track
from .widgets import label, button, icon
from .youtube_links import MAX_LINK_LENGTH, PROBLEM_KEYS, YouTubeLinkError, parse_youtube_link

LINK_PAGE = 'YouTube link'


class YouTubeLinkPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.route = window.route_epoch
        self.work = {'generation': 0, 'task': None, 'active': True}
        self.track = None
        self.loading = False
        self.setObjectName('youtube-link-page')
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(12)
        layout.addWidget(label(window.tr('youtube_link_hint'), 'muted'))
        layout.addWidget(label(window.tr('youtube_link_label')))
        self.input = QLineEdit(); self.input.setObjectName('youtube-link-input'); self.input.setMaxLength(MAX_LINK_LENGTH + 1)
        self.input.setPlaceholderText('https://youtu.be/…'); self.input.setAccessibleName(window.tr('youtube_link_label'))
        self.input.setClearButtonEnabled(True); self.input.setText(getattr(window, 'youtube_link_input', ''))
        self.input.textChanged.connect(self.typed); self.input.returnPressed.connect(self.resolve); layout.addWidget(self.input)
        layout.addWidget(label(window.tr('youtube_link_formats'), 'muted'))
        actions = QHBoxLayout()
        self.paste_button = button(window.tr('youtube_link_paste'), self.paste); self.paste_button.setObjectName('youtube-link-paste')
        self.resolve_button = button(window.tr('youtube_link_show'), self.resolve, True); self.resolve_button.setObjectName('youtube-link-resolve')
        self.resolve_button.setEnabled(bool(self.input.text().strip()))
        actions.addWidget(self.paste_button, 1); actions.addWidget(self.resolve_button, 1); layout.addLayout(actions)
        self.busy = QWidget(); busy = QHBoxLayout(self.busy); busy.setContentsMargins(0, 0, 0, 0)
        busy.addWidget(label(window.tr('youtube_link_loading'), 'muted'), 1)
        self.cancel_button = button(window.tr('cancel'), self.cancel); self.cancel_button.setObjectName('youtube-link-cancel'); busy.addWidget(self.cancel_button)
        layout.addWidget(self.busy); self.busy.hide()
        self.error = label(''); self.error.setObjectName('youtube-link-error'); layout.addWidget(self.error); self.error.hide()
        self.preview = QFrame(); self.preview.setObjectName('youtube-link-preview'); preview = QVBoxLayout(self.preview)
        preview.addWidget(label(window.tr('youtube_link_preview'), 'pageTitle'))
        row = QHBoxLayout(); self.cover = Cover(window.artwork_cache, side=72); row.addWidget(self.cover)
        info = QVBoxLayout(); self.title = label(''); self.title.setObjectName('youtube-link-title'); info.addWidget(self.title)
        self.artist = label('', 'muted'); info.addWidget(self.artist); row.addLayout(info, 1)
        self.more_button = button('', self.more); self.more_button.setObjectName('track-more')
        self.more_button.setIcon(icon('more_vert', palette(window.effective_theme())['onSurface']))
        self.more_button.setAccessibleName(window.tr('more')); row.addWidget(self.more_button); preview.addLayout(row)
        self.canonical = label('', 'muted'); self.canonical.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview.addWidget(self.canonical)
        self.play_button = button(window.tr('play'), self.play, True); self.play_button.setObjectName('youtube-link-play')
        preview.addWidget(self.play_button); layout.addWidget(self.preview); self.preview.hide(); layout.addStretch()
        # A queued task may outlive a page's native QObject. Cancel via plain Python state, not deleted widgets.
        work = self.work
        def destroyed():
            work['active'] = False
            if work['task']:
                work['task'].cancel.set()
        self.destroyed.connect(destroyed)

    def current(self, generation):
        return (not sip.isdeleted(self) and self.work['active'] and not self.window.closing
                and self.window.page == LINK_PAGE and self.route == self.window.route_epoch
                and generation == self.work['generation'])

    def set_loading(self, value):
        self.loading = value; self.busy.setVisible(value)
        self.resolve_button.setEnabled(bool(self.input.text().strip()) and not value)

    def cancel(self):
        self.work['generation'] += 1
        if self.work['task']:
            self.work['task'].cancel.set(); self.work['task'] = None
        self.set_loading(False)

    def deactivate(self):
        self.cancel(); self.work['active'] = False

    def typed(self, value):
        self.cancel(); self.window.youtube_link_input = value
        self.track = None; self.preview.hide(); self.error.clear(); self.error.hide()

    def paste(self):
        # Deliberate text-only clipboard access; typing/paste never triggers extraction or playback.
        clipboard = QApplication.clipboard()
        value = clipboard.text() if clipboard.mimeData() and clipboard.mimeData().hasText() else ''
        if not value.strip():
            self.window.notify(self.window.tr('youtube_link_clipboard_empty')); return
        self.input.setText(value)

    def problem(self, code):
        self.track = None; self.preview.hide()
        self.error.setText(self.window.tr(PROBLEM_KEYS.get(code, 'err_unavailable'))); self.error.show()

    def resolve(self):
        if self.loading:
            return
        self.cancel(); self.track = None; self.preview.hide(); self.error.hide()
        try:
            link = parse_youtube_link(self.input.text())
        except YouTubeLinkError as error:
            self.problem(error.problem); return
        generation = self.work['generation']; self.set_loading(True); self.input.clearFocus()
        def load(cancel, progress):
            try:
                return self.window.provider.open_youtube_link(link, cancel), None
            except YouTubeLinkError as error:
                return None, error.problem
        def ready(result):
            if not self.current(generation):
                return
            self.work['task'] = None; self.set_loading(False)
            track, error = result
            if error:
                self.problem(error); return
            try:
                if not isinstance(track, Track) or track.id != link.video_id:
                    raise ValueError('Wrong video identity')
                track.validate()
            except (ValueError, TypeError):
                self.problem('unavailable'); return
            self.track = track; self.title.setText(track.title); self.artist.setText(track.artist)
            self.cover.set_url(track.thumbnail); self.canonical.setText(link.url); self.preview.show()
        def failed(_):
            if self.current(generation):
                self.work['task'] = None; self.set_loading(False); self.problem('unavailable')
        self.work['task'] = self.window.run(load, ready, failed=failed)

    def play(self):
        if self.track:
            self.window.play_track(self.track, related=False)

    def more(self):
        if self.track:
            self.window.track_menu(self.track, self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))
