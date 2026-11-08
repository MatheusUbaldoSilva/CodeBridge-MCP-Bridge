"""Card "IAs" no topo do CodeBridge: quais modelos estao ligados e onde rodam.

Fica ao lado do logo, no mesmo visual do cronometro. Le a IA Local pelo proprio
servidor e os modelos da Central RAG pelos processos llama-server em execucao
(argumentos -m, -ngl e --device), entao funciona seja quem for que os ligou.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

# (chave, nome na tela, modelo na tela, trecho do nome do arquivo .gguf)
MODELS = (
    ("LOCAL", "IA Local", "Qwen 7B", "qwen2.5-coder-"),
    ("RAG_TEXT", "RAG texto", "Jina v5", "v5-small-retrieval"),
    ("RAG_CODE", "RAG código", "Jina Code", "jina-code-embeddings"),
)

GREEN, AMBER, RED, GRAY = "#3fb950", "#d29922", "#e5534b", "#4a5560"
LOCAL_STATES = {  # estado do LocalAiServer -> (texto, cor, conta como ativa)
    "READY": ("Ligada", GREEN, True),
    "LOADING": ("Carregando…", AMBER, True),
    "ERROR": ("Erro", RED, False),
    "OFF": ("Desligada", GRAY, False),
}
GPU_FLAGS = ("-ngl", "--n-gpu-layers", "--gpu-layers")

# Chave de processamento das IAs (mesma ordem e visual dos botoes do cronometro).
COMPUTE_BUTTONS = (
    ("CPU", "CPU", "#c0762c",
     "Todas as IAs rodam no processador e a placa de vídeo fica livre."),
    ("GPU", "GPU", "#2f9e44",
     "Todas as IAs rodam na placa de vídeo. Sem placa ou sem memória livre, elas não ligam."),
    ("AUTO", "Automático", "#3a78c2",
     "Usa a placa de vídeo quando há memória livre; senão, o processador."),
)

BOX_STYLE = ("QFrame#aiStatusBox{background:#0a1015;border:1px solid #33414d;"
             "border-radius:10px;}QFrame#aiStatusBox:hover{border-color:#4a5c6b;}")
TITLE_STYLE = ("color:#7f93a3;font-size:11px;font-weight:600;letter-spacing:1px;"
               "background:transparent;border:0;")
NAME_STYLE = "color:#dfe7ee;font-size:12px;background:transparent;border:0;"
MODEL_STYLE = "color:#7f93a3;font-size:11px;background:transparent;border:0;"


# ---- leitura dos processos ------------------------------------------------
def parse_cmdline(cmdline) -> dict:
    """Argumentos de um llama-server -> {"model": nome do .gguf, "device": GPU|CPU}."""
    args = [str(a) for a in (cmdline or [])]
    model, layers, device = "", None, None
    for index, arg in enumerate(args[:-1]):
        value = args[index + 1]
        if arg in ("-m", "--model"):
            model = Path(value).name
        elif arg in GPU_FLAGS:
            try:
                layers = int(value)
            except ValueError:
                layers = None
        elif arg == "--device":
            device = value.strip().lower()
    on_cpu = device in ("none", "cpu") or layers == 0
    return {"model": model.lower(), "device": "CPU" if on_cpu else "GPU"}


def scan_llama_servers(process_iter=None) -> list:
    """llama-server em execucao na maquina (qualquer copia, qualquer dono)."""
    if process_iter is None:
        try:
            import psutil
        except Exception:
            return []
        process_iter = psutil.process_iter
    found = []
    for proc in process_iter(["name"]):
        try:
            name = str((proc.info or {}).get("name") or "").lower()
            if name.startswith("llama-server"):
                found.append(parse_cmdline(proc.cmdline()))
        except Exception:
            continue
    return found


def _device_of(processes, needle):
    for proc in processes or []:
        if needle in proc.get("model", ""):
            return proc.get("device") or "GPU"
    return None


def local_label(model) -> str | None:
    """'qwen2.5-coder-3b-instruct-q4_k_m.gguf' -> 'Qwen 3B' (tamanho escolhido pelo instalador)."""
    match = re.search(r"coder-(\d+(?:\.\d+)?)b", Path(str(model or "")).name.lower())
    return "Qwen %sB" % match.group(1) if match else None


def describe(local_server, processes) -> list:
    """Linhas do card: dicts com key, name, model, text, color e active."""
    rows = []
    for key, name, model, needle in MODELS:
        device = _device_of(processes, needle)
        if key == "LOCAL" and local_server is not None:
            model = local_label(getattr(local_server, "model", None)) or model
        if key == "LOCAL":
            if local_server is None:
                text, color, active = "—", GRAY, False
            elif not local_server.is_installed():
                text, color, active = "Não instalada", GRAY, False
            else:
                text, color, active = LOCAL_STATES.get(
                    str(local_server.state), ("Desligada", GRAY, False))
                if local_server.state == "READY" and device:
                    text += " · " + device
        elif device:
            text, color, active = "Ativa · " + device, GREEN, True
        else:
            text, color, active = "Parada", GRAY, False
        rows.append({"key": key, "name": name, "model": model,
                     "text": text, "color": color, "active": active})
    return rows


def compute_button_style(index: int, count: int, color: str, checked: bool) -> str:
    """Botoes segmentados iguais aos do cronometro (ChatGPT | Claude | Desabilitado)."""
    radius = ""
    if index == 0:
        radius = "border-top-left-radius:6px;border-bottom-left-radius:6px;"
    elif index == count - 1:
        radius = "border-top-right-radius:6px;border-bottom-right-radius:6px;"
    return ("QPushButton{background:%s;color:%s;border:1px solid #33414d;border-radius:0px;%s"
            "padding:3px 14px;font-size:12px;font-weight:%s;}"
            % (color if checked else "#1b242c", "white" if checked else "#9fb0bd",
               radius, "700" if checked else "500"))


def title_for(rows) -> str:
    active = sum(1 for row in rows if row["active"])
    if not active:
        return "IAS · NENHUMA ATIVA"
    return "IAS · %d ATIVA%s" % (active, "" if active == 1 else "S")


# ---- card --------------------------------------------------------------------
class AiStatusCard(QFrame):
    """Card clicavel (abre a aba IA Local). Varre os processos fora da tela."""

    def __init__(self, local_server=lambda: None, on_click=None, scan=scan_llama_servers,
                 parent=None, interval_ms: int = 2000, compute=lambda: "AUTO", on_compute=None):
        super().__init__(parent)
        self.setObjectName("aiStatusBox")
        self.setStyleSheet(BOX_STYLE)
        self.setMinimumWidth(230)
        self.setFixedHeight(128)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Status das IAs do CodeBridge · clique para abrir a IA Local")
        self._local_server, self._on_click, self._scan = local_server, on_click, scan
        self._compute, self._on_compute = compute, on_compute
        self._processes, self._scanning = [], False

        box = QVBoxLayout(self)
        box.setContentsMargins(14, 10, 14, 8)
        box.setSpacing(3)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 4)
        buttons.setSpacing(0)
        buttons.addStretch(1)
        self.compute_group = QButtonGroup(self)
        self.compute_group.setExclusive(True)
        self.compute_buttons = {}
        for mode, text, _color, tip in COMPUTE_BUTTONS:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setToolTip(tip)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, value=mode: self.choose_compute(value))
            self.compute_group.addButton(button)
            self.compute_buttons[mode] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        box.addLayout(buttons)
        self.title = QLabel("IAS")
        self.title.setStyleSheet(TITLE_STYLE)
        box.addWidget(self.title)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(1)
        grid.setColumnStretch(2, 1)
        self.dots, self.states, self.models = {}, {}, {}
        for row, (key, name, model, _needle) in enumerate(MODELS):
            dot, label, small, state = QLabel("●"), QLabel(name), QLabel(model), QLabel()
            label.setStyleSheet(NAME_STYLE)
            small.setStyleSheet(MODEL_STYLE)
            state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(dot, row, 0)
            grid.addWidget(label, row, 1)
            grid.addWidget(small, row, 2)
            grid.addWidget(state, row, 3)
            self.dots[key], self.states[key], self.models[key] = dot, state, small
        box.addLayout(grid)
        self.refresh_now()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)

    def choose_compute(self, mode: str) -> None:
        if self._on_compute is not None:
            self._on_compute(mode)
        self.refresh_now()

    def _render_compute(self) -> None:
        try:
            current = str(self._compute() or "AUTO").upper()
        except Exception:
            current = "AUTO"
        for index, (mode, _text, color, _tip) in enumerate(COMPUTE_BUTTONS):
            button = self.compute_buttons[mode]
            checked = mode == current
            if button.isChecked() != checked:
                button.setChecked(checked)
            style = compute_button_style(index, len(COMPUTE_BUTTONS), color, checked)
            if button.styleSheet() != style:
                button.setStyleSheet(style)

    def refresh_now(self, processes=None) -> list:
        self._render_compute()
        if processes is not None:
            self._processes = processes
        try:
            server = self._local_server()
        except Exception:
            server = None
        rows = describe(server, self._processes)
        self.title.setText(title_for(rows))
        for row in rows:
            color = row["color"]
            self.dots[row["key"]].setStyleSheet(
                "color:%s;font-size:10px;background:transparent;border:0;" % color)
            state = self.states[row["key"]]
            state.setText(row["text"])
            self.models[row["key"]].setText(row["model"])
            state.setStyleSheet("color:%s;font-size:12px;background:transparent;border:0;"
                                % (color if row["active"] else "#7f93a3"))
        return rows

    def _tick(self):
        self.refresh_now()
        if not self._scanning:
            self._scanning = True
            threading.Thread(target=self._scan_in_background, name="AiStatusScan",
                             daemon=True).start()

    def _scan_in_background(self):
        try:
            self._processes = self._scan()
        except Exception:
            self._processes = []
        finally:
            self._scanning = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_click is not None:
            self._on_click()
        super().mousePressEvent(event)
