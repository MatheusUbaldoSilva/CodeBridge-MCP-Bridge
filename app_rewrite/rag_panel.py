"""Central RAG: non-blocking read-only management and index planning UI."""
import sys
import threading
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QFileDialog, QComboBox,
    QMessageBox, QHeaderView,
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
        return bridge.search_rag_context(query=args["query"], project_id=args["project"], top_k=10)
    if operation == "plan":
        return bridge.index_rag(project_id=args["project"], project_root=args["root"],
                                scope=args["scope"], execute=False)
    raise ValueError("Unknown operation")

class RagPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = BridgeWorker(self)
        self._worker.completed.connect(self._complete)
        self._busy = False
        self._results = []
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.summary = QLabel("Central RAG — atualizar para consultar o indice")
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.clicked.connect(lambda: self._run("status", {}))
        header.addWidget(self.summary, 1)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        self.projects = QTableWidget(0, 4)
        self.projects.setHorizontalHeaderLabels(["Projeto", "Documentos", "Chunks", "Estado"])
        self.projects.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.projects.setMaximumHeight(160)
        layout.addWidget(self.projects)
        row = QHBoxLayout()
        self.project = QLineEdit("codebridge")
        self.project.setPlaceholderText("ID do projeto")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Pesquisar o conhecimento indexado...")
        self.search_btn = QPushButton("Pesquisar")
        self.search_btn.clicked.connect(self.search)
        row.addWidget(self.project, 1)
        row.addWidget(self.query, 3)
        row.addWidget(self.search_btn)
        layout.addLayout(row)
        self.results = QTableWidget(0, 3)
        self.results.setHorizontalHeaderLabels(["Origem", "Score", "Trecho"])
        self.results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results.itemSelectionChanged.connect(self.show_selected)
        layout.addWidget(self.results, 2)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Selecione um resultado para ver o conteudo.")
        layout.addWidget(self.preview, 1)
        folder_row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Pasta para adicionar conhecimentos")
        self.browse_btn = QPushButton("Escolher pasta")
        self.browse_btn.clicked.connect(self.browse)
        self.scope = QComboBox()
        self.scope.addItems(["BOTH", "TEXT", "CODE"])
        self.plan_btn = QPushButton("Previa de indexacao")
        self.plan_btn.clicked.connect(self.plan)
        folder_row.addWidget(self.folder, 3)
        folder_row.addWidget(self.browse_btn)
        folder_row.addWidget(self.scope)
        folder_row.addWidget(self.plan_btn)
        layout.addLayout(folder_row)
        self.plan_summary = QLabel("Nenhuma pasta analisada.")
        layout.addWidget(self.plan_summary)
        self.candidates = QTableWidget(0, 3)
        self.candidates.setHorizontalHeaderLabels(["Arquivo elegivel", "Texto", "Codigo"])
        self.candidates.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.candidates.setMaximumHeight(180)
        layout.addWidget(self.candidates)
        self.notice = QLabel("Indexacao real desabilitada ate validacao do executor. A previa nao altera o indice.")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self._run("status", {})

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta para indexacao")
        if folder:
            self.folder.setText(folder)

    def search(self):
        if not self.query.text().strip() or not self.project.text().strip():
            return
        self._run("search", {"query":self.query.text().strip(), "project":self.project.text().strip()})

    def plan(self):
        if not self.project.text().strip() or not Path(self.folder.text().strip()).is_dir():
            QMessageBox.warning(self, "Central RAG", "Informe um projeto e uma pasta existente.")
            return
        self._run("plan", {"project":self.project.text().strip(), "root":self.folder.text().strip(),
                            "scope":self.scope.currentText()})

    def _run(self, operation, args):
        if self._busy:
            return
        self._busy = True
        self.notice.setText("Processando " + operation + "...")
        for button in (self.refresh_btn, self.search_btn, self.plan_btn):
            button.setEnabled(False)
        def work():
            try:
                result = _rag_operation(operation, args)
                self._worker.completed.emit(operation, result, "")
            except Exception as exc:
                self._worker.completed.emit(operation, {}, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _complete(self, operation, data, error):
        self._busy = False
        for button in (self.refresh_btn, self.search_btn, self.plan_btn):
            button.setEnabled(True)
        if error:
            self.notice.setText("Falha: " + error)
            return
        if operation == "status":
            idx = data.get("index", {})
            entries = data.get("projects", [])
            self.summary.setText("Central RAG — Indice: " + str(idx.get("state", "?")))
            self.projects.setRowCount(len(entries))
            for i, entry in enumerate(entries):
                for j, value in enumerate((entry.get("project_id", ""),entry.get("document_count", 0),
                                           entry.get("chunk_count", 0),entry.get("index_state", ""))):
                    self.projects.setItem(i,j,QTableWidgetItem(str(value)))
            self.notice.setText(f"{len(entries)} projeto(s) cadastrado(s). Indexacao real ainda nao habilitada.")
        elif operation == "search":
            self._results = list(data.get("results") or [])
            self.results.setRowCount(len(self._results))
            for i, entry in enumerate(self._results):
                origin = entry.get("path") or entry.get("source_path") or entry.get("source_id") or "(sem origem)"
                score = entry.get("score")
                excerpt = str(entry.get("text") or entry.get("content") or entry.get("snippet") or "")
                for j, value in enumerate((origin, score if score is not None else "-", excerpt[:170])):
                    self.results.setItem(i,j,QTableWidgetItem(str(value)))
            self.notice.setText(f"{len(self._results)} resultado(s). Rota: {data.get('effective_route', '?')}; fallback: {data.get('fallback_reason') or 'nenhum'}")
        elif operation == "plan":
            plan = data.get("plan") or {}
            candidates = plan.get("candidates") or []
            self.plan_summary.setText(
                f"Elegiveis: {plan.get('candidate_count', 0)} | "
                f"Texto: {plan.get('text_candidate_count', 0)} | "
                f"Codigo: {plan.get('code_candidate_count', 0)} | "
                f"Ignorados: {plan.get('denied_count', 0)} | "
                f"Nao suportados: {plan.get('unsupported_count', 0)} | "
                f"Sensiveis: {plan.get('sensitive_count', 0)}"
            )
            self.candidates.setRowCount(len(candidates))
            for i, candidate in enumerate(candidates):
                values = (candidate.get("path", ""),
                          "Sim" if candidate.get("text_eligible") else "-",
                          "Sim" if candidate.get("code_eligible") else "-")
                for j, value in enumerate(values):
                    self.candidates.setItem(i, j, QTableWidgetItem(str(value)))
            self.preview.setPlainText(__import__("json").dumps(plan, ensure_ascii=False, indent=2))
            self.notice.setText("Previa somente leitura. Nenhuma indexacao foi executada.")

    def show_selected(self):
        row = self.results.currentRow()
        if 0 <= row < len(self._results):
            import json
            self.preview.setPlainText(json.dumps(self._results[row], indent=2, ensure_ascii=False, default=str))
