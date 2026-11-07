"""Central RAG - chave de atualizacao do conhecimento: Automatico / Desligado / Manual.

Vigia a pasta escolhida do projeto. No Automatico atualiza sozinho; no Manual
so avisa e espera o clique. Cada atualizacao pode ser desfeita.
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)

ELL = chr(0x2026)
DOT = " " + chr(0xB7) + " "
A_ACUTE, C_CED, A_TILDE, E_ACUTE, O_ACUTE = chr(0xE1), chr(0xE7), chr(0xE3), chr(0xE9), chr(0xF3)
CHECK_MS = 30000
MODES = (
    ("AUTO", "Autom" + A_ACUTE + "tico", "#2f855a",
     "Vigia a pasta do projeto e atualiza o conhecimento sozinho quando um arquivo "
     + E_ACUTE + " criado, alterado ou apagado. Cada atualiza" + C_CED + A_TILDE + "o pode ser desfeita."),
    ("OFF", "Desligado", "#5b6670",
     "N" + A_TILDE + "o vigia a pasta. O conhecimento s" + O_ACUTE + " muda pelas abas "
     "Indexar e Meus arquivos."),
    ("MANUAL", "Manual", "#b7791f",
     "Vigia a pasta e avisa quantos arquivos mudaram; s" + O_ACUTE + " atualiza quando "
     "voc" + chr(0xEA) + " clicar em Atualizar agora."),
)
MUTED = "color:#8b9aa7;background:transparent;border:0;"


def _sync():
    from rag.runtime import knowledge_sync
    return knowledge_sync


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


def describe(changes) -> str:
    parts = []
    if changes.get("added"):
        parts.append(_plural(len(changes["added"]), "novo", "novos"))
    if changes.get("changed"):
        parts.append(_plural(len(changes["changed"]), "alterado", "alterados"))
    if changes.get("removed"):
        parts.append(_plural(len(changes["removed"]), "apagado", "apagados"))
    return ", ".join(parts)


class KnowledgeSyncBar(QWidget):
    knowledge_changed = Signal(str)

    def __init__(self, parent=None, sync=None, ask_folder=None, confirm=None):
        super().__init__(parent)
        self._sync_module = sync
        self._ask_folder = ask_folder or self._default_ask_folder
        self._confirm = confirm or self._default_confirm
        self._events = queue.Queue()
        self._seq = 0
        self._busy = None
        self.project_id = ""
        self.supported = False
        self.mode = "OFF"
        self.folder = None
        self.last = None
        self.can_undo = False
        self.changes = None
        self.error = ""
        self.progress = ""
        self.notice = ""
        self._last_fp = None
        self._pending_fp = None
        self._failed_fp = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        title = QLabel("Atualiza" + C_CED + A_TILDE + "o:")
        title.setStyleSheet(MUTED + "padding-right:8px;")
        row.addWidget(title)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for mode, text, _color, tip in MODES:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setToolTip(tip)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, m=mode: self.choose_mode(m))
            self.group.addButton(button)
            self.buttons[mode] = button
            row.addWidget(button)
        row.addSpacing(10)
        self.status = QLabel("")
        self.status.setStyleSheet(MUTED)
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(self.status, 1)
        self.folder_button = QPushButton("Pasta" + ELL)
        self.folder_button.setToolTip("Escolher a pasta do projeto que ser" + A_ACUTE + " vigiada")
        self.folder_button.clicked.connect(self.change_folder)
        self.apply_button = QPushButton("Atualizar agora")
        self.apply_button.setStyleSheet(
            "QPushButton{background:#2b6cb0;color:white;font-weight:700;padding:3px 12px;}")
        self.apply_button.clicked.connect(self.apply_now)
        self.undo_button = QPushButton("Desfazer")
        self.undo_button.setToolTip("Volta o conhecimento para antes da " + chr(0xFA) + "ltima atualiza"
                                    + C_CED + A_TILDE + "o")
        self.undo_button.clicked.connect(self.undo)
        for button in (self.folder_button, self.apply_button, self.undo_button):
            row.addSpacing(6)
            row.addWidget(button)

        self._drain_timer = QTimer(self)
        self._drain_timer.timeout.connect(self._drain)
        self._drain_timer.start(150)
        self._check_timer = QTimer(self)
        self._check_timer.timeout.connect(self.check)
        self._check_timer.start(CHECK_MS)
        self._render()

    @property
    def sync(self):
        if self._sync_module is None:
            self._sync_module = _sync()
        return self._sync_module
    # ----- trabalho em segundo plano -------------------------------------
    def _run(self, kind, fn, *args, **kwargs):
        self._seq += 1
        seq, token = self._seq, object()
        if kind not in ("load", "check"):
            self._busy = token
        progress = lambda message: self._events.put(("progress", seq, kind, message, None))

        def worker():
            try:
                if kind == "apply":
                    kwargs["progress"] = progress
                result, error = fn(*args, **kwargs), None
            except Exception as exc:
                result, error = None, str(exc) or exc.__class__.__name__
            self._events.put(("done", seq, kind, result, error, token))

        self._start(worker)
        self._render()

    def _start(self, worker):
        threading.Thread(target=worker, name="CodeBridgeKnowledgeSync", daemon=True).start()

    def _drain(self):
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            if event[0] == "progress":
                if self._busy is not None:
                    self.progress = event[3]
                    self._render()
                continue
            _, seq, kind, result, error, token = event
            if token is self._busy:
                self._busy = None
                self.progress = ""
            if seq == self._seq or kind in ("apply", "undo"):
                self._finish(kind, result, error)
            self._render()

    # ----- projeto e modo -------------------------------------------------
    def set_project(self, project_id):
        project_id = str(project_id or "")
        if project_id == self.project_id:
            return
        self.project_id = project_id
        self.supported, self.mode, self.folder, self.last = False, "OFF", None, None
        self.changes, self.error, self.can_undo = None, "", False
        self._last_fp = self._pending_fp = self._failed_fp = None
        if project_id:
            self._run("load", self._load, project_id)
        self._render()

    def _load(self, project_id):
        return {"project_id": project_id, "supported": self.sync.supported(project_id),
                "settings": self.sync.settings(project_id), "undo": self.sync.can_undo(project_id)}

    def choose_mode(self, mode):
        self.notice = ""
        if self._busy is not None or not self.supported:
            self._render()
            return
        if mode == "OFF":
            self._save(mode="OFF")
            self.mode, self.changes, self.error = "OFF", None, ""
            self._render()
            return
        folder = self.folder or self._ask_folder(self.project_id)
        if not folder:
            self._render()
            return
        self._run("enable", self._preview_enable, mode, str(folder))

    def _preview_enable(self, mode, folder):
        return {"mode": mode, "folder": folder, "fingerprint": self.sync.fingerprint(folder),
                "changes": self.sync.compute_changes(self.project_id, folder)}

    def change_folder(self):
        self.notice = ""
        if self._busy is not None or not self.supported:
            return
        folder = self._ask_folder(self.project_id)
        if not folder:
            return
        if self.mode == "OFF":
            self.folder = str(folder)
            self._save(folder=self.folder)
            self._render()
        else:
            self._run("enable", self._preview_enable, self.mode, str(folder))

    def _save(self, **changes):
        try:
            self.sync.update_settings(self.project_id, **changes)
        except Exception as exc:
            self.error = str(exc)

    # ----- verificacao periodica -----------------------------------------
    def check(self):
        if (self._busy is not None or not self.supported or self.mode == "OFF"
                or not self.folder):
            return False
        self._run("check", self.sync.fingerprint, self.folder)
        return True

    def apply_now(self):
        self.notice = ""
        if self._busy is None and self.changes and self.changes.get("total"):
            self._run("apply", self.sync.apply_changes, self.project_id, self.changes)

    def undo(self):
        if self._busy is None and self.can_undo:
            self._run("undo", self.sync.undo_last, self.project_id)
    def _diff(self, fp):
        return {"fingerprint": fp, "changes": self.sync.compute_changes(self.project_id, self.folder)}

    # ----- resultados -----------------------------------------------------
    def _finish(self, kind, result, error):
        if error:
            self.error = ("A atualiza" + C_CED + A_TILDE + "o falhou: " + error) if kind == "apply" else error
            if kind == "apply":
                self._failed_fp = self._last_fp
            return
        self.error = ""
        if kind == "load":
            if result["project_id"] != self.project_id:
                return
            state = result["settings"]
            self.supported = bool(result["supported"])
            self.mode, self.folder, self.last = state["mode"], state["folder"], state["last"]
            self.can_undo = bool(result["undo"])
            if self.mode != "OFF":
                self.check()
        elif kind == "enable":
            changes = result["changes"]
            if result["mode"] == "AUTO" and not self._confirm(self.project_id, result["folder"], changes):
                return
            self.mode, self.folder = result["mode"], result["folder"]
            self._save(mode=self.mode, folder=self.folder)
            self.changes = changes
            self._last_fp, self._pending_fp, self._failed_fp = result.get("fingerprint"), None, None
            if self.mode == "AUTO" and changes.get("total"):
                self.apply_now()
        elif kind == "check":
            if result == self._last_fp:
                self._pending_fp = None
            elif self._last_fp is None or result == self._pending_fp:
                self._pending_fp = None
                self._run("diff", self._diff, result)
            else:
                self._pending_fp = result
        elif kind == "diff":
            self._last_fp, self.changes = result["fingerprint"], result["changes"]
            if (self.mode == "AUTO" and self.changes.get("total")
                    and self._last_fp != self._failed_fp):
                self.apply_now()
        elif kind == "apply":
            if result.get("state") == "SYNCED":
                self.last, self.can_undo = result, True
            self.changes = {**(self.changes or {}), "added": [], "changed": [], "removed": [], "total": 0}
            self.knowledge_changed.emit(self.project_id)
        elif kind == "undo":
            self.can_undo, self.last = False, None
            self.knowledge_changed.emit(self.project_id)
            if self.mode == "AUTO":
                self.mode = "MANUAL"
                self._save(mode="MANUAL")
                self.notice = ("Desfeito. Mudei para Manual para n" + A_TILDE + "o atualizar de novo "
                              "sozinho; clique em Autom" + A_ACUTE + "tico quando quiser voltar.")
            self._last_fp = None
            self.check()

    # ----- desenho --------------------------------------------------------
    def _folder_name(self):
        return Path(self.folder).name if self.folder else ""

    def _last_text(self):
        if not self.last or not self.last.get("at"):
            return ""
        try:
            from datetime import datetime
            when = datetime.fromisoformat(self.last["at"]).astimezone().strftime("%H:%M")
        except (TypeError, ValueError):
            return ""
        what = describe({k: [0] * int(self.last.get(k) or 0) for k in ("added", "changed", "removed")})
        return "atualizado " + chr(0xE0) + "s " + when + (f" ({what})" if what else "")

    def status_text(self):
        if not self.project_id:
            return ""
        if not self.supported:
            return ("Dispon" + chr(0xED) + "vel para projetos com " + chr(0xED) + "ndice pr"
                    + O_ACUTE + "prio (criados pela aba Indexar).")
        if self._busy is not None:
            return self.progress or ("Conferindo a pasta" + ELL)
        if self.error:
            return self.error
        if self.mode == "OFF":
            return "Desligado" + DOT + (self._folder_name() or "nenhuma pasta escolhida")
        changes = self.changes or {}
        if changes.get("total"):
            text = _plural(changes["total"], "arquivo mudou", "arquivos mudaram") + " na pasta (" \
                + describe(changes) + ")"
        elif self.changes is not None:
            text = "Em dia com a pasta " + self._folder_name()
        else:
            text = "Vigiando a pasta " + self._folder_name()
        last = self._last_text()
        final = text + (DOT + last if last else "")
        return (self.notice + DOT + final) if self.notice else final

    def _render(self):
        idle = self._busy is None
        for index, (mode, _text, color, _tip) in enumerate(MODES):
            button = self.buttons[mode]
            checked = mode == self.mode
            if button.isChecked() != checked:
                button.setChecked(checked)
            button.setEnabled(self.supported and idle)
            radius = ("border-top-left-radius:6px;border-bottom-left-radius:6px;" if index == 0 else
                      "border-top-right-radius:6px;border-bottom-right-radius:6px;"
                      if index == len(MODES) - 1 else "")
            style = ("QPushButton{background:" + (color if checked else "#1b242c") + ";color:"
                     + ("white" if checked else "#9fb0bd") + ";border:1px solid #33414d;border-radius:0px;"
                     + radius + "padding:3px 12px;font-size:12px;font-weight:"
                     + ("700" if checked else "500") + ";}"
                     "QPushButton:disabled{color:#5f6b75;}")
            if button.styleSheet() != style:
                button.setStyleSheet(style)
        self.status.setText(self.status_text())
        self.status.setToolTip((self.folder or "") + ("\n" + describe(self.changes) if self.changes else ""))
        self.folder_button.setVisible(self.supported)
        self.folder_button.setEnabled(idle)
        self.apply_button.setVisible(bool(idle and self.supported and self.mode != "OFF"
                                          and self.changes and self.changes.get("total")))
        self.undo_button.setVisible(bool(idle and self.can_undo))

    # ----- dialogos -------------------------------------------------------
    def _default_ask_folder(self, project_id):
        start = self.folder or str(Path.home())
        return QFileDialog.getExistingDirectory(
            self, "Pasta do projeto " + project_id + " que ser" + A_ACUTE + " vigiada", start) or None

    def _default_confirm(self, project_id, folder, changes):
        from PySide6.QtWidgets import QDialog
        from rag_index_panel import ConfirmByNameDialog
        html = ("<b>Atualiza" + C_CED + A_TILDE + "o autom" + A_ACUTE + "tica</b><br>"
                "O conhecimento de <b>" + project_id + "</b> vai acompanhar a pasta<br><code>"
                + str(folder) + "</code><br><br>Arquivos novos e alterados entram; arquivos que "
                "n" + A_TILDE + "o est" + A_TILDE + "o na pasta saem do conhecimento. Cada "
                "atualiza" + C_CED + A_TILDE + "o pode ser desfeita.<br><br>Agora: <b>"
                + (describe(changes) or "nada a mudar") + "</b>.")
        dialog = ConfirmByNameDialog("Ligar atualiza" + C_CED + A_TILDE + "o autom" + A_ACUTE + "tica",
                                     html, project_id, "Ligar autom" + A_ACUTE + "tico", parent=self)
        return dialog.exec() == QDialog.Accepted