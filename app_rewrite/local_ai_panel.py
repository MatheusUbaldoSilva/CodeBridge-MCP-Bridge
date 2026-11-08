"""Aba IA Local: Qwen2.5-Coder no computador, com acesso as ferramentas do CodeBridge.

Modos Ligada / Desligada / Sob demanda, medidores de memoria, conversa com
linhas de acao em cinza e cartao de aprovacao para cada comando.
"""
from __future__ import annotations

import queue
import threading
import time

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

import local_ai_server as srv
from local_ai_chat import ChatView
from local_ai_format import format_message, format_plain  # noqa: F401 - usados pelos testes
from local_ai_agent import LocalAiAgent, RuntimeCommandRunner, terminal_label
from local_ai_client import LocalAiClient

MUTED = "color:#9fb0bf;"
DOT = " · "
MODE_BUTTONS = (
    ("ON", "Ligada", "#2f855a"),
    ("OFF", "Desligada", "#5b6670"),
    ("ON_DEMAND", "Sob demanda", "#2b6cb0"),
)
BUTTON_OFF_STYLE = ("QPushButton{background:#1b2229;color:#c9d4dd;border:1px solid #33414d;"
                    "padding:4px 12px;}")
METER_STYLE = ("QProgressBar{background:#1b2229;border:1px solid #33414d;border-radius:4px;"
               "color:#dfe7ee;text-align:center;font-size:11px;}"
               "QProgressBar::chunk{background:%s;border-radius:3px;}")
def _gb(mb) -> str:
    return ("%.1f" % (mb / 1024)).replace(".", ",")


def status_line(server, agent_status: str = "") -> tuple[str, str]:
    """(texto, cor) da linha de estado ao lado dos modos."""
    if server.state == srv.STATE_ERROR and server.error:
        return "● " + server.error, "#e07a7a"
    if agent_status:
        return "● " + agent_status, "#e0c46c"
    if server.state == srv.STATE_LOADING:
        return "● Carregando modelo…", "#e0c46c"
    if server.state == srv.STATE_READY:
        left = server.idle_seconds_left()
        if left is None:
            return "● Pronta", "#8fd19e"
        minutes = max(1, (left + 59) // 60)
        return "● Pronta%sdesliga em %d min" % (DOT, minutes), "#8fd19e"
    if server.mode == "ON_DEMAND":
        return "● Desligada%sliga ao enviar uma mensagem" % DOT, "#9fb0bf"
    return "● Desligada", "#9fb0bf"


def badge(server) -> tuple[str, str]:
    if server.is_running():
        return "IA: ON", "background:#1f7a3d; color:white; font-weight:bold;"
    return "IA: OFF", "background:#3a4550; color:#c9d4dd; font-weight:bold;"


def _default_search(query, project_id, top_k):
    from rag_search_panel import _default_search as search
    return search(query, project_id, top_k)


class LocalAiPanel(QWidget):
    def __init__(self, runtime, *, project_id=lambda: "", project_root=lambda: None,
                 search_fn=None, server=None, runner=None, client_factory=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.server = server or srv.LocalAiServer()
        self.agent = LocalAiAgent(
            client_factory=client_factory or (lambda: LocalAiClient(self.server.port, self.server.api_key)),
            ensure_ready=self._ensure_ready,
            runner=runner or RuntimeCommandRunner(runtime),
            search_fn=search_fn or _default_search,
            project_id=project_id, project_root=project_root,
            on_activity=self._set_busy,
        )
        self.blocks: list = []
        self._dirty = True
        self._agent_status = ""
        self._memory: dict = {}
        self._memory_results: queue.Queue = queue.Queue()
        self._memory_busy = False
        self._memory_at = 0.0
        self._build()
        self._render_mode()
        if not self.server.is_installed():
            self._add("error", "Modelo não instalado. Esperado em: " + str(srv.AI_DIR))
        elif self.server.mode == "ON":
            self.server.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(150)
        self._tick()

    # ---- montagem ---------------------------------------------------------
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("IA Local — " + srv.MODEL_NAME)
        title.setStyleSheet("font-size:14px;font-weight:bold;")
        layout.addWidget(title)
        self.folder_label = QLabel()
        self.folder_label.setStyleSheet(MUTED + "font-size:11px;")
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.folder_label)

        modes = QHBoxLayout()
        label = QLabel("Modo:")
        label.setStyleSheet(MUTED + "padding-right:8px;")
        modes.addWidget(label)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons = {}
        for mode, text, _color in MODE_BUTTONS:
            button = QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, m=mode: self.choose_mode(m))
            self.mode_group.addButton(button)
            self.mode_buttons[mode] = button
            modes.addWidget(button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        modes.addSpacing(12)
        modes.addWidget(self.status, 1)
        layout.addLayout(modes)

        meters = QHBoxLayout()
        self.vram_meter = self._meter("#4a90c2")
        self.ram_meter = self._meter("#6b8e5a")
        meters.addWidget(self.vram_meter, 1)
        meters.addWidget(self.ram_meter, 1)
        layout.addLayout(meters)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#33414d;")
        layout.addWidget(line)

        self.chat = ChatView(self)
        layout.addWidget(self.chat, 1)

        self.card = QFrame()
        self.card.setObjectName("aiApprovalCard")
        self.card.setStyleSheet("QFrame#aiApprovalCard{background:#1a2026;border:1px solid #c9a227;"
                                "border-radius:8px;}")
        card = QVBoxLayout(self.card)
        self.card_title = QLabel()
        self.card_title.setStyleSheet("font-weight:bold;")
        self.card_reason = QLabel()
        self.card_reason.setWordWrap(True)
        self.card_reason.setStyleSheet(MUTED)
        self.card_command = QPlainTextEdit()
        self.card_command.setReadOnly(True)
        self.card_command.setMaximumHeight(90)
        self.card_command.setStyleSheet("font-family:Consolas,monospace;background:#0a1015;")
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.run_button = QPushButton("Executar")
        self.run_button.setStyleSheet("background:#1f7a3d;color:white;font-weight:bold;padding:4px 14px;")
        self.edit_button = QPushButton("Editar")
        self.reject_button = QPushButton("Recusar")
        self.run_button.clicked.connect(self.approve_command)
        self.edit_button.clicked.connect(self.edit_command)
        self.reject_button.clicked.connect(self.reject_command)
        for button in (self.run_button, self.edit_button, self.reject_button):
            actions.addWidget(button)
        for widget in (self.card_title, self.card_reason, self.card_command):
            card.addWidget(widget)
        card.addLayout(actions)
        self.card.hide()
        self._pending = None
        layout.addWidget(self.card)

        self.use_rag = QCheckBox("Consultar Central RAG")
        self.use_rag.setChecked(False)  # liga so quando precisar dos conhecimentos do projeto
        self.use_rag.setToolTip("Marque quando a pergunta depender dos conhecimentos do projeto")
        layout.addWidget(self.use_rag)

        bottom = QHBoxLayout()
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Pergunte ou peça uma tarefa…  (Enter envia, Shift+Enter nova linha)")
        self.input.setMaximumHeight(84)
        self.input.installEventFilter(self)
        bottom.addWidget(self.input, 1)
        side = QVBoxLayout()
        self.send_button = QPushButton("Enviar")
        self.stop_button = QPushButton("Parar")
        self.clear_button = QPushButton("Limpar")
        self.send_button.clicked.connect(self.send)
        self.stop_button.clicked.connect(self.stop)
        self.clear_button.clicked.connect(self.clear)
        for button in (self.send_button, self.stop_button, self.clear_button):
            side.addWidget(button)
        bottom.addLayout(side)
        layout.addLayout(bottom)

    def _meter(self, color):
        meter = QProgressBar()
        meter.setRange(0, 100)
        meter.setValue(0)
        meter.setTextVisible(True)
        meter.setFixedHeight(18)
        meter.setStyleSheet(METER_STYLE % color)
        return meter

    def eventFilter(self, obj, event):
        if (obj is self.input and event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and not event.modifiers() & Qt.ShiftModifier):
            self.send()
            return True
        return super().eventFilter(obj, event)

    # ---- acoes do usuario ------------------------------------------------
    def choose_mode(self, mode):
        if mode == "OFF" and self.agent.running:
            self.agent.cancel()
        try:
            self.server.set_mode(mode)
        except Exception as exc:
            self._add("error", "Não foi possível mudar o modo: " + str(exc))
        self._render_mode()
        self._tick()

    def send(self):
        text = self.input.toPlainText().strip()
        if not text or self.agent.running:
            return
        if not self.server.is_installed():
            self._add("error", "Modelo não instalado. Esperado em: " + str(srv.AI_DIR))
            return
        if self.server.mode == "OFF":
            self._add("error", "A IA está desligada. Escolha Ligada ou Sob demanda.")
            return
        self.input.clear()
        self._add("user", text)
        self.agent.send(text, rag_enabled=self.use_rag.isChecked())
        self._tick()

    def stop(self):
        if self.agent.running:
            self.agent.cancel()
        self._close_card()

    def clear(self):
        if self.agent.clear():
            self.blocks = []
            self._dirty = True
            self._tick()

    def approve_command(self):
        if self._pending is None:
            return
        edited = self.card_command.toPlainText().strip()
        self.agent.approve(edited if edited != self._pending["command"] else None)
        self._close_card()

    def edit_command(self):
        self.card_command.setReadOnly(False)
        self.card_command.setFocus()

    def reject_command(self):
        if self._pending is None:
            return
        self.agent.reject()
        self._close_card()

    def shutdown(self):
        self.timer.stop()
        if self.agent.running:
            self.agent.cancel()
        self.server.stop()

    # ---- integracao com o servidor --------------------------------------
    def _ensure_ready(self, cancelled, status):
        server = self.server
        if server.state == srv.STATE_READY:
            server.touch()
            return True, ""
        if server.mode == "OFF":
            return False, "A IA está desligada. Escolha Ligada ou Sob demanda."
        status("Carregando modelo…")
        if not server.start():
            return False, server.error or "Não foi possível ligar a IA."
        if server.wait_ready(cancelled=cancelled):
            return True, ""
        return False, server.error or "A IA não terminou de carregar."

    def _set_busy(self, busy):
        self.server.busy = bool(busy)
        self.server.touch()

    # ---- atualizacao periodica ------------------------------------------
    def _tick(self):
        self._drain_events()
        self.server.tick()
        self._refresh_memory()
        text, color = status_line(self.server, self._agent_status)
        self.status.setText(text)
        self.status.setStyleSheet("color:%s;" % color)
        running = self.agent.running
        self.send_button.setEnabled(not running and self.server.mode != "OFF")
        self.stop_button.setEnabled(running)
        self.clear_button.setEnabled(not running and bool(self.blocks))
        self._render_mode()
        if self._dirty:
            self._render_chat()

    def _drain_events(self):
        while True:
            try:
                kind, data = self.agent.events.get_nowait()
            except queue.Empty:
                return
            if kind == "status":
                self._agent_status = data or ""
            elif kind == "assistant_start":
                self._add("assistant", "")
            elif kind == "text":
                if self.blocks and self.blocks[-1][0] == "assistant":
                    self.blocks[-1][1] += data
                    self._dirty = True
            elif kind == "assistant_done":
                if self.blocks and self.blocks[-1][0] == "assistant":
                    if data:
                        self.blocks[-1][1] = data
                    else:
                        self.blocks.pop()
                    self._dirty = True
            elif kind == "note":
                if data == "interrompido":
                    self._add("info", "Interrompido")
                elif self.blocks and self.blocks[-1][0] == "activity":
                    self.blocks[-1][1].append(data)
                    self._dirty = True
                else:
                    self._add("activity", [data])
            elif kind == "error":
                self._add("error", data)
            elif kind == "approval":
                self._open_card(data)
            elif kind == "approval_closed":
                self._close_card()
            elif kind == "turn_done":
                self._agent_status = ""

    def _refresh_memory(self):
        while True:
            try:
                self._memory = self._memory_results.get_nowait()
                self._memory_busy = False
            except queue.Empty:
                break
        now = time.monotonic()
        if not self._memory_busy and now - self._memory_at >= 2.0:
            self._refresh_folder()
            self._memory_busy, self._memory_at = True, now
            threading.Thread(target=lambda: self._memory_results.put(srv.memory_snapshot()),
                             name="LocalAiMemory", daemon=True).start()
        self._set_meter(self.vram_meter, "Placa de vídeo", self._memory.get("vram_used_mb"),
                        self._memory.get("vram_total_mb"))
        self._set_meter(self.ram_meter, "RAM", self._memory.get("ram_used_mb"),
                        self._memory.get("ram_total_mb"))

    def _refresh_folder(self):
        try:
            root = self.agent.project_root()
        except Exception:
            root = None
        self.folder_label.setText(
            "Pasta do projeto: " + str(root) if root
            else "Pasta do projeto: nenhuma (escolha na Central RAG)")

    @staticmethod
    def _set_meter(meter, name, used, total):
        if not total or used is None:
            meter.setValue(0)
            meter.setFormat(name + ": sem leitura")
            return
        meter.setValue(int(100 * used / total))
        meter.setFormat("%s %s / %s GB" % (name, _gb(used), _gb(total)))

    # ---- desenho ---------------------------------------------------------
    def _render_mode(self):
        for mode, _text, color in MODE_BUTTONS:
            button = self.mode_buttons[mode]
            active = mode == self.server.mode
            button.setChecked(active)
            button.setStyleSheet(
                "QPushButton{background:%s;color:white;font-weight:bold;border:1px solid %s;"
                "padding:4px 12px;}" % (color, color) if active else BUTTON_OFF_STYLE)

    def _add(self, kind, payload):
        self.blocks.append([kind, payload if kind == "activity" else (payload or "")])
        self._dirty = True

    def _render_chat(self):
        self.chat.sync(self.blocks)
        self._dirty = False

    def _open_card(self, request):
        self._pending = request
        self.card_title.setText("A IA quer rodar este comando no %s:" % terminal_label(request["terminal"]))
        self.card_reason.setText(request.get("reason") or "")
        self.card_reason.setVisible(bool(request.get("reason")))
        self.card_command.setPlainText(request["command"])
        self.card_command.setReadOnly(True)
        self.card.show()

    def _close_card(self):
        self._pending = None
        self.card.hide()
