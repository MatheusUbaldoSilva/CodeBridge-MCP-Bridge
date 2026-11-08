"""IA Local: conversa no estilo do app do Claude, com as cores do CodeBridge.

Seu texto vai num balao arredondado a direita; a resposta da IA e texto solto a
esquerda; o que a IA fez vira uma linha cinza que abre e fecha
("Usou o CodeBridge · leu 1 arquivo · executou 1 comando ›").
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from local_ai_format import format_message, format_plain

BUBBLE_MAX_RATIO = 0.78
BUBBLE_PADDING = 12 * 2 + 2 + 6  # padding do USER_STYLE + borda + folga de arredondamento
CHEVRON_CLOSED = "  ›"
CHEVRON_OPEN = "  ⌄"

USER_STYLE = ("QLabel{background:#1f2b37;color:#e6edf3;border:1px solid #2c3a48;"
              "border-radius:14px;padding:8px 12px;font-size:13px;}")
ANSWER_STYLE = "QLabel{color:#dfe7ee;font-size:13px;background:transparent;}"
ACTIVITY_STYLE = ("QPushButton{color:#8b98a5;background:transparent;border:none;text-align:left;"
                  "padding:0;font-size:12px;}QPushButton:hover{color:#c9d4dd;}")
DETAILS_STYLE = "QLabel{color:#7f93a3;font-size:11px;background:transparent;padding-left:12px;}"
ERROR_STYLE = "QLabel{color:#e07a7a;font-size:12px;background:transparent;}"
INFO_STYLE = "QLabel{color:#7f93a3;font-size:11px;background:transparent;}"


def _plural(count: int, one: str, many: str) -> str:
    return "%d %s" % (count, one if count == 1 else many)


def activity_summary(notes) -> str:
    """Resumo de uma linha do que a IA fez num pedido."""
    notes = list(notes or [])
    files = sum(n.startswith("leu ") for n in notes)
    dirs = sum(n.startswith("listou a pasta") for n in notes)
    rag = any(n.startswith("consultou a Central RAG") for n in notes)
    commands = sum(n.startswith("executando no") for n in notes)
    refused = sum(n.startswith("você recusou") for n in notes)
    missing = sum(n.startswith(("não encontrei", "não li")) for n in notes)
    parts = []
    if files:
        parts.append("leu " + _plural(files, "arquivo", "arquivos"))
    if dirs:
        parts.append("listou " + _plural(dirs, "pasta", "pastas"))
    if rag:
        parts.append("consultou a Central RAG")
    if commands:
        parts.append("executou " + _plural(commands, "comando", "comandos"))
    if refused:
        parts.append("comando recusado")
    if missing:
        parts.append("arquivo não encontrado" if missing == 1 else _plural(missing, "", "arquivos não encontrados").strip())
    if not parts:
        parts.append(notes[-1] if notes else "trabalhando")
    return "Usou o CodeBridge · " + " · ".join(parts)


class _UserBubble(QWidget):
    def __init__(self, text: str):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setStyleSheet(USER_STYLE)
        row.addWidget(self.label)
        self.update_payload(text)

    def update_payload(self, text):
        self.text = str(text or "")
        self.label.setText(format_plain(self.text))
        self.fit(getattr(self, "_width", 0) or 600)

    def fit(self, width: int):
        """Largura do balao = largura do texto (poucas palavras ficam numa linha so),
        no maximo 78% da conversa; acima disso quebra a linha."""
        self._width = width
        limit = max(160, int(width * BUBBLE_MAX_RATIO))
        self.label.ensurePolished()
        metrics = self.label.fontMetrics()
        lines = self.text.splitlines() or [""]
        natural = max(metrics.horizontalAdvance(line) for line in lines) + BUBBLE_PADDING
        self.label.setFixedWidth(min(natural, limit))



class _Answer(QLabel):
    def __init__(self, text: str):
        super().__init__()
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setStyleSheet(ANSWER_STYLE)
        self.update_payload(text)

    def update_payload(self, text):
        self.setText(format_message(text) if text else '<span style="color:#7f93a3;">…</span>')


class _Activity(QWidget):
    def __init__(self, notes):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(3)
        self.header = QPushButton()
        self.header.setFlat(True)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setStyleSheet(ACTIVITY_STYLE)
        self.header.clicked.connect(self.toggle)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details.setStyleSheet(DETAILS_STYLE)
        self.details.hide()
        box.addWidget(self.header)
        box.addWidget(self.details)
        self.notes = []
        self.update_payload(notes)

    @property
    def expanded(self) -> bool:
        return not self.details.isHidden()

    def toggle(self):
        self.details.setVisible(not self.expanded)
        self._render_header()

    def update_payload(self, notes):
        self.notes = list(notes or [])
        self.details.setText("<br>".join("· " + html.escape(n) for n in self.notes))
        self._render_header()

    def _render_header(self):
        self.header.setText(activity_summary(self.notes) + (CHEVRON_OPEN if self.expanded else CHEVRON_CLOSED))


class _Notice(QLabel):
    def __init__(self, text: str, style: str):
        super().__init__()
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setStyleSheet(style)
        self.update_payload(text)

    def update_payload(self, text):
        self.setText(html.escape(text or ""))


def _make(kind, payload):
    if kind == "user":
        return _UserBubble(payload)
    if kind == "assistant":
        return _Answer(payload)
    if kind == "activity":
        return _Activity(payload)
    return _Notice(payload, ERROR_STYLE if kind == "error" else INFO_STYLE)


def _signature(kind, payload):
    return kind, tuple(payload) if isinstance(payload, list) else payload


class ChatView(QScrollArea):
    """Lista de itens da conversa; sync() so recria o que mudou."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiChat")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("QScrollArea#aiChat{background:#0f151b;border:1px solid #33414d;"
                           "border-radius:8px;}")
        self.body = QWidget()
        self.body.setObjectName("aiChatBody")
        self.body.setStyleSheet("QWidget#aiChatBody{background:#0f151b;}")
        self.column = QVBoxLayout(self.body)
        self.column.setContentsMargins(16, 14, 16, 14)
        self.column.setSpacing(12)
        self.column.addStretch(1)
        self.setWidget(self.body)
        self.items: list = []
        self._blocks: list = []

    # ---- sincronizacao ---------------------------------------------------
    def sync(self, blocks) -> None:
        stick = self._at_bottom()
        self._blocks = blocks
        for index, (kind, payload) in enumerate(blocks):
            signature = _signature(kind, payload)
            if index < len(self.items):
                old_signature, widget = self.items[index]
                if old_signature == signature:
                    continue
                if old_signature[0] == kind:
                    widget.update_payload(payload)
                    self.items[index] = (signature, widget)
                    continue
                self._drop_from(index)
            widget = _make(kind, payload)
            self.column.insertWidget(self.column.count() - 1, widget)
            self.items.append((signature, widget))
        if len(self.items) > len(blocks):
            self._drop_from(len(blocks))
        self._fit()
        if stick:
            QTimer.singleShot(0, self.scroll_to_bottom)

    def _drop_from(self, index: int) -> None:
        for _signature_, widget in self.items[index:]:
            self.column.removeWidget(widget)
            widget.deleteLater()
        del self.items[index:]

    # ---- rolagem e largura -------------------------------------------------
    def _at_bottom(self) -> bool:
        bar = self.verticalScrollBar()
        return bar.value() >= bar.maximum() - 40

    def scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _fit(self) -> None:
        width = self.viewport().width() - 32
        for _signature_, widget in self.items:
            if isinstance(widget, _UserBubble):
                widget.fit(width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    # ---- texto para testes e copia --------------------------------------
    def toHtml(self) -> str:
        out = []
        for kind, payload in self._blocks:
            if kind == "user":
                out.append(format_plain(payload))
            elif kind == "assistant":
                out.append(format_message(payload))
            elif kind == "activity":
                out.append(html.escape(activity_summary(payload)))
                out.extend("· " + html.escape(n) for n in payload)
            else:
                out.append(html.escape(payload))
        return "\n".join(out)
