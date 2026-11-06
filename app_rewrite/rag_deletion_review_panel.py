"""RAG-DEL Qt surface: review, confirmed removal and undo of indexed knowledge.

Source files are never deleted: only the project's indexed knowledge
(SQLite/FTS/manifest/vectors) is rebuilt without the selected files.
"""
from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)
from rag_deletion_selector import KnowledgeRemovalSelector
from rag.runtime.knowledge_deletion_review import build_deletion_review


def _execute(*args, **kwargs):
    from rag.runtime.knowledge_deletion_operational import execute_knowledge_removal
    return execute_knowledge_removal(*args, **kwargs)


def _rollback(transaction):
    from rag.runtime.knowledge_deletion_operational import rollback_knowledge_removal
    return rollback_knowledge_removal(transaction)


def _pending(project_id):
    from rag.runtime.knowledge_deletion_operational import pending_removal
    return pending_removal(project_id)


class KnowledgeRemovalReviewPanel(QWidget):
    """Review first, then remove after typing the project name; undo the last one."""

    BLOCKED_REASON = "Confira a exclusão antes de executar."
    PUBLIC_REASON = "Exclusão do índice público não é permitida."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_id = ""
        self._files: list[str] = []
        self._busy = False
        self._events: queue.Queue = queue.Queue()
        self._undo_transaction = None
        self._removed_last: list[str] = []
        self.selector = KnowledgeRemovalSelector(self)
        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Selecione os arquivos e confira a prévia.")
        self.last_review = None
        self.delete_button = QPushButton("Excluir conhecimentos", self)
        self.delete_button.setObjectName("ragDeletionAction")
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip(
            "Remove do índice os arquivos conferidos. Os arquivos de origem não são apagados.")
        self.undo_button = QPushButton("Desfazer última exclusão", self)
        self.undo_button.setObjectName("ragDeletionUndo")
        self.undo_button.setEnabled(False)
        self.delete_status = QLabel(self.BLOCKED_REASON, self)
        self.delete_status.setWordWrap(True)

        root = QVBoxLayout(self)
        root.addWidget(self.selector)
        root.addWidget(self.details)
        root.addWidget(self.delete_button)
        root.addWidget(self.undo_button)
        root.addWidget(self.delete_status)
        self.selector.preview_requested.connect(self.review_selected)
        self.delete_button.clicked.connect(self.request_removal)
        self.undo_button.clicked.connect(self.request_undo)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_events)
        self._timer.start(150)

    # ---------------------------------------------------------------- state
    def _refresh_buttons(self):
        public = self.project_id == "codebridge"
        self.delete_button.setEnabled(
            not self._busy and not public and self.last_review is not None)
        self.undo_button.setEnabled(not self._busy and self._undo_transaction is not None)
        self.selector.setEnabled(not self._busy)

    def set_project_files(self, project_id: str, filenames: list[str]):
        self.project_id = project_id
        self._files = list(filenames)
        self.last_review = None
        self.details.clear()
        self.selector.set_files(filenames)
        self._undo_transaction = None
        if project_id == "codebridge":
            self.selector.preview_button.setEnabled(False)
            self.delete_status.setText(self.PUBLIC_REASON)
            self.details.setPlainText(self.PUBLIC_REASON)
        else:
            self.delete_status.setText(self.BLOCKED_REASON)
            try:
                pending = _pending(project_id)
            except Exception:
                pending = None
            if pending:
                self._undo_transaction = pending["transaction"]
        self._refresh_buttons()

    def review_selected(self, selected: list[str]):
        self.last_review = None
        self.details.clear()
        if not selected or self.project_id == "codebridge":
            self._refresh_buttons()
            return
        try:
            review = build_deletion_review(self.project_id, selected)
        except (ValueError, OSError, RuntimeError) as error:
            self.details.setPlainText("Prévia bloqueada: " + str(error))
            self._refresh_buttons()
            return
        if not self._review_is_genuine(review, selected):
            shown = review.get("display_text", "") if isinstance(review, dict) else ""
            self.details.setPlainText(
                (str(shown) + "\n\n" if shown else "")
                + "Prévia bloqueada para execução: revisão inválida ou adulterada.")
            self._refresh_buttons()
            return
        self.last_review = review
        self.details.setPlainText(review["display_text"].replace(
            "SIMULAÇÃO: nenhum conhecimento foi removido.",
            "Prévia conferida. Use \"Excluir conhecimentos\" para executar."))
        self.delete_status.setText("Prévia conferida: pronta para excluir.")
        self._refresh_buttons()

    def _review_is_genuine(self, review, selected) -> bool:
        if not isinstance(review, dict):
            return False
        digest = review.get("review_sha256")
        return (review.get("state") == "READ_ONLY_REVIEW"
                and review.get("project_id") == self.project_id
                and review.get("selected_paths") == sorted(selected)
                and isinstance(digest, str) and len(digest) == 64
                and all(c in "0123456789abcdef" for c in digest)
                and review.get("execution_enabled") is False
                and isinstance(review.get("documents_to_remove"), int)
                and review["documents_to_remove"] > 0
                and isinstance(review.get("display_text"), str))

    # --------------------------------------------------------------- remove
    def request_removal(self):
        review = self.last_review
        if review is None or self._busy:
            return
        count = review["documents_to_remove"]
        text, ok = QInputDialog.getText(
            self, "Confirmar exclusão",
            f"Remover {count} arquivo(s) do conhecimento do projeto \"{self.project_id}\"?\n"
            "Os arquivos de origem NÃO são apagados e dá para desfazer em seguida.\n\n"
            "Digite o nome do projeto para confirmar:",
            QLineEdit.Normal, "")
        if not ok:
            return
        if text.strip() != self.project_id:
            QMessageBox.warning(self, "Exclusão cancelada", "O nome digitado não confere.")
            return
        self._start("remove", _execute, self.project_id, list(review["selected_paths"]),
                    review["review_sha256"], text.strip(), progress=self._progress)

    def request_undo(self):
        if self._undo_transaction is None or self._busy:
            return
        answer = QMessageBox.question(
            self, "Desfazer exclusão",
            "Restaurar a geração anterior do projeto, com os conhecimentos removidos?")
        if answer != QMessageBox.Yes:
            return
        self._start("undo", _rollback, self._undo_transaction)

    # -------------------------------------------------------------- worker
    def _progress(self, message: str):
        self._events.put(("progress", message))

    def _start(self, kind, function, *args, **kwargs):
        self._busy = True
        self._refresh_buttons()
        self.delete_status.setText("Excluindo..." if kind == "remove" else "Desfazendo...")

        def worker():
            try:
                self._events.put((kind, True, function(*args, **kwargs)))
            except Exception as error:  # noqa: BLE001 - shown to the operator
                self._events.put((kind, False, f"{type(error).__name__}: {error}"))

        threading.Thread(target=worker, name="CodeBridgeKnowledgeRemoval", daemon=True).start()

    def _drain_events(self):
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            if event[0] == "progress":
                self.delete_status.setText(event[1])
                continue
            kind, ok, payload = event
            self._busy = False
            if kind == "remove" and ok:
                removed = list(payload["removed_files"])
                self._removed_last = removed
                self._undo_transaction = payload["transaction"]
                self._files = [f for f in self._files if f not in removed]
                self.selector.set_files(self._files)
                self.last_review = None
                self.details.setPlainText(
                    f"Exclusão concluída no projeto {payload['project_id']}.\n"
                    f"Arquivos removidos do conhecimento: {payload['documents_removed']}\n"
                    f"Chunks removidos: {payload['chunks_removed']}\n"
                    f"Arquivos preservados: {payload['documents_preserved']}\n"
                    f"Geração anterior: {payload['previous_generation']}\n"
                    f"Nova geração: {payload['generation']}\n\n"
                    "Os arquivos de origem não foram alterados.")
                self.delete_status.setText("Exclusão concluída. Dá para desfazer.")
            elif kind == "undo" and ok:
                self._files = sorted(set(self._files) | set(self._removed_last))
                self._removed_last = []
                self._undo_transaction = None
                self.selector.set_files(self._files)
                self.details.setPlainText("Exclusão desfeita: a geração anterior foi restaurada.")
                self.delete_status.setText("Exclusão desfeita.")
            else:
                label = "Exclusão falhou" if kind == "remove" else "Desfazer falhou"
                self.details.setPlainText(label + ": " + str(payload))
                self.delete_status.setText(label + ". Nada foi alterado sem verificação.")
            self._refresh_buttons()