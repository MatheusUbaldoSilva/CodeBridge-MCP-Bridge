"""Central RAG - aba Indexar: escolher, conferir, indexar e ativar num lugar so.

Junta as antigas abas "Adicionar" e "Indexacao automatica". Projeto novo e
ativado pelo canario isolado; projeto existente recebe os arquivos por
juncao (RAG-ADD-01). Toda alteracao do conhecimento pede o nome do projeto
digitado e pode ser desfeita em seguida.
"""
from __future__ import annotations

import os
import queue
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from rag_deletion_review_panel import DOT, PANEL, KnowledgeFileTree

BLUE = "#2b6cb0"
ELL = "…"
STEPS = ("Escolher", "Conferir", "Indexar", "Ativar")
RUNNING = ("RUNNING", "PAUSE_REQUESTED", "CANCEL_REQUESTED")
LABELS = {"load": "Carregando", "preview": "Conferindo os arquivos",
          "queue": "Aprovando e iniciando a indexação", "start": "Iniciando a indexação",
          "review": "Preparando a ativação", "activate": "Ativando", "undo": "Desfazendo",
          "control": "Enviando o pedido", "resume": "Continuando"}


def _flow():
    from rag.runtime import knowledge_index_flow
    return knowledge_index_flow


class ConfirmByNameDialog(QDialog):
    def __init__(self, title, html, project_id, ok_text, color=BLUE, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        box = QLabel(html)
        box.setWordWrap(True)
        box.setStyleSheet(PANEL + "padding:10px;")
        lay.addWidget(box)
        lay.addWidget(QLabel(f"Digite <b>{project_id}</b> para confirmar:"))
        self.name = QLineEdit(self)
        self.name.setPlaceholderText(project_id)
        lay.addWidget(self.name)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancelar", self)
        self.ok = QPushButton(ok_text, self)
        self.ok.setEnabled(False)
        self.ok.setStyleSheet(
            f"QPushButton{{background:{color};color:white;font-weight:700;padding:6px 14px;}}"
            "QPushButton:disabled{background:#2a3440;color:#7f8a94;}")
        cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self.accept)
        self.name.textChanged.connect(lambda t: self.ok.setEnabled(t.strip() == project_id))
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)

    def confirmation(self):
        return self.name.text().strip()


class KnowledgeIndexPanel(QWidget):
    knowledge_changed = Signal(str)

    def __init__(self, parent=None, flow=None):
        super().__init__(parent)
        self.flow = flow or _flow()
        self.project_id = ""
        self.root = ""
        self.preview = None
        self.preview_paths = None
        self.job = None
        self.status = None
        self.undo_info = None
        self._busy = False
        self._events = queue.Queue()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.steps = QLabel(self)
        self.steps.setTextFormat(Qt.RichText)
        lay.addWidget(self.steps)

        self.banner = QFrame(self)
        self.banner.setStyleSheet("QFrame{background:#12324a;border:1px solid #2b6cb0;border-radius:6px;}")
        row = QHBoxLayout(self.banner)
        row.setContentsMargins(12, 6, 12, 6)
        self.banner_text = QLabel("", self.banner)
        self.banner_text.setStyleSheet("border:0;color:#e6f0f7;")
        self.banner_text.setWordWrap(True)
        self.progress = QProgressBar(self.banner)
        self.progress.setFixedWidth(220)
        self.progress.setTextVisible(False)
        self.undo_button = QPushButton("Desfazer", self.banner)
        self.undo_button.setCursor(Qt.PointingHandCursor)
        self.undo_button.setStyleSheet(
            "QPushButton{background:transparent;color:#7fc4ff;border:0;font-weight:700;"
            "text-decoration:underline;}QPushButton:disabled{color:#5b6670;}")
        self.undo_button.clicked.connect(self.request_undo)
        row.addWidget(self.banner_text, 1)
        row.addWidget(self.progress)
        row.addWidget(self.undo_button)
        self.banner.hide()
        lay.addWidget(self.banner)

        pick = QHBoxLayout()
        self.folder = QLineEdit(self)
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText("Escolha uma pasta com documentos ou código")
        self.folder_button = QPushButton("Escolher pasta", self)
        self.files_button = QPushButton("Escolher arquivos", self)
        self.folder_button.clicked.connect(self.choose_folder)
        self.files_button.clicked.connect(self.choose_files)
        pick.addWidget(self.folder, 1)
        pick.addWidget(self.folder_button)
        pick.addWidget(self.files_button)
        lay.addLayout(pick)

        self.selector = KnowledgeFileTree(self)
        self.selector.tree.setHeaderLabels(["Caminho", "Tipo", "", ""])
        self.selector.on_change(self._render)
        lay.addWidget(self.selector, 1)

        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(64)
        self.details.setPlaceholderText("Os detalhes do trabalho aparecem aqui.")
        self.details.setStyleSheet("QPlainTextEdit{" + PANEL + "color:#9fb0bd;padding:4px 8px;}")
        lay.addWidget(self.details)

        footer = QFrame(self)
        footer.setStyleSheet("QFrame{" + PANEL + "}")
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(12, 8, 12, 8)
        self.footer_text = QLabel("", footer)
        self.footer_text.setWordWrap(True)
        self.footer_text.setStyleSheet("border:0;color:#e6f0f7;font-weight:600;")
        self.pause_button = QPushButton("Pausar", footer)
        self.cancel_button = QPushButton("Cancelar trabalho", footer)
        self.primary = QPushButton("Conferir arquivos", footer)
        self.primary.setStyleSheet(
            f"QPushButton{{background:{BLUE};color:white;font-weight:700;padding:6px 16px;}}"
            "QPushButton:disabled{background:#22303c;color:#7f8a94;}")
        self.pause_button.clicked.connect(self.request_pause_resume)
        self.cancel_button.clicked.connect(self.request_cancel)
        self.primary.clicked.connect(self.primary_action)
        frow.addWidget(self.footer_text, 1)
        frow.addWidget(self.pause_button)
        frow.addWidget(self.cancel_button)
        frow.addWidget(self.primary)
        lay.addWidget(footer)

        self._drain = QTimer(self)
        self._drain.timeout.connect(self._drain_events)
        self._drain.start(150)
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._poll_status)
        self._poll.start(2000)
        self._render()
    # ------------------------------------------------------------ state
    def set_project(self, project_id):
        self.project_id = project_id or ""
        self.root = ""
        self.preview = None
        self.folder.clear()
        self.selector.set_files([])
        self.details.clear()
        self.banner.hide()
        self.job = self.status = self.undo_info = None
        if self.project_id and self.project_id != "codebridge":
            self._start("load", self._load, self.project_id)
        self._render()

    def _load(self, project_id):
        job = self.flow.current_job(project_id)
        status = self.flow.status(job["job_id"]) if job else None
        return {"job": job, "status": status, "undo": self.flow.pending_undo(project_id)}

    def _state(self):
        return (self.status or self.job or {}).get("state")

    def _step(self):
        if self._state() == "READY_FOR_REVIEW":
            return 3
        if self.job is not None:
            return 2
        return 1 if self.preview is not None else 0

    def _render(self):
        current = self._step()
        parts = []
        for number, name in enumerate(STEPS):
            color = "#ffffff" if number == current else ("#7fc4ff" if number < current else "#5b6670")
            weight = "700" if number == current else "400"
            parts.append(f"<span style='color:{color};font-weight:{weight}'>{number + 1} {name}</span>")
        self.steps.setText(" <span style='color:#5b6670'>&rsaquo;</span> ".join(parts))
        public = self.project_id == "codebridge"
        state = self._state()
        choosing = self.job is None and not self._busy and not public and bool(self.project_id)
        for widget in (self.folder_button, self.files_button, self.selector):
            widget.setEnabled(choosing)
        active = ("QUEUED", "PAUSED") + RUNNING
        self.pause_button.setVisible(self.job is not None and state in active)
        self.cancel_button.setVisible(self.job is not None and state in active + ("DRAFT", "AWAITING_APPROVAL"))
        self.pause_button.setText("Continuar" if state == "PAUSED" else "Pausar")
        self.pause_button.setEnabled(not self._busy and state in ("QUEUED", "PAUSED", "RUNNING"))
        self.cancel_button.setEnabled(not self._busy and state != "CANCEL_REQUESTED")
        self.undo_button.setVisible(self.undo_info is not None)
        self.undo_button.setEnabled(not self._busy and self.undo_info is not None)
        label, enabled, text = "Conferir arquivos", False, ""
        if public:
            text = "O índice público não recebe arquivos por aqui. Escolha ou crie outro projeto."
        elif not self.project_id:
            text = "Escolha um projeto."
        elif self.job is None:
            if self.preview is None:
                enabled = bool(self.root)
                text = "Escolha a pasta ou os arquivos que entram no conhecimento."
            else:
                chosen = self.selector.selected_paths()
                kinds = self._kinds(chosen)
                label, enabled = f"Indexar {len(chosen)} arquivo(s)", bool(chosen)
                text = (f"{len(chosen)} selecionado(s){DOT}{kinds['CODE']} código{DOT}{kinds['TEXT']} texto"
                        if chosen else "Marque ao menos um arquivo.")
        elif state == "QUEUED":
            label, enabled, text = "Iniciar indexação", True, "Arquivos aprovados e na fila."
        elif state in RUNNING:
            label, text = "Indexando" + ELL, self._progress_text()
        elif state == "PAUSED":
            label, text = "Indexação pausada", "Pausado com segurança entre lotes."
        elif state == "READY_FOR_REVIEW":
            label, enabled = "Ativar no projeto" + ELL, True
            text = "Indexação concluída. Falta ativar para o projeto usar os arquivos."
        else:
            text = "Trabalho em estado " + str(state) + "."
        self.primary.setText(label)
        self.primary.setEnabled(enabled and not self._busy)
        self.footer_text.setText(text)

    def _kinds(self, paths):
        kinds = {"CODE": 0, "TEXT": 0}
        index = {s["path"]: s.get("index_kind") for s in (self.preview or {}).get("sources", [])}
        for path in paths:
            kinds["CODE" if index.get(path) == "CODE" else "TEXT"] += 1
        return kinds

    def _progress_text(self):
        status = self.status or {}
        done, expected = status.get("vectors_done") or 0, status.get("vectors_expected") or 0
        return f"Indexando{DOT}{done} de {expected} trechos" if expected else "Indexando" + ELL

    def _banner(self, text, *, busy=False, value=None):
        self.banner_text.setText(text)
        self.progress.setVisible(busy or value is not None)
        if value is None:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(value))
        self.banner.show()

    # ------------------------------------------------------------ choose
    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Escolher pasta")
        if folder:
            self.set_root(folder, None)

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Escolher arquivos")
        if files:
            root = os.path.commonpath([str(Path(f).parent) for f in files])
            self.set_root(root, sorted(Path(f).relative_to(root).as_posix() for f in files))

    def set_root(self, root, paths=None):
        self.root = str(Path(root))
        self.folder.setText(self.root)
        self.preview = None
        self.preview_paths = list(paths) if paths else None
        self.selector.set_files([])
        self._start("preview", self.flow.preview, self.project_id, self.root, paths)

    # ------------------------------------------------------------ actions
    def primary_action(self):
        if self._busy:
            return
        state = self._state()
        if self.job is None and self.preview is None:
            if self.root:
                self._start("preview", self.flow.preview, self.project_id, self.root,
                            self.preview_paths)
        elif self.job is None:
            self.request_index()
        elif state == "QUEUED":
            self._start("start", self.flow.start, self.job["job_id"])
        elif state == "READY_FOR_REVIEW":
            self._start("review", self.flow.activation_review, self.project_id, self.job["job_id"])

    def request_index(self):
        chosen = self.selector.selected_paths()
        if not chosen:
            return
        everything = len(chosen) == self.selector.leaf_count()
        kinds = self._kinds(chosen)
        html = (f"<b>Indexar {len(chosen)} arquivo(s) em {self.project_id}?</b><br>"
                f"{kinds['CODE']} de código (placa de vídeo){DOT}{kinds['TEXT']} de texto (processador)<br>"
                f"Pasta: {self.root}<br><span style='color:#7fa7c9'>Os arquivos de origem não são "
                "alterados. Nada muda no projeto até você ativar no fim.</span>")
        dialog = ConfirmByNameDialog("Indexar arquivos", html, self.project_id, "Indexar", parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.confirmation() != self.project_id:
            return
        # A aprovacao precisa da MESMA lista usada na previa (pasta inteira
        # ou os arquivos escolhidos); outra lista muda o SHA e e recusada.
        self._start("queue", self._queue_and_start, self.project_id, self.root,
                    self.preview_paths if everything else chosen,
                    self.preview["review_sha256"] if everything else None)

    def _queue_and_start(self, project_id, root, paths, review_sha256):
        if review_sha256 is None:
            review_sha256 = self.flow.preview(project_id, root, paths)["review_sha256"]
        queued = self.flow.queue(project_id, root, paths, review_sha256)
        return {"queued": queued, "started": self.flow.start(queued["job_id"])}

    def request_pause_resume(self):
        if not self.job or self._busy:
            return
        if self._state() == "PAUSED":
            self._start("resume", self._resume, self.job["job_id"])
        else:
            self._start("control", self.flow.control, self.job["job_id"], "PAUSE")

    def _resume(self, job_id):
        self.flow.control(job_id, "RESUME")
        return self.flow.start(job_id)

    def request_cancel(self):
        if not self.job or self._busy:
            return
        answer = QMessageBox.question(
            self, "Cancelar trabalho",
            "Cancelar este trabalho de indexação? O conhecimento do projeto não muda.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self._start("control", self.flow.control, self.job["job_id"], "CANCEL")

    def _confirm_activation(self, review):
        if review["mode"] == "MERGE":
            html = (f"<b>Juntar ao projeto {self.project_id}?</b><br>"
                    f"Novos: <b>{len(review['added_paths'])}</b> arquivo(s){DOT}"
                    f"atualizados: <b>{len(review['replaced_paths'])}</b><br>"
                    f"O projeto passa de {review['documents_before']} para "
                    f"<b>{review['documents_after']}</b> arquivos "
                    f"({review['chunks_before']} para {review['chunks_after']} trechos).<br>"
                    "<span style='color:#7fa7c9'>Dá para desfazer em seguida.</span>")
        else:
            html = (f"<b>Criar o projeto {self.project_id} com estes arquivos?</b><br>"
                    f"{review.get('documents_after')} arquivo(s){DOT}{review.get('chunks_after')} trechos<br>"
                    "<span style='color:#7fa7c9'>Dá para desfazer em seguida.</span>")
        dialog = ConfirmByNameDialog("Ativar no projeto", html, self.project_id,
                                     "Ativar no projeto", parent=self)
        if dialog.exec() != QDialog.Accepted or dialog.confirmation() != self.project_id:
            self.details.setPlainText("Ativação cancelada; nada mudou no projeto.")
            return
        self._start("activate", self.flow.activate, self.project_id, self.job["job_id"], review,
                    dialog.confirmation(), progress=self._progress_event)

    def request_undo(self):
        if self.undo_info is None or self._busy:
            return
        self._start("undo", self.flow.undo, self.project_id)
    # ------------------------------------------------------------ worker
    def _progress_event(self, message):
        self._events.put(("progress", message))

    def _start(self, kind, function, *args, **kwargs):
        self._busy = True
        if kind != "status":
            self._banner(LABELS.get(kind, "Trabalhando") + ELL, busy=True)
        self._render()
        project = self.project_id

        def worker():
            try:
                self._events.put((kind, True, project, function(*args, **kwargs)))
            except Exception as error:  # noqa: BLE001 - shown to the operator
                self._events.put((kind, False, project, f"{type(error).__name__}: {error}"))

        threading.Thread(target=worker, name="CodeBridgeIndexPanel", daemon=True).start()

    def _poll_status(self):
        if self._busy or not self.job:
            return
        if self._state() in RUNNING + ("QUEUED", "PAUSED"):
            self._start("status", self.flow.status, self.job["job_id"])

    def _drain_events(self):
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            if event[0] == "progress":
                self._banner("Ativando" + ELL + " " + str(event[1]), busy=True)
                continue
            kind, ok, project, payload = event
            self._busy = False
            if project == self.project_id:
                self._handle(kind, ok, payload)
            self._render()

    def _clear_choice(self):
        self.job = self.status = self.preview = None
        self.root = ""
        self.folder.clear()
        self.selector.set_files([])
        self.details.clear()

    def _handle(self, kind, ok, payload):
        if not ok:
            if kind == "status":
                self.details.setPlainText("Status indispon\u00edvel: " + str(payload))
                return
            self._banner("N\u00e3o foi poss\u00edvel concluir. Nada mudou no projeto sem verifica\u00e7\u00e3o.")
            self.details.setPlainText(str(payload))
            return
        if kind == "load":
            self.job, self.status, self.undo_info = payload["job"], payload["status"], payload["undo"]
            self.banner.hide()
            if self.undo_info:
                self._banner("H\u00e1 uma ativa\u00e7\u00e3o recente neste projeto que ainda pode ser desfeita.")
            self._show_status()
        elif kind == "preview":
            self.preview = payload
            sources = payload.get("sources") or []
            self.selector.set_files([s["path"] for s in sources], {},
                                    {s["path"]: s.get("index_kind", "") for s in sources})
            self.selector.tree.blockSignals(True)
            for leaf in self.selector._leaves.values():
                leaf.setCheckState(0, Qt.Checked)
            self.selector.tree.blockSignals(False)
            self.selector.tree.expandToDepth(0)
            skipped = sum(payload.get(k) or 0 for k in ("denied_count", "unsupported_count", "sensitive_count"))
            self.banner.hide()
            self.details.setPlainText(
                f"{payload.get('candidate_count', 0)} arquivo(s) podem entrar"
                + (f"{DOT}{skipped} ignorado(s) (sem suporte, sens\u00edveis ou negados)" if skipped else ""))
        elif kind == "queue":
            self.job = {"job_id": payload["queued"]["job_id"], "state": "QUEUED"}
            self._after_start(payload["started"])
        elif kind in ("start", "resume"):
            self._after_start(payload)
        elif kind == "status":
            self.status = payload
            self._show_status()
        elif kind == "control":
            if payload.get("state") == "CANCELLED":
                self._clear_choice()
                self._banner("Trabalho cancelado. O conhecimento do projeto n\u00e3o mudou.")
            else:
                self.status = {**(self.status or {}), "state": payload.get("state")}
                self._show_status()
        elif kind == "review":
            self.banner.hide()
            self._confirm_activation(payload)
        elif kind == "activate":
            self._clear_choice()
            self.undo_info = {"mode": payload.get("mode")}
            if payload.get("mode") == "MERGE":
                self._banner(f"{len(payload.get('added_files', []))} novo(s){DOT}"
                             f"{len(payload.get('replaced_files', []))} atualizado(s){DOT}"
                             f"projeto com {payload.get('documents')} arquivos")
            else:
                self._banner("Projeto criado e pronto para pesquisa.")
            self.knowledge_changed.emit(self.project_id)
        elif kind == "undo":
            self.undo_info = None
            self._banner("Ativa\u00e7\u00e3o desfeita: o projeto voltou \u00e0 vers\u00e3o anterior.")
            self.knowledge_changed.emit(self.project_id)

    def _after_start(self, started):
        if (started or {}).get("state") == "PROCESS_STARTED_UNVERIFIED":
            self.status = {"state": "RUNNING", "vectors_done": 0, "vectors_expected": 0}
            self._banner("Indexando" + ELL + " o progresso aparece aqui.", busy=True)
        else:
            self.status = {"state": "QUEUED"}
            self._banner("In\u00edcio adiado: mem\u00f3ria insuficiente. Tente de novo em instantes.")

    def _show_status(self):
        status = self.status or {}
        state = status.get("state")
        if state in RUNNING:
            value = status.get("percent") if status.get("percent_known") else None
            self._banner(self._progress_text(), busy=True, value=value)
        elif state == "READY_FOR_REVIEW":
            self._banner("Indexa\u00e7\u00e3o conclu\u00edda. Clique em Ativar no projeto.")
        if self.job:
            info = [f"Trabalho {self.job['job_id'][:8]}", str(state or self.job.get("state"))]
            if status.get("file_count"):
                info.append(f"{status['file_count']} arquivos")
            if status.get("chunk_count"):
                info.append(f"{status['chunk_count']} trechos")
            if status.get("last_error"):
                info.append("erro: " + str(status["last_error"]))
            self.details.setPlainText(DOT.join(info))