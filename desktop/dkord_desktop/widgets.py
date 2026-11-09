"""Small native components using the phone's resources and real Material icons."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import sys
from .qt import (Qt, QLabel, QPushButton, QApplication, QIcon, QPixmap, QPainter,
                 QImage, QColor, QSvgRenderer, QSize)
from .experience import contract, text, palette


def translated(value):
    app = QApplication.instance()
    language = app.property('dkord-language') if app else 'en'
    if language == 'hi':
        for key, english in contract()['strings']['en'].items():
            if english == value:
                return text(key, 'hi')
    return value


def label(value, style=None):
    result = QLabel(translated(value)); result.setTextFormat(Qt.TextFormat.PlainText); result.setWordWrap(True)
    if style:
        result.setObjectName(style)
    return result


def button(value, callback, primary=False):
    result = QPushButton(translated(value)); result.clicked.connect(callback); result.setIconSize(QSize(24,24))
    if not value: result.setProperty('iconOnly',True);result.setFixedSize(44,44)
    if primary:
        result.setProperty('primary', True)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result


@lru_cache(maxsize=128)
def icon(name, color='#FFFFFF', side=24):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    path = root/'assets/material'/(name+'.svg')
    if not path.is_file():
        return QIcon()
    svg = path.read_text(encoding='utf-8')
    # Official Material filled paths use current default black; set only the root fill.
    svg = svg.replace('<svg ', '<svg fill="'+color+'" ', 1)
    image = QImage(side*2, side*2, QImage.Format.Format_ARGB32); image.fill(0)
    painter = QPainter(image); QSvgRenderer(svg.encode('utf-8')).render(painter); painter.end()
    pixmap = QPixmap.fromImage(image); pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class ElideLabel(QLabel):
    def __init__(self, value='', parent=None):
        super().__init__(value, parent)
        self.setTextFormat(Qt.TextFormat.PlainText); self.setWordWrap(False); self.setMinimumWidth(0)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setFont(self.font()); painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width()))
        painter.end()
