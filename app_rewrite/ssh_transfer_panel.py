"""Transferencia de arquivos em duas colunas: Windows | Linux.

Esquerda: pastas do Windows. Direita: pastas do Linux (SFTP).
"Enviar ->" manda o que esta selecionado no Windows para a pasta aberta no
Linux; "<- Baixar" traz o que esta selecionado no Linux para a pasta aberta
no Windows. Arquivos e pastas inteiras. Transferencias da IA (MCP) tambem
aparecem em "Recentes".
"""
import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSplitter, QStyle,
    QVBoxLayout, QWidget,
)

from ssh_transfer import DOWNLOAD, UPLOAD, list_local

PATH_ROLE = Qt.UserRole
DIR_ROLE = Qt.UserRole + 1


def human_size(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def remote_parent(path):
    path = (path or "/").rstrip("/") or "/"
    if path == "/":
        return "/"
    return path.rsplit("/", 1)[0] or "/"


class _Bridge(QObject):
    remote_listed = Signal(int, str, object, str)


class FileColumn(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        head.addWidget(self.title)
        head.addStretch(1)
        self.up_btn = QPushButton("Subir")
        self.refresh_btn = QPushButton("Atualizar")
        head.addWidget(self.up_btn)
        head.addWidget(self.refresh_btn)
        layout.addLayout(head)
        self.path = QLineEdit()
        layout.addWidget(self.path)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.list, 1)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.action_btn = QPushButton()
        layout.addWidget(self.action_btn)

    def fill(self, items):
        self.list.clear()
        style = self.style()
        dir_icon = style.standardIcon(QStyle.SP_DirIcon)
        file_icon = style.standardIcon(QStyle.SP_FileIcon)
        for item in items:
            label = item["name"] + ("/" if item["is_dir"] else f"   {human_size(item['size'])}")
            row = QListWidgetItem(dir_icon if item["is_dir"] else file_icon, label)
            row.setData(PATH_ROLE, item["path"])
            row.setData(DIR_ROLE, bool(item["is_dir"]))
            self.list.addItem(row)

    def selected_paths(self):
        return [i.data(PATH_ROLE) for i in self.list.selectedItems()]


class SshTransferPanel(QWidget):
    POLL_MS = 400

    def __init__(self, registry, channel_factory, parent=None, ask_overwrite=None,
                 local_start=None):
        super().__init__(parent)
        self.registry = registry
        self._channel_factory = channel_factory
        self._channel = None
        self._ask_overwrite = ask_overwrite or self._ask
        self._remote_seq = 0
        self._remote_loaded = False
        self._remote_lock = threading.Lock()
        self._active_id = None
        self._bridge = _Bridge()
        self._bridge.remote_listed.connect(self._on_remote_listed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        header = QLabel("Transferir arquivos  (Windows <-> Linux)")
        header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(header)
        split = QSplitter(Qt.Horizontal)
        self.local = FileColumn("Windows")
        self.remote = FileColumn("Linux")
        self.local.action_btn.setText("Enviar  ->")
        self.local.action_btn.setToolTip("Envia o que esta selecionado aqui para a pasta aberta no Linux.")
        self.remote.action_btn.setText("<-  Baixar")
        self.remote.action_btn.setToolTip("Baixa o que esta selecionado aqui para a pasta aberta no Windows.")
        split.addWidget(self.local)
        split.addWidget(self.remote)
        layout.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.overwrite = QCheckBox("Substituir se ja existir")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_label = QLabel("")
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setEnabled(False)
        bottom.addWidget(self.overwrite)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.cancel_btn)
        layout.addLayout(bottom)
        layout.addWidget(self.progress_label)
        self.recent = QLabel("")
        self.recent.setWordWrap(True)
        self.recent.setStyleSheet("color: #8a94a6;")
        layout.addWidget(self.recent)

        self.local.path.returnPressed.connect(lambda: self.open_local(self.local.path.text()))
        self.local.up_btn.clicked.connect(lambda: self.open_local(str(Path(self.local.path.text()).parent)))
        self.local.refresh_btn.clicked.connect(lambda: self.open_local(self.local.path.text()))
        self.local.list.itemDoubleClicked.connect(self._local_double)
        self.remote.path.returnPressed.connect(lambda: self.open_remote(self.remote.path.text()))
        self.remote.up_btn.clicked.connect(lambda: self.open_remote(remote_parent(self.remote.path.text())))
        self.remote.refresh_btn.clicked.connect(self.reconnect)
        self.remote.list.itemDoubleClicked.connect(self._remote_double)
        self.local.action_btn.clicked.connect(self.send_selected)
        self.remote.action_btn.clicked.connect(self.download_selected)
        self.cancel_btn.clicked.connect(self.cancel_active)

        self.open_local(local_start or str(Path.home()))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(self.POLL_MS)

    # ---------- Windows ----------
    def open_local(self, path):
        try:
            items = list_local(path)
        except Exception as exc:
            self.local.info.setText(str(exc))
            return
        self.local.path.setText(str(Path(path)))
        self.local.fill(items)
        self.local.info.setText(f"{len(items)} itens")

    def _local_double(self, item):
        if item.data(DIR_ROLE):
            self.open_local(item.data(PATH_ROLE))

    # ---------- Linux ----------
    def showEvent(self, event):
        super().showEvent(event)
        if not self._remote_loaded:
            self._remote_loaded = True
            self.open_remote(self.remote.path.text() or "")

    def reconnect(self):
        channel, self._channel = self._channel, None
        if channel is not None:
            threading.Thread(target=channel.close, daemon=True).start()
        self.open_remote(self.remote.path.text() or "")

    def open_remote(self, path):
        self._remote_seq += 1
        seq = self._remote_seq
        self.remote.info.setText("Carregando...")
        threading.Thread(target=self._list_remote_worker, args=(seq, path),
                         daemon=True).start()

    def _list_remote_worker(self, seq, path):
        try:
            with self._remote_lock:
                if self._channel is None:
                    self._channel = self._channel_factory()
                target = path or self._channel.home()
                real, items = self._channel.list_remote(target)
            self._bridge.remote_listed.emit(seq, real, items, "")
        except Exception as exc:
            self._bridge.remote_listed.emit(seq, path, None, f"{type(exc).__name__}: {exc}")

    def _on_remote_listed(self, seq, path, items, error):
        if seq != self._remote_seq:
            return
        if error:
            hint = ""
            if "known_hosts" in error or "BadHostKey" in error:
                hint = "  Use \"Testar conexao\" acima para conferir e aceitar a chave do servidor."
            self.remote.info.setText("Sem conexao com o Linux: " + error + hint)
            return
        self.remote.path.setText(path)
        self.remote.fill(items)
        self.remote.info.setText(f"{len(items)} itens")

    def _remote_double(self, item):
        if item.data(DIR_ROLE):
            self.open_remote(item.data(PATH_ROLE))

    # ---------- transferencias ----------
    def send_selected(self):
        sources = self.local.selected_paths()
        destination = self.remote.path.text().strip()
        if not sources:
            self.progress_label.setText("Selecione arquivos ou pastas no Windows.")
            return
        if not destination:
            self.progress_label.setText("Abra uma pasta no Linux primeiro.")
            return
        self.start(UPLOAD, sources, destination)

    def download_selected(self):
        sources = self.remote.selected_paths()
        destination = self.local.path.text().strip()
        if not sources:
            self.progress_label.setText("Selecione arquivos ou pastas no Linux.")
            return
        self.start(DOWNLOAD, sources, destination)

    def start(self, direction, sources, destination, overwrite=None):
        if self._active_id is not None:
            self.progress_label.setText("Ja existe uma transferencia em andamento.")
            return None
        overwrite = self.overwrite.isChecked() if overwrite is None else overwrite
        status = self.registry.start(direction, sources, destination,
                                     overwrite=overwrite, origin="TELA")
        self._active_id = status["id"]
        self.progress.setValue(0)
        self.cancel_btn.setEnabled(True)
        self.local.action_btn.setEnabled(False)
        self.remote.action_btn.setEnabled(False)
        self.progress_label.setText("Preparando...")
        return status

    def cancel_active(self):
        if self._active_id:
            self.registry.cancel(self._active_id)
            self.progress_label.setText("Cancelando...")

    def _poll(self):
        if self._active_id is not None:
            try:
                status = self.registry.status(self._active_id)
            except KeyError:
                status = {"state": "FAILED", "error": "transferencia sumiu"}
            self._show(status)
        self._show_recent()

    def _show(self, status):
        prog = status.get("progress") or {}
        total = int(prog.get("total_bytes") or 0)
        done = int(prog.get("done_bytes") or 0)
        if total:
            self.progress.setValue(int(done * 100 / total))
        state = status.get("state")
        if state == "RUNNING":
            name = os.path.basename(str(prog.get("file") or "")) or "..."
            self.progress_label.setText(
                f"{name}  {human_size(done)} de {human_size(total)}  "
                f"({prog.get('done_files', 0)}/{prog.get('total_files', 0)} arquivos)")
            return
        self._finish(status)

    def _finish(self, status):
        self._active_id = None
        self.cancel_btn.setEnabled(False)
        self.local.action_btn.setEnabled(True)
        self.remote.action_btn.setEnabled(True)
        state = status.get("state")
        if state == "DONE":
            result = status.get("result") or {}
            skipped = result.get("skipped") or []
            extra = f", {len(skipped)} ignorados" if skipped else ""
            self.progress.setValue(100)
            self.progress_label.setText(
                f"Pronto: {result.get('files', 0)} arquivos, "
                f"{human_size(result.get('bytes', 0))}{extra}.")
            if status.get("direction") == UPLOAD:
                self.open_remote(self.remote.path.text())
            else:
                self.open_local(self.local.path.text())
        elif state == "CONFLICT":
            conflicts = status.get("conflicts") or []
            if self._ask_overwrite(conflicts):
                self.start(status["direction"], status["sources"], status["destination"],
                           overwrite=True)
            else:
                self.progress_label.setText("Nada foi transferido: itens ja existem no destino.")
        elif state == "CANCELLED":
            self.progress_label.setText("Cancelado. O que ja tinha chegado inteiro foi mantido.")
        else:
            self.progress_label.setText("Falhou: " + str(status.get("error") or "erro desconhecido"))

    def _show_recent(self):
        try:
            items = self.registry.recent(4)
        except Exception:
            return
        lines = []
        for item in items:
            arrow = "Windows -> Linux" if item.get("direction") == UPLOAD else "Linux -> Windows"
            who = "IA" if item.get("origin") == "IA" else "voce"
            lines.append(f"{arrow} ({who}): {item.get('state')}")
        self.recent.setText(("Recentes:  " + "  |  ".join(lines)) if lines else "")

    def _ask(self, conflicts):
        shown = "\n".join(conflicts[:8]) + ("\n..." if len(conflicts) > 8 else "")
        answer = QMessageBox.question(
            self, "Ja existe no destino",
            f"{len(conflicts)} item(ns) ja existem no destino:\n\n{shown}\n\nSubstituir?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes