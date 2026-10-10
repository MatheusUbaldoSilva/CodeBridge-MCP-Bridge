"""Simple, read-only RAG knowledge center with safe indexing preview."""
import sqlite3
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from rag_projects import list_projects, create_project, validate_preview_folder
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QListWidget, QListWidgetItem, QStackedWidget,
    QFileDialog, QMessageBox, QComboBox, QInputDialog,
)


class BridgeWorker(QObject):
    completed = Signal(str, object, str)


def _rag_operation(operation, args):
    import importlib
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    bridge = importlib.import_module("author_mcp.rag_bridge")
    if operation == "status":
        return bridge.get_rag_status()
    if operation == "search":
        return bridge.search_rag_context(
            query=args["query"], project_id=args["project"], top_k=10)
    if operation == "plan":
        validate_preview_folder(args["root"])
        return bridge.index_rag(
            project_id=args["project"], project_root=args["root"],
            scope="BOTH", execute=False)
    if operation == "documents":
        from rag.runtime.status import resolve_rag_sqlite_path
        db = resolve_rag_sqlite_path()
        if not db.is_file():
            return []
        with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as con:
            rows = con.execute(
                "SELECT path, COUNT(*), MAX(source_type) FROM rag_documents "
                "WHERE project_id=? GROUP BY path ORDER BY path LIMIT 2000",
                (args["project"],),
            ).fetchall()
        return [{"path": path, "count": count, "type": kind} for path, count, kind in rows]
    raise ValueError("Operacao desconhecida")


def _source(hit):
    meta = hit.get("metadata") or {}
    return (hit.get("path") or hit.get("source_path") or
            meta.get("path") or meta.get("source_path") or
            hit.get("document_path") or "Documento sem nome")


def _content(hit):
    return str(hit.get("content") or hit.get("text") or hit.get("snippet") or "")


class RagPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = BridgeWorker(self)
        self._worker.completed.connect(self._complete)
        self._busy = False
        self._results = []
        self._documents = []
        self.project_id = "codebridge"
        outer = QVBoxLayout(self)
        heading = QHBoxLayout()
        self.summary = QLabel("Meus conhecimentos")
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.clicked.connect(self.refresh)
        heading.addWidget(self.summary, 1)
        heading.addWidget(self.refresh_btn)
        outer.addLayout(heading)
        project_row = QHBoxLayout()
        project_row.addWidget(QLabel("Projeto:"))
        self.project_picker = QComboBox()
        self.project_picker.addItem("codebridge")
        self.project_picker.currentTextChanged.connect(self.change_project)
        self.new_project_btn = QPushButton("Novo projeto")
        self.new_project_btn.clicked.connect(self.new_project)
        project_row.addWidget(self.project_picker, 1)
        project_row.addWidget(self.new_project_btn)
        outer.addLayout(project_row)

        navigation = QHBoxLayout()
        self.nav_buttons = []
        self.pages = QStackedWidget()
        for index, title in enumerate(("Meus arquivos", "Pesquisar", "Adicionar")):
            button = QPushButton(title)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.set_page(i))
            self.nav_buttons.append(button)
            navigation.addWidget(button)
        outer.addLayout(navigation)
        outer.addWidget(self.pages, 1)

        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        files_layout.addWidget(QLabel("Arquivos que o CodeBridge conhece"))
        self.files = QListWidget()
        self.files.currentRowChanged.connect(self._show_file)
        files_layout.addWidget(self.files, 2)
        self.file_details = QPlainTextEdit()
        self.file_details.setReadOnly(True)
        self.file_details.setPlaceholderText("Selecione um arquivo.")
        files_layout.addWidget(self.file_details, 1)
        self.pages.addWidget(files_page)

        search_page = QWidget()
        search_layout = QVBoxLayout(search_page)
        search_row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("O que voce quer encontrar?")
        self.search_btn = QPushButton("Pesquisar")
        self.search_btn.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        search_row.addWidget(self.query, 1)
        search_row.addWidget(self.search_btn)
        search_layout.addLayout(search_row)
        self.results = QListWidget()
        self.results.currentRowChanged.connect(self._show_result)
        search_layout.addWidget(self.results, 2)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Selecione um resultado para ler o trecho encontrado.")
        search_layout.addWidget(self.preview, 1)
        self.pages.addWidget(search_page)

        add_page = QWidget()
        add_layout = QVBoxLayout(add_page)
        add_layout.addWidget(QLabel("Escolha uma pasta com documentos ou codigo."))
        folder_row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Nenhuma pasta selecionada")
        self.folder.setReadOnly(True)
        self.browse_btn = QPushButton("Escolher pasta")
        self.browse_btn.clicked.connect(self.browse)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.browse_btn)
        add_layout.addLayout(folder_row)
        self.plan_btn = QPushButton("Ver arquivos que podem ser adicionados")
        self.plan_btn.clicked.connect(self.plan)
        add_layout.addWidget(self.plan_btn)
        self.plan_summary = QLabel("Selecione uma pasta para conferir os arquivos.")
        self.plan_summary.setWordWrap(True)
        add_layout.addWidget(self.plan_summary)
        self.candidates = QListWidget()
        add_layout.addWidget(self.candidates, 1)
        self.index_btn = QPushButton("Adicionar ao conhecimento (em preparacao)")
        self.index_btn.setEnabled(False)
        self.index_btn.setToolTip("A atualizacao incremental ainda nao foi validada.")
        add_layout.addWidget(self.index_btn)
        add_layout.addWidget(QLabel(
            "A inclusao real ainda nao esta disponivel. A previa nao altera seus conhecimentos."))
        self.pages.addWidget(add_page)

        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        self.set_page(0)
        self.refresh()

    def set_page(self, index):
        self.pages.setCurrentIndex(index)
        for number, button in enumerate(self.nav_buttons):
            button.setChecked(number == index)

    def change_project(self, name):
        if not name or name == self.project_id:
            return
        self.project_id = name
        self.files.clear()
        self._documents = []
        self.results.clear()
        self._results = []
        self.preview.clear()
        self._run("documents", {"project": name})

    def new_project(self):
        name, accepted = QInputDialog.getText(self, "Novo projeto", "Nome do projeto (letras, numeros e hifens):")
        if not accepted or not name.strip():
            return
        try:
            name = create_project(name)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Novo projeto", str(exc))
            return
        if self.project_picker.findText(name) < 0:
            self.project_picker.addItem(name)
        self.project_picker.setCurrentText(name)
        self.notice.setText("Projeto criado. Ele recebera documentos quando a indexacao for habilitada.")

    def refresh(self):
        self._run("status", {})

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, "Escolher pasta")
        if path:
            self.folder.setText(path)
            self.candidates.clear()
            self.plan_summary.setText("Clique para conferir os arquivos selecionados.")

    def search(self):
        query = self.query.text().strip()
        if query:
            self._run("search", {"project": self.project_id, "query": query})

    def plan(self):
        path = self.folder.text().strip()
        if not path or not Path(path).is_dir():
            QMessageBox.information(self, "Adicionar conhecimentos", "Escolha uma pasta primeiro.")
            return
        self._run("plan", {"project": self.project_id, "root": path})

    def _run(self, operation, args):
        if self._busy:
            return
        self._busy = True
        self.notice.setText("Carregando...")
        for button in (self.refresh_btn, self.search_btn, self.plan_btn):
            button.setEnabled(False)
        def work():
            try:
                value = _rag_operation(operation, args)
                self._worker.completed.emit(operation, value, "")
            except Exception as exc:
                self._worker.completed.emit(operation, {}, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _complete(self, operation, data, error):
        self._busy = False
        for button in (self.refresh_btn, self.search_btn, self.plan_btn):
            button.setEnabled(True)
        if error:
            self.notice.setText("Nao foi possivel carregar: " + error)
            return
        self.notice.setText("")
        if operation == "status":
            projects = data.get("projects") or []
            count = sum(int(p.get("document_count") or 0) for p in projects)
            self.summary.setText(f"Meus conhecimentos — {count} documentos")
            names = sorted(set(["codebridge"] +
                               [str(p.get("project_id")) for p in projects if p.get("project_id")] +
                               list_projects()))
            self.project_picker.blockSignals(True)
            self.project_picker.clear()
            self.project_picker.addItems(names)
            if self.project_id not in names:
                self.project_id = names[0]
            self.project_picker.setCurrentText(self.project_id)
            self.project_picker.blockSignals(False)
            self._run("documents", {"project": self.project_id})
        elif operation == "documents":
            self._documents = list(data)
            self.files.clear()
            for item in self._documents:
                self.files.addItem(str(item["path"]))
            if not self._documents:
                self.file_details.setPlainText("Nenhum arquivo encontrado.")
        elif operation == "search":
            self._results = list(data.get("results") or [])
            self.results.clear()
            for i, hit in enumerate(self._results, 1):
                snippet = _content(hit).replace("\r", " ").replace("\n", " ").strip()
                self.results.addItem(f"{i}. {_source(hit)}\n{snippet[:180]}")
            if not self._results:
                self.preview.setPlainText("Nenhum resultado encontrado.")
            else:
                self.results.setCurrentRow(0)
            if data.get("fallback_reason"):
                self.notice.setText("Pesquisa textual ativa. Pesquisa inteligente ainda em preparacao.")
        elif operation == "plan":
            plan = data.get("plan") or {}
            self.candidates.clear()
            for item in plan.get("candidates") or []:
                self.candidates.addItem(str(item.get("path") or ""))
            self.plan_summary.setText(
                f"{plan.get('candidate_count', 0)} arquivos disponiveis para futura inclusao. "
                f"{plan.get('denied_count', 0)} protegidos, "
                f"{plan.get('sensitive_count', 0)} sensiveis, "
                f"{plan.get('unsupported_count', 0)} nao suportados."
            )

    def _show_file(self, row):
        if 0 <= row < len(self._documents):
            item = self._documents[row]
            self.file_details.setPlainText(
                f"Arquivo: {item['path']}\nTipo: {item['type']}\n"
                "O conteudo permanece no indice e pode ser localizado pela pesquisa.")

    def _show_result(self, row):
        if 0 <= row < len(self._results):
            hit = self._results[row]
            self.preview.setPlainText(f"Arquivo: {_source(hit)}\n\n{_content(hit)}")
