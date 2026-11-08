"""Card "IAs" no topo do CodeBridge: quais modelos estao ligados e onde rodam.

Fica ao lado do logo, no mesmo visual do cronometro. Le a IA Local pelo proprio
servidor e os modelos da Central RAG pelos processos llama-server em execucao
(argumentos -m, -ngl e --device), entao funciona seja quem for que os ligou.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

# (chave, nome na tela, modelo na tela, trecho do nome do arquivo .gguf)
MODELS = (
    ("LOCAL", "IA Local", "Qwen 7B", "qwen2.5-coder-7b"),
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


def describe(local_server, processes) -> list:
    """Linhas do card: dicts com key, name, model, text, color e active."""
    rows = []
    for key, name, model, needle in MODELS:
        device = _device_of(processes, needle)
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


def title_for(rows) -> str:
    active = sum(1 for row in rows if row["active"])
    if not active:
        return "IAS · NENHUMA ATIVA"
    return "IAS · %d ATIVA%s" % (active, "" if active == 1 else "S")


# ---- card --------------------------------------------------------------------
class AiStatusCard(QFrame):
    """Card clicavel (abre a aba IA Local). Varre os processos fora da tela."""

    def __init__(self, local_server=lambda: None, on_click=None, scan=scan_llama_servers,
                 parent=None, interval_ms: int = 2000):
        super().__init__(parent)
        self.setObjectName("aiStatusBox")
        self.setStyleSheet(BOX_STYLE)
        self.setMinimumWidth(230)
        self.setFixedHeight(84)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Status das IAs do CodeBridge · clique para abrir a IA Local")
        self._local_server, self._on_click, self._scan = local_server, on_click, scan
        self._processes, self._scanning = [], False

        box = QVBoxLayout(self)
        box.setContentsMargins(14, 8, 14, 8)
        box.setSpacing(3)
        self.title = QLabel("IAS")
        self.title.setStyleSheet(TITLE_STYLE)
        box.addWidget(self.title)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(1)
        grid.setColumnStretch(2, 1)
        self.dots, self.states = {}, {}
        for row, (key, name, model, _needle) in enumerate(MODELS):
            dot, label, small, state = QLabel("●"), QLabel(name), QLabel(model), QLabel()
            label.setStyleSheet(NAME_STYLE)
            small.setStyleSheet(MODEL_STYLE)
            state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(dot, row, 0)
            grid.addWidget(label, row, 1)
            grid.addWidget(small, row, 2)
            grid.addWidget(state, row, 3)
            self.dots[key], self.states[key] = dot, state
        box.addLayout(grid)
        self.refresh_now()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)

    def refresh_now(self, processes=None) -> list:
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
