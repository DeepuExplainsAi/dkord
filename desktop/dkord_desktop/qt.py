"""One widget tree; Qt6 on existing targets, Qt5 solely for genuine Windows x86."""
from .platforms import WINDOWS_X86

if WINDOWS_X86:
    from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg, sip
    from .qt5media import QAudioOutput, QMediaPlayer
    QAction = QtWidgets.QAction
    QShortcut = QtWidgets.QShortcut
    for _class in (QtWidgets.QApplication, QtWidgets.QDialog, QtWidgets.QMenu):
        if not hasattr(_class,'exec'):_class.exec = _class.exec_
    BINDING = 'PyQt5'
else:
    from PyQt6 import QtCore, QtGui, QtWidgets, QtSvg, sip
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    QAction = QtGui.QAction
    QShortcut = QtGui.QShortcut
    BINDING = 'PyQt6'

Qt = QtCore.Qt
QThreadPool = QtCore.QThreadPool
QTimer = QtCore.QTimer
QUrl = QtCore.QUrl
QSize = QtCore.QSize
QLockFile = QtCore.QLockFile
QObject = QtCore.QObject
QRunnable = QtCore.QRunnable
pyqtSignal = QtCore.pyqtSignal
QColor = QtGui.QColor
QFont = QtGui.QFont
QIcon = QtGui.QIcon
QImage = QtGui.QImage
QPainter = QtGui.QPainter
QPixmap = QtGui.QPixmap
QPainterPath = QtGui.QPainterPath
QFontDatabase = QtGui.QFontDatabase
QKeySequence = QtGui.QKeySequence
QSvgRenderer = QtSvg.QSvgRenderer
for _name in (
    'QApplication', 'QAbstractItemView', 'QCheckBox', 'QComboBox', 'QDialog', 'QDialogButtonBox', 'QDockWidget',
    'QDoubleSpinBox', 'QFileDialog', 'QFormLayout', 'QFrame', 'QHBoxLayout', 'QHeaderView', 'QInputDialog',
    'QLabel', 'QLineEdit', 'QListWidget', 'QListWidgetItem', 'QMainWindow', 'QMenu', 'QMessageBox', 'QPushButton',
    'QTabWidget', 'QStackedWidget', 'QSizePolicy', 'QToolButton', 'QScrollArea', 'QSlider', 'QSpinBox', 'QStyle', 'QTableWidget', 'QTableWidgetItem', 'QTextEdit', 'QVBoxLayout', 'QWidget',
):
    globals()[_name] = getattr(QtWidgets, _name)
del _name
