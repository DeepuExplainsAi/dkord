from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from .media import Cancelled


from .models import public_error

class TaskSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(object)
    finished = pyqtSignal()


class Task(QRunnable):
    def __init__(self, call):
        super().__init__()
        self.call = call
        self.signals = TaskSignals()
        self.cancel = threading.Event()

    def run(self):
        try:
            result = self.call(self.cancel, self.signals.progress.emit)
            if not self.cancel.is_set():
                self.signals.result.emit(result)
        except Cancelled:
            pass
        except BaseException as error:
            if not self.cancel.is_set():
                self.signals.error.emit(public_error(error))
        finally:
            self.signals.finished.emit()
