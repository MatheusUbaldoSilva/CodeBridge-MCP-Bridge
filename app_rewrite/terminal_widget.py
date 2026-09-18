from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget


class TerminalBridge(QObject):
    output = Signal(str)
    reset_terminal = Signal()

    def __init__(self, terminals, target, on_ready=None):
        super().__init__()
        self.terminals = terminals
        self.target = target
        self.on_ready = on_ready

    @Slot(str)
    def input(self, data):
        try:
            self.terminals.send_input(self.target, data)
        except Exception:
            pass

    @Slot(int, int)
    def resize(self, cols, rows):
        try:
            self.terminals.resize(self.target, cols, rows)
        except Exception:
            pass

    @Slot()
    def ready(self):
        if self.on_ready is not None:
            self.on_ready()


class TerminalWidget(QWidget):
    def __init__(self, terminals, target, parent=None):
        super().__init__(parent)
        self.terminals = terminals
        self.target = target
        self._ready = False
        self._generation = 0
        self._position = 0
        self._initial_replay_done = False

        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background:#0c0c0c;border:0;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.web = QWebEngineView(self)
        self.web.setMinimumWidth(0)
        self.web.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.web.setStyleSheet("background:#0c0c0c;border:0;")
        self.web.page().setBackgroundColor(QColor("#0c0c0c"))
        layout.addWidget(self.web, 1)

        self.channel = QWebChannel(self.web.page())
        self.bridge = TerminalBridge(terminals, target, self._mark_ready)
        self.channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(self.channel)

        html = Path(__file__).resolve().parent / "web_terminal" / "terminal.html"
        self.web.setUrl(QUrl.fromLocalFile(str(html)))

    def _mark_ready(self):
        self._ready = True
        if self.isVisible():
            QTimer.singleShot(0, self._fit_and_replay_once)

    def drain(self):
        if not self._ready:
            return
        generation, position, delta, reset = self.terminals.raw_delta(
            self.target, self._generation, self._position
        )
        if reset:
            self.bridge.reset_terminal.emit()
        if delta:
            self.bridge.output.emit(delta)
        self._generation = generation
        self._position = position

    def fit_terminal(self):
        if not self._ready:
            return
        self.web.page().runJavaScript("window.cbFit && window.cbFit();")

    def _fit_and_replay_once(self):
        if not self._ready:
            return
        self.fit_terminal()
        if self._initial_replay_done:
            return
        self._initial_replay_done = True
        self._generation = 0
        self._position = 0
        self.bridge.reset_terminal.emit()
        QTimer.singleShot(60, self.drain)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_and_replay_once)
        QTimer.singleShot(80, self.fit_terminal)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            QTimer.singleShot(0, self.fit_terminal)

    def focus_terminal(self):
        self.web.setFocus()
        self.fit_terminal()
        self.web.page().runJavaScript("window.cbFocus && window.cbFocus();")
