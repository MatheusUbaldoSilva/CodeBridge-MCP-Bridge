"""Olhinho no campo de senha: mostra/esconde o que esta digitado.

Se o campo estiver vazio e houver senha salva no Windows, o primeiro
clique traz a senha salva para o campo, ja visivel.
"""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLineEdit


def eye_icon(open_eye=True, color="#c9d1d9", size=20):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    p.setPen(pen)
    w = h = float(size)
    path = QPainterPath()
    path.moveTo(2, h / 2)
    path.quadTo(w / 2, h * 0.12, w - 2, h / 2)
    path.quadTo(w / 2, h * 0.88, 2, h / 2)
    p.drawPath(path)
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(w / 2, h / 2), w * 0.14, w * 0.14)
    if not open_eye:
        p.drawLine(QPointF(3, h - 3), QPointF(w - 3, 3))
    p.end()
    return QIcon(pix)


class PasswordEye:
    def __init__(self, line_edit, load_saved=None):
        self.edit = line_edit
        self._load_saved = load_saved
        self.edit.setEchoMode(QLineEdit.Password)
        self.action = QAction(eye_icon(True), "Mostrar senha", self.edit)
        self.action.setToolTip("Mostrar senha")
        self.action.triggered.connect(self.toggle)
        self.edit.addAction(self.action, QLineEdit.TrailingPosition)

    @property
    def visible(self):
        return self.edit.echoMode() == QLineEdit.Normal

    def conceal(self):
        self.edit.setEchoMode(QLineEdit.Password)
        self.action.setIcon(eye_icon(True))
        self.action.setToolTip("Mostrar senha")

    def toggle(self):
        if self.visible:
            self.conceal()
            return
        if not self.edit.text() and self._load_saved is not None:
            try:
                saved = self._load_saved() or ""
            except Exception:
                saved = ""
            if saved:
                self.edit.setText(saved)
        self.edit.setEchoMode(QLineEdit.Normal)
        self.action.setIcon(eye_icon(False))
        self.action.setToolTip("Esconder senha")