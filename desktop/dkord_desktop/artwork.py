"""Bounded public cover-art cache shared by phone-style rows/cards/players.

No local-file/HTML/SVG URLs, credentials or arbitrary imported thumbnail hosts.
Images are decoded and downscaled off the GUI thread; QPixmap is created only on
Qt's GUI thread. No cover network request is made in offline capture fixtures.
"""
from __future__ import annotations
from collections import OrderedDict
from io import BytesIO
import threading
from urllib.parse import urlsplit
import weakref

from .qt import (sip, Qt, QTimer, QThreadPool, QImage, QPixmap, QPainter, QPainterPath,
                 QColor, QSize, QLabel, QIcon, QtCore)
from .experience import palette
from .tasks import Task

HOSTS = ('ytimg.com', 'googleusercontent.com', 'ggpht.com', 'google.com')


def supported_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    if value.startswith('//'):
        value = 'https:' + value
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower()
        if (url.scheme != 'https' or url.username is not None or url.password is not None or url.port not in (None, 443)
                or not any(host == allowed or host.endswith('.'+allowed) for allowed in HOSTS)):
            return None
        return value
    except ValueError:
        return None


def fetch_image(url, cancel):
    import requests
    from PIL import Image
    session = requests.Session(); session.trust_env = False
    try:
        with session.get(url, stream=True, timeout=10, allow_redirects=False) as response:
            response.raise_for_status()
            if response.headers.get('Content-Type', '').split(';')[0].lower() not in ('image/jpeg', 'image/png', 'image/webp'):
                raise ValueError('Unsupported cover image')
            data = bytearray()
            for chunk in response.iter_content(16_384):
                if cancel.is_set():
                    return None
                data.extend(chunk)
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError('Cover image is too large')
            with Image.open(BytesIO(data)) as image:
                if image.width <= 0 or image.height <= 0 or image.width * image.height > 16_777_216:
                    raise ValueError('Unsupported cover dimensions')
                image.thumbnail((512, 512)); output = BytesIO()
                image.convert('RGB').save(output, 'JPEG', quality=90)
                result = QImage.fromData(output.getvalue())
                return result if not result.isNull() else None
    finally:
        session.close()


class ArtworkCache:
    def __init__(self, parent):
        self.parent = parent
        self.images = OrderedDict()
        self.pending = {}
        self.failed = set()
        self.pool = QThreadPool(parent); self.pool.setMaxThreadCount(3)
        self.tasks = set()
        self.labels = weakref.WeakSet()
        self.timer = QTimer(parent); self.timer.setInterval(300); self.timer.timeout.connect(self.visible); self.timer.start()
        self.closed = False

    def register(self, widget):
        self.labels.add(widget)

    def visible(self):
        if self.closed:
            return
        for widget in tuple(self.labels):
            if sip.isdeleted(widget) or not widget.isVisible() or widget._requested:
                continue
            # Qt considers children beyond a scroll viewport visible; don't prefetch
            # every off-screen tile and starve catalogue/player/download work.
            ancestor = widget.parentWidget()
            clipped = False
            while ancestor:
                if hasattr(ancestor, 'viewport'):
                    point = widget.mapTo(ancestor.viewport(), QtCore.QPoint(0, 0))
                    if not ancestor.viewport().rect().intersects(QtCore.QRect(point, widget.size())):
                        clipped = True; break
                ancestor = ancestor.parentWidget()
            if not clipped:
                widget._requested = True
                self.request(widget.url, lambda pixmap, widget=widget, url=widget.url: widget.loaded(pixmap, url))

    def request(self, url, callback):
        url = supported_url(url)
        if not url or self.closed or url in self.failed:
            return
        if url in self.images:
            self.images.move_to_end(url); callback(self.images[url]); return
        if url in self.pending:
            self.pending[url].append(callback); return
        # Bound callbacks/work when rapidly paging through large libraries.
        if len(self.pending) >= 64:
            return
        self.pending[url] = [callback]
        task = Task(lambda cancel, progress: fetch_image(url, cancel)); self.tasks.add(task)
        def ready(image):
            if self.closed or image is None:
                return
            pixmap = QPixmap.fromImage(image); self.images[url] = pixmap
            while len(self.images) > 96:
                self.images.popitem(last=False)
            for call in self.pending.get(url, []):
                call(pixmap)
        def error(_):
            self.failed.add(url)
            if len(self.failed) > 256:
                self.failed.clear()
        def finished():
            self.tasks.discard(task); self.pending.pop(url, None)
        task.signals.result.connect(ready); task.signals.error.connect(error); task.signals.finished.connect(finished)
        self.pool.start(task)

    def close(self):
        self.closed = True; self.timer.stop()
        for task in tuple(self.tasks):
            task.cancel.set()
        self.pool.clear()


class Cover(QLabel):
    def __init__(self, cache, url=None, side=52, circular=False, action=None, parent=None):
        super().__init__(parent)
        self.cache, self.url, self.circular, self.action = cache, supported_url(url), circular, action
        self.pixmap_data = None; self._requested = False
        self.setFixedSize(side, side)
        self.setAccessibleName('Album artwork')
        if action:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        cache.register(self)

    def set_url(self, value):
        value = supported_url(value)
        if value != self.url:
            self.url = value; self.pixmap_data = None; self._requested = False; self.update()

    def loaded(self, pixmap, url=None):
        if not sip.isdeleted(self) and (url is None or self.url == url):
            self.pixmap_data = pixmap; self.update()

    def mouseReleaseEvent(self, event):
        if self.action and event.button() == Qt.MouseButton.LeftButton:
            self.action()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = QtCore.QRectF(self.rect())
        if self.circular:
            path.addEllipse(rect)
        else:
            path.addRoundedRect(rect, 6, 6)
        painter.setClipPath(path)
        if self.pixmap_data:
            pixmap = self.pixmap_data.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((self.width()-pixmap.width())//2, (self.height()-pixmap.height())//2, pixmap)
        else:
            p = palette(self.cache.parent.store.setting('theme', 'dark'))
            painter.fillRect(self.rect(), QColor(p['surfaceVariant']))
            font = painter.font(); font.setPixelSize(max(18, self.width()//3)); painter.setFont(font)
            painter.setPen(QColor(p['onSurfaceVariant'])); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '♪')
        painter.end()
