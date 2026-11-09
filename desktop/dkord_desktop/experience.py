"""Phone-owned presentation contract, consumed by both Qt6 and real Win32 Qt5."""
from __future__ import annotations
from functools import lru_cache
import json
from pathlib import Path
import re
import sys


@lru_cache(maxsize=1)
def contract() -> dict:
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    value = json.loads((root / 'assets/phone-contract.json').read_text(encoding='utf-8'))
    if value.get('schema') != 1:
        raise ValueError('Unsupported phone product contract')
    return value


def text(key: str, language: str = 'en', *args) -> str:
    strings = contract()['strings']
    value = strings.get(language, {}).get(key, strings['en'].get(key, key))
    # Android positional format specifiers, including reordered Hindi arguments.
    offset = 0
    def replace(match):
        nonlocal offset
        position = int(match.group(1)) - 1 if match.group(1) else offset
        if not match.group(1):
            offset += 1
        return str(args[position]) if position < len(args) else match.group(0)
    return re.sub(r'%(?:(\d+)\$)?[ds]', replace, value).replace('%%', '%')


def palette(mode='dark') -> dict:
    palettes = contract()['palettes']
    result = dict(palettes['dark'])
    result.update(palettes.get(mode, palettes['dark']))
    if mode == 'light':
        # Material3 light defaults for roles not overridden by the phone.
        result.update(onBackground='#1D1B20', onSurface='#1D1B20', outline='#79747E',
                      outlineVariant='#CAC4D0', surfaceContainerLow='#F7F2FA', surfaceContainerHighest='#E6E0E9')
    return result


def branding(title: str, language='en') -> str:
    keys = {'dkord:choliwood:popular': 'choliwood_popular', 'dkord:choliwood:latest': 'choliwood_latest'}
    if title in keys:
        return text(keys[title], language)
    # Display branding only; the query, song identity/title and artist are untouched.
    return re.sub(r'\bbhojpuri\b|भोजपुरी', text('choliwood_name', language), title, flags=re.I)


def stylesheet(mode='dark') -> str:
    # Native Qt5/Windows and macOS tab chrome otherwise keeps a white/blue fill
    # under inherited white text. Scope explicit phone-palette tab subcontrols
    # to the full player; do not change navigation, media or persistence logic.
    p = palette(mode)
    return f'''
QWidget {{ background:{p['background']}; color:{p['onSurface']}; font-family:'Roboto','Noto Sans Devanagari','Segoe UI','Noto Sans','Arial'; font-size:14px; }}
QMainWindow,QDialog,QScrollArea,QScrollArea>QWidget>QWidget {{ background:{p['background']}; }}
QFrame#sidebar {{ border-right:1px solid {p['outlineVariant']}; }}
QLabel#brand {{ font-size:25px; font-weight:700; }} QLabel#pageTitle {{ font-size:26px; font-weight:700; }}
QLabel#eyebrow,QLabel#muted {{ color:{p['onSurfaceVariant']}; }}
QFrame#player {{ background:{p['surfaceContainerHigh']}; border-top:1px solid {p['outlineVariant']}; }}
QPushButton {{ background:{p['surfaceContainerHigh']}; padding:9px 14px; border:0; border-radius:19px; min-height:20px; }}
QPushButton:hover {{ background:{p['surfaceContainerHighest']}; }}
QPushButton[primary="true"] {{ background:{p['primary']}; color:{p['onPrimary']}; font-weight:600; }}
QPushButton:disabled {{ color:{p['onSurfaceVariant']}; }}
QPushButton#nav {{ text-align:left; padding:12px 16px; background:transparent; border:0; border-radius:24px; }}
QPushButton#nav:checked {{ background:{p['surfaceVariant']}; font-weight:700; }}
QToolButton#bottom-nav {{ background:transparent; padding:8px 2px; border:0; border-radius:0; font-size:11px; min-height:48px; }}
QToolButton#bottom-nav:checked {{ color:{p['primary']}; }}
QPushButton#cover-card {{ background:transparent; padding:0; border-radius:8px; }}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {{ background:{p['surfaceContainerHigh']}; border:1px solid {p['outlineVariant']}; border-radius:18px; padding:9px; selection-background-color:{p['primary']}; }}
QLineEdit:focus {{ border-color:{p['primary']}; }} QComboBox::drop-down {{ border:0; width:22px; }}
QTableWidget,QListWidget,QTextEdit {{ background:{p['background']}; border:0; selection-background-color:{p['surfaceVariant']}; }}
QTableWidget::item {{ padding:8px; border:0; }} QHeaderView::section {{ background:{p['background']}; color:{p['onSurfaceVariant']}; border:0; padding:8px; }}
QTabWidget#full-player-tabs::pane {{ border:0; background:{p['background']}; }}
QTabWidget#full-player-tabs QTabBar {{ background:transparent; qproperty-drawBase:0; }}
QTabWidget#full-player-tabs QTabBar::tab {{ background:{p['surfaceContainerHigh']}; color:{p['onSurface']}; border:0; border-radius:16px; min-height:20px; padding:8px 16px; margin:2px 3px; }}
QTabWidget#full-player-tabs QTabBar::tab:selected {{ background:{p['primary']}; color:{p['onPrimary']}; }}
QTabWidget#full-player-tabs QTabBar::tab:hover:!selected {{ background:{p['surfaceContainerHighest']}; }}
QListWidget::item {{ padding:8px; border-radius:6px; }} QListWidget::item:selected {{ background:{p['surfaceVariant']}; }}
QScrollArea {{ border:0; }} QScrollBar:vertical {{ background:transparent; width:8px; }}
QScrollBar::handle:vertical {{ background:{p['outline']}; border-radius:4px; min-height:30px; }}
QScrollBar:horizontal {{ background:transparent; height:6px; }} QScrollBar::handle:horizontal {{ background:{p['outline']}; min-width:28px; border-radius:3px; }}
QSlider::groove:horizontal {{ height:3px; background:{p['outline']}; }}
QSlider::handle:horizontal {{ background:{p['onSurface']}; width:12px; margin:-4px 0; border-radius:6px; }}
QSlider::sub-page:horizontal {{ background:{p['primary']}; }}
QDockWidget::title {{ background:{p['surfaceContainer']}; padding:10px; font-weight:600; }}
QMenu {{ border:1px solid {p['outline']}; padding:6px; }} QMenu::item {{ padding:10px 18px; }} QMenu::item:selected {{ background:{p['surfaceVariant']}; }}
QToolTip {{ background:{p['surfaceContainerHighest']}; color:{p['onSurface']}; border:1px solid {p['outline']}; }}
QStatusBar {{ color:{p['onSurfaceVariant']}; font-size:12px; }}
QLabel {{ background: transparent; }}
QPushButton[iconOnly="true"] {{ background:transparent; padding:0; border-radius:20px; }}
QPushButton[iconOnly="true"]:hover {{ background:{p['surfaceContainerHighest']}; }}
QPushButton#play-toggle {{ min-width:44px; max-width:44px; min-height:44px; max-height:44px; }}
QPushButton#full-play-toggle {{ background:white; color:black; padding:0; border:0; border-radius:36px; min-width:72px; max-width:72px; min-height:72px; max-height:72px; }}
'''
