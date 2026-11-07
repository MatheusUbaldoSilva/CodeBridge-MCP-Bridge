"""Central RAG - arquivos do projeto: lista unica com selecao, filtro,
detalhe, exclusao confirmada e Desfazer.

Somente o conhecimento indexado e removido (SQLite/FTS/manifest/vetores);
os arquivos de origem nunca sao apagados.
"""
from __future__ import annotations

import queue
import sqlite3
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QProgressBar, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)
from rag.runtime.knowledge_deletion_review import build_deletion_review

DOT = " \u00b7 "
RED = "#c0392b"
PANEL = "background:#0a1015;border:1px solid #33414d;border-radius:6px;"


def _execute(*args, **kwargs):
    from rag.runtime.knowledge_deletion_operational import execute_knowledge_removal
    return execute_knowledge_removal(*args, **kwargs)


def _rollback(transaction):
    from rag.runtime.knowledge_deletion_operational import rollback_knowledge_removal
    return rollback_knowledge_removal(transaction)


def _keep(transaction):
    from rag.runtime.knowledge_deletion_operational import keep_knowledge_removal
    return keep_knowledge_removal(transaction)


def _sync_module():
    import importlib
    return importlib.import_module("rag.runtime.knowledge_sync")


def _sync_last(project_id):
    try:
        return (_sync_module().settings(project_id) or {}).get("last") or {}
    except Exception:
        return {}


def _hhmm(stamp):
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(stamp)).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def pending_banner_text(pending, last=None):
    """Texto do aviso: o que saiu, quem pediu e quando."""
    last = last or {}
    files = [str(f) for f in (pending.get("removed_files") or [])]
    origin = pending.get("origin")
    stamp = pending.get("at")
    count = len(files)
    if last.get("transaction") and last.get("transaction") == pending.get("transaction"):
        origin = origin or "AUTO"
        stamp = last.get("at") or stamp
        count = count or int(last.get("removed") or 0)
    who = {"AUTO": " pela atualiza" + chr(0xE7) + chr(0xE3) + "o autom" + chr(0xE1) + "tica",
           "TELA": " por voc" + chr(0xEA)}.get(str(origin or "").upper(), "")
    if count == 1:
        head = "1 arquivo removido do conhecimento" + who
    elif count:
        head = f"{count} arquivos removidos do conhecimento" + who
    else:
        head = "Exclus" + chr(0xE3) + "o recente" + who
    when = _hhmm(stamp) if stamp else ""
    if when:
        head += " " + chr(0xE0) + "s " + when
    if files:
        names = ", ".join(Path(f).name for f in files[:3])
        if len(files) > 3:
            names += f" e mais {len(files) - 3}"
        head += ": " + names
    return head + ". D" + chr(0xE1) + " para desfazer at" + chr(0xE9) + " fechar o CodeBridge."


def _pending(project_id):
    from rag.runtime.knowledge_deletion_operational import pending_removal
    return pending_removal(project_id)


def _index_metadata(project_id: str) -> dict:
    """{path: (chunks, size)} read-only from the private project index."""
    try:
        from rag.runtime.isolated_project_index import resolve_isolated_project
        index = resolve_isolated_project(project_id)
        if index is None:
            return {}
        con = sqlite3.connect(Path(index.sqlite).as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            chunks = dict(con.execute(
                "SELECT path, COUNT(*) FROM rag_chunks WHERE project_id=? GROUP BY path", (project_id,)))
            sizes = dict(con.execute(
                "SELECT path, LENGTH(content) FROM rag_documents WHERE project_id=?", (project_id,)))
        finally:
            con.close()
        return {path: (chunks.get(path, 0), sizes.get(path) or 0) for path in sizes}
    except Exception:
        return {}


def _human(size) -> str:
    if not isinstance(size, int) or size <= 0:
        return ""
    return f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"


class KnowledgeFileTree(QWidget):
    """One checkable tree of the project's indexed files, with a filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._leaves: dict[str, QTreeWidgetItem] = {}
        self._on_change = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.filter = QLineEdit(self)
        self.filter.setPlaceholderText("Filtrar arquivos...")
        self.filter.textChanged.connect(self.apply_filter)
        self.totals = QLabel("", self)
        self.totals.setStyleSheet("color:#7f93a3;")
        bar.addWidget(self.filter, 1)
        bar.addWidget(self.totals)
        lay.addLayout(bar)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Caminho", "Tipo", "Chunks", "Tamanho"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setStyleSheet(
            "QTreeWidget{background:#0d141a;alternate-background-color:#111b23;"
            "border:1px solid #33414d;border-radius:6px;}"
            "QTreeWidget::item{padding:3px;}QTreeWidget::item:selected{background:#1d4e74;}")
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        lay.addWidget(self.tree, 1)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._changed)
        self.tree.itemChanged.connect(lambda *_: self._debounce.start(30))

    def on_change(self, callback):
        self._on_change = callback

    def _changed(self):
        if callable(self._on_change):
            self._on_change()

    def set_files(self, filenames: list[str], metadata: dict | None = None,
                  types: dict | None = None):
        if (not isinstance(filenames, list)
                or any(not isinstance(f, str) or not f or "\\" in f for f in filenames)
                or len(set(filenames)) != len(filenames)):
            raise ValueError("inventario de arquivos invalido")
        metadata = metadata or {}
        types = types or {}
        self.tree.blockSignals(True)
        self.tree.clear()
        self._leaves = {}
        folders: dict[str, QTreeWidgetItem] = {}
        total_chunks = 0
        for path in sorted(filenames):
            chunks, size = metadata.get(path, (None, None))
            total_chunks += chunks or 0
            parent = None
            parts = path.split("/")
            for depth in range(1, len(parts)):
                key = "/".join(parts[:depth])
                if key not in folders:
                    folder = QTreeWidgetItem([parts[depth - 1] + "/", "", "", ""])
                    folder.setFlags(folder.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                    folder.setCheckState(0, Qt.Unchecked)
                    folder.setData(2, Qt.UserRole, 0)
                    (parent.addChild(folder) if parent else self.tree.addTopLevelItem(folder))
                    folders[key] = folder
                parent = folders[key]
                if chunks:
                    parent.setData(2, Qt.UserRole, (parent.data(2, Qt.UserRole) or 0) + chunks)
                    parent.setText(2, str(parent.data(2, Qt.UserRole)))
            leaf = QTreeWidgetItem([parts[-1], str(types.get(path, "")),
                                    "" if chunks is None else str(chunks), _human(size)])
            leaf.setData(0, Qt.UserRole, path)
            leaf.setData(2, Qt.UserRole, chunks or 0)
            leaf.setFlags(leaf.flags() | Qt.ItemIsUserCheckable)
            leaf.setCheckState(0, Qt.Unchecked)
            (parent.addChild(leaf) if parent else self.tree.addTopLevelItem(leaf))
            self._leaves[path] = leaf
        self.tree.blockSignals(False)
        label = f"{len(filenames)} arquivos"
        if total_chunks:
            label += DOT + f"{total_chunks:,} chunks".replace(",", ".")
        self.totals.setText(label)
        self.apply_filter(self.filter.text())
        self._changed()

    def set_checked(self, path: str, checked: bool = True):
        self._leaves[path].setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
        self._changed()

    def clear_checks(self):
        self.tree.blockSignals(True)
        for leaf in self._leaves.values():
            leaf.setCheckState(0, Qt.Unchecked)
        for i in range(self.tree.topLevelItemCount()):
            self._sync_folder(self.tree.topLevelItem(i))
        self.tree.blockSignals(False)
        self._changed()

    def _sync_folder(self, item):
        if item.data(0, Qt.UserRole):
            return
        for i in range(item.childCount()):
            self._sync_folder(item.child(i))
        if item.childCount():
            item.setCheckState(0, Qt.Unchecked)

    def leaf_count(self) -> int:
        return len(self._leaves)

    def selected_paths(self) -> list[str]:
        return sorted(p for p, leaf in self._leaves.items() if leaf.checkState(0) == Qt.Checked)

    def selected_chunks(self) -> int:
        return sum(int(self._leaves[p].data(2, Qt.UserRole) or 0) for p in self.selected_paths())

    def apply_filter(self, text: str):
        text = (text or "").strip().lower()

        def walk(item):
            path = item.data(0, Qt.UserRole)
            if path:
                visible = not text or text in path.lower()
            else:
                visible = any([walk(item.child(i)) for i in range(item.childCount())])
                if text:
                    item.setExpanded(visible)
            item.setHidden(not visible)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))


class RemovalConfirmDialog(QDialog):
    def __init__(self, project_id: str, review: dict, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        files = list(review["selected_paths"])
        self.setWindowTitle("Excluir do conhecimento")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>Remover {len(files)} arquivo(s) do conhecimento de {project_id}?</b>"))
        box = QLabel(
            f"Saem do índice: <b>{review['documents_to_remove']}</b> arquivos" + DOT
            + f"<b>{review['chunks_to_remove']}</b> chunks<br>"
            f"Permanecem: <b>{review['documents_to_preserve']}</b> arquivos<br>"
            "<span style='color:#7fa7c9'>Os arquivos de origem não são apagados. "
            "Dá para desfazer em seguida.</span>")
        box.setStyleSheet(PANEL + "padding:10px;")
        lay.addWidget(box)
        listing = QLabel("<br>".join("- " + f for f in files[:8])
                         + (f"<br>... e mais {len(files) - 8}" if len(files) > 8 else ""))
        listing.setStyleSheet("color:#c9d4dc;font-family:Consolas;font-size:11px;padding:4px 2px;")
        lay.addWidget(listing)
        lay.addWidget(QLabel(f"Digite <b>{project_id}</b> para confirmar:"))
        self.name = QLineEdit(self)
        self.name.setPlaceholderText(project_id)
        lay.addWidget(self.name)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancelar", self)
        self.ok = QPushButton("Excluir do conhecimento", self)
        self.ok.setEnabled(False)
        self.ok.setStyleSheet(
            f"QPushButton{{background:{RED};color:white;font-weight:700;padding:6px 14px;}}"
            "QPushButton:disabled{background:#4a2b2b;color:#9a7a7a;}")
        cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self.accept)
        self.name.textChanged.connect(lambda t: self.ok.setEnabled(t.strip() == project_id))
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)

    def confirmation(self) -> str:
        return self.name.text().strip()


class KnowledgeRemovalReviewPanel(QWidget):
    """Files of the project: select, review, remove after confirmation, undo."""

    BLOCKED_REASON = "Nenhum arquivo selecionado. Confira a exclusão antes de executar."
    PUBLIC_REASON = "Exclusão do índice público não é permitida."

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_id = ""
        self._files: list[str] = []
        self._types: dict[str, str] = {}
        self._busy = False
        self._events: queue.Queue = queue.Queue()
        self._undo_transaction = None
        self._removed_last: list[str] = []
        self.last_review = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.banner = QFrame(self)
        self.banner.setStyleSheet("QFrame{background:#12324a;border:1px solid #2b6cb0;border-radius:6px;}")
        banner_row = QHBoxLayout(self.banner)
        banner_row.setContentsMargins(12, 6, 12, 6)
        self.banner_text = QLabel("", self.banner)
        self.banner_text.setStyleSheet("border:0;color:#e6f0f7;")
        self.progress = QProgressBar(self.banner)
        self.progress.setFixedWidth(220)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.undo_button = QPushButton("Desfazer", self.banner)
        self.undo_button.setObjectName("ragDeletionUndo")
        self.undo_button.setCursor(Qt.PointingHandCursor)
        self.undo_button.setStyleSheet(
            "QPushButton{background:transparent;color:#7fc4ff;border:0;font-weight:700;"
            "text-decoration:underline;}QPushButton:disabled{color:#5b6670;}")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.request_undo)
        self.keep_button = QPushButton("Manter exclus" + chr(0xE3) + "o", self.banner)
        self.keep_button.setObjectName("ragDeletionKeep")
        self.keep_button.setCursor(Qt.PointingHandCursor)
        self.keep_button.setToolTip("Torna a exclus" + chr(0xE3) + "o definitiva e tira este aviso.")
        self.keep_button.setStyleSheet(self.undo_button.styleSheet())
        self.keep_button.setEnabled(False)
        self.keep_button.hide()
        self.keep_button.clicked.connect(self.request_keep)
        banner_row.addWidget(self.banner_text, 1)
        banner_row.addWidget(self.progress)
        banner_row.addWidget(self.undo_button)
        banner_row.addSpacing(10)
        banner_row.addWidget(self.keep_button)
        self.banner.hide()
        root.addWidget(self.banner)

        self.selector = KnowledgeFileTree(self)
        self.selector.on_change(self._selection_changed)
        self.selector.tree.currentItemChanged.connect(self._show_detail)
        root.addWidget(self.selector, 1)

        self.details = QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(64)
        self.details.setPlaceholderText("Selecione um arquivo para ver os detalhes.")
        self.details.setStyleSheet("QPlainTextEdit{" + PANEL + "color:#9fb0bd;padding:4px 8px;}")
        root.addWidget(self.details)

        footer = QFrame(self)
        footer.setStyleSheet("QFrame{" + PANEL + "}")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(12, 8, 12, 8)
        self.delete_status = QLabel(self.BLOCKED_REASON, footer)
        self.delete_status.setWordWrap(True)
        self.delete_status.setStyleSheet("border:0;color:#e6f0f7;font-weight:600;")
        self.clear_button = QPushButton("Limpar seleção", footer)
        self.clear_button.clicked.connect(self.selector.clear_checks)
        self.delete_button = QPushButton("Excluir do conhecimento\u2026", footer)
        self.delete_button.setObjectName("ragDeletionAction")
        self.delete_button.setToolTip(
            "Remove do índice os arquivos marcados. Os arquivos de origem não são apagados.")
        self.delete_button.setStyleSheet(
            f"QPushButton{{background:{RED};color:white;font-weight:700;padding:6px 16px;}}"
            "QPushButton:disabled{background:#3a2626;color:#8a6d6d;}")
        self.delete_button.clicked.connect(self.request_removal)
        footer_row.addWidget(self.delete_status, 1)
        footer_row.addWidget(self.clear_button)
        footer_row.addWidget(self.delete_button)
        root.addWidget(footer)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_events)
        self._timer.start(150)
        self._refresh_buttons()

    # ---------------------------------------------------------------- state
    def _refresh_buttons(self):
        public = self.project_id == "codebridge"
        selected = self.selector.selected_paths()
        self.delete_button.setEnabled(
            not self._busy and not public and (bool(selected) or self.last_review is not None))
        self.clear_button.setEnabled(not self._busy and bool(selected))
        self.undo_button.setEnabled(not self._busy and self._undo_transaction is not None)
        self.keep_button.setEnabled(not self._busy and self._undo_transaction is not None)
        self.keep_button.setVisible(self._undo_transaction is not None)
        self.selector.setEnabled(not self._busy)

    def _selection_changed(self):
        self.last_review = None
        if not self._busy:
            if self.project_id == "codebridge":
                self.delete_status.setText(self.PUBLIC_REASON)
            else:
                selected = self.selector.selected_paths()
                chunks = self.selector.selected_chunks()
                self.delete_status.setText(
                    (f"{len(selected)} selecionado(s)" + (DOT + f"{chunks} chunks" if chunks else ""))
                    if selected else self.BLOCKED_REASON)
        self._refresh_buttons()

    def set_project_files(self, project_id: str, filenames: list[str], documents=None):
        self.project_id = project_id
        self._files = list(filenames)
        self.last_review = None
        self.details.clear()
        types = {}
        for item in documents or []:
            if isinstance(item, dict) and item.get("path"):
                types[str(item["path"])] = item.get("type", "")
        self._types = types
        metadata = {} if project_id == "codebridge" or not filenames else _index_metadata(project_id)
        self.selector.set_files(list(filenames), metadata, types)
        self._undo_transaction = None
        self.banner.hide()
        if project_id == "codebridge":
            self.details.setPlainText(self.PUBLIC_REASON)
        elif project_id:
            try:
                pending = _pending(project_id)
            except Exception:
                pending = None
            if pending and pending.get("kind") != "ADD":
                self._undo_transaction = pending["transaction"]
                self._show_banner(pending_banner_text(pending, _sync_last(project_id)), progress=False)
        self._selection_changed()

    def _show_detail(self, item, _previous=None):
        if item is None:
            return
        path = item.data(0, Qt.UserRole)
        if path:
            parts = [path]
            for column in (1, 2, 3):
                if item.text(column):
                    parts.append(item.text(column) + (" chunks" if column == 2 else ""))
            parts.append("no índice")
            self.details.setPlainText(DOT.join(parts))
        else:
            self.details.setPlainText(DOT.join(
                [item.text(0), f"{item.childCount()} itens"]
                + ([item.text(2) + " chunks"] if item.text(2) else [])))

    def _show_banner(self, text: str, *, progress: bool):
        self.banner_text.setText(text)
        self.progress.setVisible(progress)
        self.banner.show()

    # --------------------------------------------------------------- review
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

    def review_selected(self, selected: list[str]):
        """Build and validate the read-only review; returns it when genuine."""
        self.last_review = None
        if not selected or self.project_id == "codebridge":
            self._refresh_buttons()
            return None
        try:
            review = build_deletion_review(self.project_id, list(selected))
        except (ValueError, OSError, RuntimeError) as error:
            self.details.setPlainText("Prévia bloqueada: " + str(error))
            self._refresh_buttons()
            return None
        if not self._review_is_genuine(review, selected):
            shown = review.get("display_text", "") if isinstance(review, dict) else ""
            self.details.setPlainText(
                (str(shown) + "\n\n" if shown else "")
                + "Prévia bloqueada para execução: revisão inválida ou adulterada.")
            self._refresh_buttons()
            return None
        self.last_review = review
        self.details.setPlainText(review["display_text"].replace(
            "SIMULAÇÃO: nenhum conhecimento foi removido.", "Prévia conferida."))
        self._refresh_buttons()
        return review

    # --------------------------------------------------------------- remove
    def request_removal(self):
        if self._busy:
            return
        selected = self.selector.selected_paths() or (
            list(self.last_review["selected_paths"]) if self.last_review else [])
        review = self.review_selected(selected)
        if review is None:
            return
        dialog = RemovalConfirmDialog(self.project_id, review, self)
        if dialog.exec() != QDialog.Accepted or dialog.confirmation() != self.project_id:
            return
        self._start("remove", _execute, self.project_id, list(review["selected_paths"]),
                    review["review_sha256"], dialog.confirmation(), progress=self._progress)

    def request_keep(self):
        if self._undo_transaction is None or self._busy:
            return
        self._start("keep", _keep, self._undo_transaction)

    def _after_undo_sync(self, transaction):
        """Se era a ultima atualizacao automatica, passa para Manual."""
        try:
            sync = _sync_module()
            cfg = sync.settings(self.project_id) or {}
            last = cfg.get("last") or {}
            if not transaction or last.get("transaction") != transaction:
                return ""
            changes = {"last": None}
            text = ""
            if cfg.get("mode") == "AUTO":
                changes["mode"] = "MANUAL"
                text = (" A atualiza" + chr(0xE7) + chr(0xE3) + "o foi para Manual para n" + chr(0xE3)
                        + "o excluir de novo sozinha.")
            sync.update_settings(self.project_id, **changes)
            return text
        except Exception:
            return ""

    def request_undo(self):
        if self._undo_transaction is None or self._busy:
            return
        self._start("undo", _rollback, self._undo_transaction)

    # -------------------------------------------------------------- worker
    def _progress(self, message: str):
        self._events.put(("progress", message))

    def _start(self, kind, function, *args, **kwargs):
        self._busy = True
        self._refresh_buttons()
        labels = {"remove": "Excluindo", "undo": "Desfazendo", "keep": "Confirmando"}
        self._show_banner(labels.get(kind, "Trabalhando") + chr(0x2026), progress=True)

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
                self._show_banner("Excluindo\u2026 " + str(event[1]), progress=True)
                continue
            kind, ok, payload = event
            self._busy = False
            if kind == "remove" and ok:
                removed = list(payload["removed_files"])
                self._removed_last = removed
                self._undo_transaction = payload["transaction"]
                self._files = [f for f in self._files if f not in removed]
                self.set_files_after_change()
                self._show_banner(
                    f"{payload['documents_removed']} arquivo(s) removido(s) do conhecimento"
                    + DOT + f"{payload['chunks_removed']} chunks" + DOT
                    + "arquivos de origem intactos", progress=False)
                self.details.setPlainText(
                    f"Geração anterior: {payload['previous_generation']}" + DOT
                    + f"nova: {payload['generation']}")
            elif kind == "undo" and ok:
                undone = self._undo_transaction
                self._files = sorted(set(self._files) | set(self._removed_last))
                self._removed_last = []
                self._undo_transaction = None
                self.set_files_after_change()
                self._show_banner("Exclus" + chr(0xE3) + "o desfeita: a gera" + chr(0xE7) + chr(0xE3)
                                  + "o anterior foi restaurada." + self._after_undo_sync(undone),
                                  progress=False)
            elif kind == "keep" and ok:
                self._undo_transaction = None
                self._removed_last = []
                self._show_banner("Exclus" + chr(0xE3) + "o mantida: agora " + chr(0xE9) + " definitiva.",
                                  progress=False)
            else:
                label = "Exclusão falhou" if kind == "remove" else "Desfazer falhou"
                self._show_banner(label + ". Nada foi alterado sem verificação.", progress=False)
                self.details.setPlainText(label + ": " + str(payload))
            self._refresh_buttons()

    def set_files_after_change(self):
        metadata = _index_metadata(self.project_id)
        self.selector.set_files(list(self._files), metadata, self._types)