"""Explicit optional video, separate from the background music player.

Qt6 uses its multimedia video sink. Genuine Win32 uses Qt5's native Windows
video widget (not the audio-only compatibility decoder). Provider restrictions
are never bypassed; closing video never resumes background audio automatically.
"""
from __future__ import annotations
from .platforms import WINDOWS_X86
from .qt import (sip, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, Qt,
                 QUrl, QLabel, QAudioOutput)
from .widgets import label, button

if WINDOWS_X86:
    from PyQt5.QtMultimedia import QMediaPlayer as VideoMediaPlayer, QMediaContent
    from PyQt5.QtMultimediaWidgets import QVideoWidget
else:
    from PyQt6.QtMultimedia import QMediaPlayer as VideoMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget


class VideoPlayer(QDialog):
    def __init__(self, owner, track, autoload=True):
        super().__init__(owner)
        self.owner, self.track = owner, track; self.closing = False; self.task = None
        self.setWindowTitle(track.title); self.resize(900, 600); self.setMinimumSize(380, 360)
        layout = QVBoxLayout(self)
        self.status = label(owner.tr('loading'), 'muted'); layout.addWidget(self.status)
        self.video = QVideoWidget(); self.video.setMinimumSize(300, 200); layout.addWidget(self.video, 1)
        self.player = VideoMediaPlayer(self); self.player.setVideoOutput(self.video)
        if WINDOWS_X86:
            self.player.setVolume(round(owner.audio.volume()*100))
            self.player.positionChanged.connect(self.position_changed)
            self.player.error.connect(lambda _: self.failed())
        else:
            self.audio = QAudioOutput(self); self.audio.setVolume(owner.audio.volume()); self.player.setAudioOutput(self.audio)
            self.player.positionChanged.connect(self.position_changed)
            self.player.errorOccurred.connect(lambda *_: self.failed())
        self.seek = QSlider(Qt.Orientation.Horizontal); self.seek.setRange(0, 1); self.seek.sliderReleased.connect(lambda: self.player.setPosition(self.seek.value()))
        self.player.durationChanged.connect(lambda value: self.seek.setRange(0, max(1, value))); layout.addWidget(self.seek)
        controls = QHBoxLayout(); self.toggle_button = button(owner.tr('pause'), self.toggle)
        controls.addWidget(self.toggle_button); controls.addStretch(); controls.addWidget(button(owner.tr('close'), self.close)); layout.addLayout(controls)
        if autoload:
            owner.desired_playing = False; owner.player.pause(); owner.update_play_button(); owner.room_local_intent()
            self.task = owner.run(lambda cancel, progress: owner.provider.resolve_video(track), self.ready, failed=lambda _: self.failed())

    def ready(self, result):
        if sip.isdeleted(self) or self.closing:
            return
        url, headers = result
        source = QUrl(self.owner.proxy.register(url, headers))
        if WINDOWS_X86:
            self.player.setMedia(QMediaContent(source))
        else:
            self.player.setSource(source)
        self.status.setText(self.track.title); self.player.play()

    def failed(self):
        if not sip.isdeleted(self) and not self.closing:
            self.status.setText(self.owner.tr('video_failed')); self.player.stop()

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)

    def toggle(self):
        playing = self.player.state() == VideoMediaPlayer.PlayingState if WINDOWS_X86 else self.player.playbackState() == VideoMediaPlayer.PlaybackState.PlayingState
        (self.player.pause if playing else self.player.play)()
        self.toggle_button.setText(self.owner.tr('play' if playing else 'pause'))

    def closeEvent(self, event):
        self.closing = True
        if self.task:
            self.task.cancel.set()
        self.player.stop()
        if WINDOWS_X86:
            self.player.setMedia(QMediaContent())
        else:
            self.player.setSource(QUrl())
        event.accept()
