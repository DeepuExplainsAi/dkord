"""Qt6-shaped controls backed by the real Qt5/Windows multimedia player.

Only the Windows x86 compatibility profile imports this module. No fake player,
PyQt6 alias package, browser UI, or x64 binary is substituted for a Win32 runtime.
"""
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer as NativePlayer


class QAudioOutput(QObject):
    """Qt5 exposes volume/mute on QMediaPlayer, unlike Qt6's separate output object."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._volume = 1.0
        self._muted = False
        self._player = None

    def setVolume(self, volume):
        self._volume = max(0.0, min(1.0, float(volume)))
        if self._player is not None:
            self._player.setVolume(round(self._volume * 100))

    def volume(self):
        return self._volume

    def setMuted(self, muted):
        self._muted = bool(muted)
        if self._player is not None:
            self._player.setMuted(self._muted)

    def isMuted(self):
        return self._muted


class QMediaPlayer(NativePlayer):
    PlaybackState = NativePlayer.State
    playbackStateChanged = pyqtSignal(object)
    errorOccurred = pyqtSignal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output = None
        self.stateChanged.connect(self.playbackStateChanged.emit)
        self.error.connect(lambda error: self.errorOccurred.emit(error, self.errorString()))

    def setAudioOutput(self, output):
        if self._output is not None:
            self._output._player = None
        self._output = output
        if output is not None:
            output._player = self
            output.setVolume(output.volume())
            output.setMuted(output.isMuted())

    def audioOutput(self):
        return self._output

    def setSource(self, url):
        self.setMedia(QMediaContent(url))

    def source(self):
        return self.media().canonicalUrl()

    def playbackState(self):
        return self.state()
