"""Simple, read-only RAG knowledge center with safe indexing preview."""
import sqlite3
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from rag_projects import list_projects, create_project, validate_preview_folder
from rag_auto_job_card import RagAutoJobCard
from rag_deletion_review_panel import KnowledgeRemovalReviewPanel
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
        from rag.runtime.incremental_discovery_guard import inventory_folder, assert_discovery_unchanged
        initial_inventory = inventory_folder(args["root"])
        response = bridge.index_rag(
            project_id=args["project"], project_root=args["root"],
            scope="BOTH", paths=args.get("paths"), execute=False)
        assert_discovery_unchanged(initial_inventory, args["root"])
        from rag.runtime.incremental_preflight import assess_incremental_plan
        from rag.runtime.incremental_preview_confirmation import snapshot_preview, revalidate_preview
        from rag.runtime.incremental_preview_view import describe_incremental_preview
        plan = response["plan"]
        candidates = plan.get("candidates") or []
        start = snapshot_preview(args["project"], args["root"], candidates) if candidates else None
        response["incremental"] = assess_incremental_plan(plan)
        describe_incremental_preview(plan, response["incremental"])
        if start is not None:
            revalidate_preview(start, args["project"], args["root"])
        response["preview_start"] = start
        return response
    if operation == "auto_preview":
        from rag.runtime.auto_index_api import auto_preview
        validate_preview_folder(args["root"])
        return auto_preview(
            args["project"],args["root"],
            paths=args.get("paths"),scope="BOTH",
        )
    if operation == "auto_approve":
        from rag.runtime.auto_index_api import auto_approve
        return auto_approve(
            args["project"],args["root"],
            paths=args.get("paths"),scope="BOTH",
            confirmed_digest=args["review_sha256"],
            operator_approved=True,
            execute=True,
            confirmation=("RAG_AUTO_QUEUE:"+args["project"]+":"+args["review_sha256"]),
        )
    if operation in ("auto_prepare_generation","auto_enable_canary","auto_rollback_canary"):
        from rag.runtime.auto_index_promotion import (
            prepare_auto_candidate,enable_auto_canary,disable_auto_canary,
        )
        job_id=args["job_id"]
        action={
            "auto_prepare_generation":prepare_auto_candidate,
            "auto_enable_canary":enable_auto_canary,
            "auto_rollback_canary":disable_auto_canary,
        }[operation]
        return action(
            job_id,execute=True,operator_approved=True,
            confirmation=args["confirmation"],
        )
    if operation == "documents":
        if args["project"] == "codebridge":
            # Hold a generation pin throughout the public SQLite inventory.
            from rag.runtime.knowledge_deletion_public_inventory_read import (
                read_pinned_public_document_inventory,
            )
            return read_pinned_public_document_inventory(
                project_id="codebridge",
            )["documents"]
        from rag.runtime.status import resolve_rag_sqlite_path
        from rag.runtime.isolated_project_index import resolve_isolated_project
        is_public=args["project"]=="codebridge"
        project=resolve_isolated_project(args["project"]) if not is_public else None
        if not is_public and project is None:
            # Never leak public/legacy inventory into a private project view.
            return []
        db = resolve_rag_sqlite_path() if is_public else project.sqlite
        if not db.is_file():
            return []
        from contextlib import closing
        with closing(sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)) as con:
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
        self._preview_snapshot = None
        self._auto_manifest = None
        self._auto_request = None
        self._selected_paths = None
        self._preview_revision = 0
        self._plan_request = None
        self.project_id = "codebridge"
        outer = QVBoxLayout(self)
        heading = QHBoxLayout()
        self.summary = QLabel("Meus conhecimentos")
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.clicked.connect(self.refresh)
        heading.addWidget(self.summary, 1)
        heading.addWidget(self.refresh_btn)
        outer.addLayout(heading)
        self.rag_status = QLabel("RAG: VERIFICANDO...")
        outer.addWidget(self.rag_status)
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
        for index, title in enumerate(("Meus arquivos", "Pesquisar", "Adicionar", "Indexação automática")):
            button = QPushButton(title)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.set_page(i))
            self.nav_buttons.append(button)
            navigation.addWidget(button)
        navigation.setSpacing(0)
        for position, button in enumerate(self.nav_buttons):
            radius = ("border-top-left-radius:6px;border-bottom-left-radius:6px;" if position == 0
                      else "border-top-right-radius:6px;border-bottom-right-radius:6px;"
                      if position == len(self.nav_buttons) - 1 else "")
            button.setStyleSheet(
                "QPushButton{background:#111b23;color:#c9d4dc;border:1px solid #33414d;"
                "border-radius:0;padding:7px 14px;" + radius + "}"
                "QPushButton:checked{background:#1d4e74;color:white;font-weight:700;"
                "border-color:#2b6cb0;}")
        outer.addLayout(navigation)
        outer.addWidget(self.pages, 1)

        files_page = QWidget()
        files_layout = QVBoxLayout(files_page)
        # Lista unica: arvore com selecao, filtro, detalhe e exclusao.
        # self.files/file_details ficam fora do layout (compatibilidade).
        self.files = QListWidget(files_page)
        self.files.currentRowChanged.connect(self._show_file)
        self.files.hide()
        self.file_details = QPlainTextEdit(files_page)
        self.file_details.setReadOnly(True)
        self.file_details.hide()
        self.deletion_review_panel = KnowledgeRemovalReviewPanel(files_page)
        files_layout.addWidget(self.deletion_review_panel, 1)
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
        self.browse_files_btn = QPushButton("Escolher arquivos individuais")
        self.browse_files_btn.clicked.connect(self.browse_files)
        add_layout.addWidget(self.browse_files_btn)
        self.plan_btn = QPushButton("Ver arquivos que podem ser adicionados")
        self.plan_btn.clicked.connect(self.plan)
        add_layout.addWidget(self.plan_btn)
        self.plan_summary = QLabel("Selecione uma pasta para conferir os arquivos.")
        self.plan_summary.setWordWrap(True)
        add_layout.addWidget(self.plan_summary)
        self.candidates = QListWidget()
        add_layout.addWidget(self.candidates, 1)
        self.confirm_preview_btn = QPushButton("Conferir previa (sem publicar)")
        self.confirm_preview_btn.setEnabled(False)
        self.confirm_preview_btn.clicked.connect(self.confirm_preview)
        add_layout.addWidget(self.confirm_preview_btn)
        self.review_auth_btn = QPushButton("Revisar autorizacao (simulacao)")
        self.review_auth_btn.setEnabled(False)
        self.review_auth_btn.clicked.connect(self.review_authorization)
        add_layout.addWidget(self.review_auth_btn)
        self.cancel_preview_btn = QPushButton("Cancelar previa")
        self.cancel_preview_btn.clicked.connect(self.cancel_preview)
        add_layout.addWidget(self.cancel_preview_btn)
        self.index_btn = QPushButton("Adicionar ao conhecimento (em preparacao)")
        self.index_btn.setEnabled(False)
        self.index_btn.setToolTip("A atualizacao incremental ainda nao foi validada.")
        add_layout.addWidget(self.index_btn)
        add_layout.addWidget(QLabel(
            "A inclusao real ainda nao esta disponivel. A previa nao altera seus conhecimentos."))
        self.auto_prepare_btn = QPushButton("Preparar fila automática (sem indexar)")
        self.auto_prepare_btn.clicked.connect(self.prepare_auto_job)
        add_layout.addWidget(self.auto_prepare_btn)
        self.auto_authorize_btn = QPushButton("Autorizar arquivos e criar trabalho")
        self.auto_authorize_btn.setEnabled(False)
        self.auto_authorize_btn.clicked.connect(self.authorize_auto_job)
        add_layout.addWidget(self.auto_authorize_btn)
        self.auto_info = QLabel("Sem aprovação: nenhum worker ou modelo é iniciado.")
        self.auto_info.setWordWrap(True)
        add_layout.addWidget(self.auto_info)
        self.pages.addWidget(add_page)

        auto_page = QWidget()
        auto_layout = QVBoxLayout(auto_page)
        self.auto_card = RagAutoJobCard(auto_page, project_id=self.project_id)
        self.auto_card.prepare_requested.connect(self._prepare_generation)
        self.auto_card.enable_requested.connect(self._enable_canary)
        self.auto_card.rollback_requested.connect(self._rollback_canary)
        auto_layout.addWidget(self.auto_card)
        auto_layout.addStretch(1)
        self.pages.addWidget(auto_page)

        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        self.set_page(0)
        self.refresh()

    def request_graceful_stop_of_workers(self):
        """Closing the GUI requests PAUSE for every active auto-index worker."""
        from rag.runtime.auto_index_queue import (
            AutoIndexQueueError,default_queue_path,get_job,list_jobs,
        )
        from rag.runtime.auto_index_controls import request_auto_index_control
        queue=default_queue_path()
        requested=[]
        for job in list_jobs(queue,limit=200):
            # Also pause a queued child that has just been launched but has
            # not yet acquired its lease, closing the start/exit race.
            if job["state"] in ("RUNNING","QUEUED"):
                try:
                    request_auto_index_control(
                        queue,job["job_id"],"PAUSE",
                        operator_requested=True,control_enabled=True,
                    )
                except AutoIndexQueueError:
                    # A job may finish between listing and the pause request.
                    fresh=get_job(queue,job["job_id"])
                    if fresh is None or fresh["state"] not in (
                        "PAUSED","PAUSE_REQUESTED","CANCELLED",
                        "READY_FOR_REVIEW","FAILED",
                    ):
                        raise
                requested.append(job["job_id"])
        return requested

    def set_page(self, index):
        self.pages.setCurrentIndex(index)
        for number, button in enumerate(self.nav_buttons):
            button.setChecked(number == index)

    def change_project(self, name):
        if not name or name == self.project_id:
            return
        self.cancel_preview()
        self.project_id = name
        self.auto_card.set_project(name)
        self._selected_paths = None
        self.files.clear()
        self._documents = []
        self.deletion_review_panel.set_project_files(name, [])
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
            self.cancel_preview()
            self._selected_paths = None
            self.folder.setText(path)
            self.candidates.clear()
            self.plan_summary.setText("Clique para conferir os arquivos selecionados.")

    def browse_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, "Escolher arquivos")
        if not names:
            return
        files = [Path(name).resolve() for name in names]
        root = (Path.home() / "CodeBridge-MCP-Bridge" if self.project_id == "codebridge"
                else files[0].parent)
        if any(not f.is_file() or not f.is_relative_to(root) for f in files):
            QMessageBox.warning(self, "Adicionar conhecimentos",
                "Selecione arquivos existentes dentro da pasta do projeto.")
            return
        self.cancel_preview()
        self._selected_paths = [f.relative_to(root).as_posix() for f in files]
        self.folder.setText(str(root))
        self.plan_summary.setText(f"{len(files)} arquivo(s) selecionado(s) para previa.")

    def search(self):
        query = self.query.text().strip()
        if query:
            self._run("search", {"project": self.project_id, "query": query})

    def plan(self):
        path = self.folder.text().strip()
        if not path or not Path(path).is_dir():
            QMessageBox.information(self, "Adicionar conhecimentos", "Escolha uma pasta primeiro.")
            return
        if self._busy:
            return
        self.cancel_preview()
        self._plan_request = (self._preview_revision, self.project_id, str(Path(path).resolve()))
        self._run("plan", {"project": self.project_id, "root": path, "paths": self._selected_paths})

    def cancel_preview(self):
        self._preview_revision += 1
        self._plan_request = None
        self._auto_request = None
        self._auto_manifest = None
        self.auto_authorize_btn.setEnabled(False)
        self._preview_snapshot = None
        self.candidates.clear()
        self.confirm_preview_btn.setEnabled(False)
        self.review_auth_btn.setEnabled(False)
        self.plan_summary.setText("Previa cancelada. Gere uma nova previa para continuar.")

    def confirm_preview(self):
        if self._preview_snapshot is None:
            return
        from rag.runtime.incremental_preview_confirmation import revalidate_preview
        try:
            result = revalidate_preview(self._preview_snapshot, self.project_id,
                                        self.folder.text().strip())
        except (ValueError, OSError) as exc:
            self.cancel_preview()
            QMessageBox.warning(self, "Previa desatualizada", str(exc))
            return
        QMessageBox.information(self, "Conferencia concluida",
            str(result["files_checked"]) + " arquivos conferidos. Nenhum indice foi alterado. "
            "A publicacao ainda esta desabilitada.")

    def review_authorization(self):
        """UI-only rehearsal: no indexing, credentials or persistent approval."""
        if self._busy or self._preview_snapshot is None:
            return
        from rag.runtime.incremental_review_contract import (
            build_review_contract, verify_review_contract)
        try:
            contract = build_review_contract(self._preview_snapshot, self.project_id,
                                             self.folder.text().strip())
        except (ValueError, OSError) as exc:
            self.cancel_preview()
            QMessageBox.warning(self, "Previa desatualizada", str(exc))
            return
        question = ("SIMULACAO - nenhuma publicacao sera executada.\n\n"
                    f"Projeto: {contract['project']}\n"
                    f"Pasta: {contract['folder']}\n"
                    f"Arquivos conferidos: {contract['files_checked']}\n"
                    f"Identificador da revisao: {contract['review_sha256'][:12]}\n\n"
                    "Confirmar somente o ensaio de autorizacao?")
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Revisao de autorizacao (sem publicar)")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(question)
        dialog.setMinimumWidth(500)
        confirm_btn = dialog.addButton("Confirmar simulacao", QMessageBox.AcceptRole)
        dialog.addButton("Cancelar", QMessageBox.RejectRole)
        dialog.exec()
        accepted = dialog.clickedButton() is confirm_btn
        if accepted:
            try:
                verify_review_contract(self._preview_snapshot, self.project_id,
                                       self.folder.text().strip(), contract)
            except (ValueError, OSError) as exc:
                self.cancel_preview()
                QMessageBox.warning(self, "Revisao desatualizada", str(exc))
                return
        self.notice.setText("Simulacao registrada na interface. Nenhum indice alterado."
                            if accepted else
                            "Simulacao cancelada. Nenhum indice alterado.")
        self.index_btn.setEnabled(False)

    def _confirm_generation_operation(self,job_id,operation,title,description,token):
        if self._busy:
            return
        from rag.runtime.auto_index_queue import default_queue_path,get_job
        job=get_job(default_queue_path(),job_id)
        if job is None or job["project_id"]!=self.project_id:
            QMessageBox.warning(self,title,"Job não pertence ao projeto selecionado.")
            return
        message=(
            description+"\n\nProjeto: "+self.project_id+
            "\nJob: "+job_id+
            "\n\nA geração pública codebridge NÃO será alterada."
        )
        if QMessageBox.question(
            self,title,message,
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No,
        )!=QMessageBox.Yes:
            return
        self._run(operation,{"job_id":job_id,"confirmation":token})

    def _prepare_generation(self,job_id):
        self._confirm_generation_operation(
            job_id,"auto_prepare_generation","Preparar geração verificada",
            "Copiar o índice concluído e o snapshot das fontes aprovadas "
            "para uma geração isolada? Isso pode ocupar espaço em disco.",
            "RAG_AUTO_PREPARE:"+self.project_id+":"+job_id,
        )

    def _enable_canary(self,job_id):
        self._confirm_generation_operation(
            job_id,"auto_enable_canary","Habilitar consulta isolada",
            "Registrar a geração no catálogo de leitura, com backup e "
            "rollback. Não substitui o RAG público e não remove outros projetos.",
            "RAG_AUTO_CANARY:"+self.project_id+":"+job_id,
        )

    def _rollback_canary(self,job_id):
        self._confirm_generation_operation(
            job_id,"auto_rollback_canary","Reverter habilitação isolada",
            "Restaurar o catálogo anterior pelo backup auditado? "
            "A geração preparada será preservada em disco.",
            "RAG_AUTO_CANARY_ROLLBACK:"+job_id,
        )

    def prepare_auto_job(self):
        """Compute a fingerprinted preview; no persistent queue is created."""
        if self.project_id=="codebridge":
            QMessageBox.warning(
                self,"Projeto reservado",
                "O identificador codebridge pertence ao índice público. "
                "Crie ou selecione outro projeto para a indexação automática.",
            )
            return
        root = self.folder.text().strip()
        if self._busy:
            return
        if not root or not Path(root).is_dir():
            QMessageBox.information(self, "Indexação automática", "Escolha uma pasta primeiro.")
            return
        self._auto_manifest = None
        self.auto_authorize_btn.setEnabled(False)
        self._auto_request = (
            self._preview_revision, self.project_id,
            str(Path(root).resolve()),
            tuple(self._selected_paths or ()),
        )
        self.auto_info.setText("Auditando fontes, hashes e permissões...")
        self._run("auto_preview", {
            "project":self.project_id,"root":root,
            "paths":list(self._selected_paths) if self._selected_paths else None,
        })

    def authorize_auto_job(self):
        """Ask the operator before persisting a source-scoped inert queue job."""
        if self._busy or not self._auto_manifest or not self._auto_request:
            return
        preview=self._auto_manifest
        expected=self._auto_request
        current=(
            self._preview_revision, self.project_id,
            str(Path(self.folder.text().strip()).resolve()),
            tuple(self._selected_paths or ()),
        )
        if current != expected:
            self.cancel_preview()
            QMessageBox.warning(self, "Prévia desatualizada", "Prepare os arquivos novamente.")
            return
        question = (
            "Autorizar a criação de um trabalho na fila?\n\n"
            f"Projeto: {preview['project_id']}\n"
            f"Pasta: {preview['source_root']}\n"
            f"Arquivos aprováveis: {preview['candidate_count']}\n"
            f"Código: {preview['code_count']} · documentação: {preview['text_count']}\n"
            f"SHA-256: {preview['review_sha256']}\n\n"
            "Não inicia GPU, CPU Jina ou publicação. A execução automática "
            "ainda será habilitada em uma etapa posterior."
        )
        answer=QMessageBox.question(
            self,"Aprovar arquivos para a fila",question,
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No,
        )
        if answer!=QMessageBox.Yes:
            self.auto_info.setText("Autorização cancelada; nenhum trabalho criado.")
            return
        self.auto_authorize_btn.setEnabled(False)
        self._run("auto_approve", {
            "project":preview["project_id"],
            "root":preview["source_root"],
            "paths":list(self._selected_paths) if self._selected_paths else None,
            "review_sha256":preview["review_sha256"],
        })

    def _run(self, operation, args):
        if self._busy:
            return
        self._busy = True
        self.notice.setText("Carregando...")
        for button in (
            self.refresh_btn,self.search_btn,self.plan_btn,
            self.project_picker,self.new_project_btn,self.browse_btn,
            self.browse_files_btn,self.auto_prepare_btn,self.auto_authorize_btn,
        ):
            button.setEnabled(False)
        def work():
            try:
                outcome = (operation, _rag_operation(operation, args), "")
            except Exception as exc:
                outcome = (operation, {}, str(exc))
            try:
                self._worker.completed.emit(*outcome)
            except RuntimeError:
                # Qt already destroyed the receiver during a graceful close.
                # Do not make a second emit against a deleted QObject.
                pass
        threading.Thread(target=work, daemon=True).start()

    def _complete(self, operation, data, error):
        self._busy = False
        for button in (
            self.refresh_btn,self.search_btn,self.plan_btn,
            self.project_picker,self.new_project_btn,self.browse_btn,
            self.browse_files_btn,self.auto_prepare_btn,
        ):
            button.setEnabled(True)
        self.auto_authorize_btn.setEnabled(self._auto_manifest is not None)
        if error:
            if operation in (
                "auto_prepare_generation","auto_enable_canary","auto_rollback_canary"
            ):
                self.auto_card.refresh()
                self.notice.setText("Operação de geração recusada: "+error)
                return
            if operation == "plan":
                from rag.runtime.incremental_preview_request import matching_preview_request
                pending = self._plan_request
                self._plan_request = None
                if not matching_preview_request(pending, self._preview_revision,
                                                self.project_id, self.folder.text().strip()):
                    return
            if operation == "status":
                self.rag_status.setText("RAG: OFFLINE")
            if operation in ("auto_preview","auto_approve"):
                self._auto_manifest = None
                self._auto_request = None
                self.auto_authorize_btn.setEnabled(False)
                self.auto_info.setText("Falha na preparação da fila: "+error)
            self.notice.setText("Nao foi possivel carregar: " + error)
            return
        self.notice.setText("")
        if operation == "status":
            ready = str((data.get("index") or {}).get("state") or "").upper() == "READY"
            self.rag_status.setText("RAG: ONLINE" if ready else "RAG: OFFLINE")
            projects = data.get("projects") or []
            isolated = [
                p for p in (data.get("isolated_project_indexes") or [])
                if p.get("state") == "ISOLATED_READ_ONLY"
            ]
            count = (
                sum(int(p.get("document_count") or 0) for p in projects)
                + sum(int(p.get("document_count") or 0) for p in isolated)
            )
            self.summary.setText(f"Meus conhecimentos — {count} documentos")
            names = sorted(set(["codebridge"] +
                               [str(p.get("project_id")) for p in projects if p.get("project_id")] +
                               [str(p.get("project_id")) for p in isolated if p.get("project_id")] +
                               list_projects()))
            self.project_picker.blockSignals(True)
            self.project_picker.clear()
            self.project_picker.addItems(names)
            if self.project_id not in names:
                self.project_id = names[0]
                self._selected_paths = None
            self.auto_card.set_project(self.project_id)
            self.project_picker.setCurrentText(self.project_id)
            self.project_picker.blockSignals(False)
            self._run("documents", {"project": self.project_id})
        elif operation == "auto_preview":
            expected=self._auto_request
            current=(
                self._preview_revision,self.project_id,
                str(Path(self.folder.text().strip()).resolve()),
                tuple(self._selected_paths or ()),
            )
            if expected is None or current!=expected:
                self._auto_manifest=None
                self.auto_authorize_btn.setEnabled(False)
                return
            self._auto_manifest=data
            self.auto_authorize_btn.setEnabled(True)
            self.auto_info.setText(
                f"{data['candidate_count']} arquivos auditados · "
                f"SHA-256: {data['review_sha256'][:16]}… · "
                "Nenhuma fila criada."
            )
        elif operation == "auto_approve":
            self._auto_manifest=None
            self._auto_request=None
            self.auto_authorize_btn.setEnabled(False)
            self.auto_info.setText(
                "Trabalho registrado: "+str(data['job_id'])+
                ". Aguardando executor; nenhum modelo iniciado."
            )
            self.auto_card.refresh()
            self.set_page(3)
        elif operation in (
            "auto_prepare_generation","auto_enable_canary","auto_rollback_canary"
        ):
            self.auto_card.refresh()
            self.notice.setText({
                "auto_prepare_generation":"Versão verificada preparada (sem publicar).",
                "auto_enable_canary":"Consulta isolada habilitada (catálogo com backup).",
                "auto_rollback_canary":"Catálogo anterior restaurado.",
            }[operation])
            if operation!="auto_prepare_generation":
                self.refresh()
        elif operation == "documents":
            self._documents = list(data)
            self.files.clear()
            for item in self._documents:
                self.files.addItem(str(item["path"]))
            private_paths = (
                [str(item["path"]) for item in self._documents]
                if self.project_id != "codebridge" else []
            )
            self.deletion_review_panel.set_project_files(
                self.project_id, private_paths, self._documents,
            )
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
            expected = self._plan_request
            self._plan_request = None
            from rag.runtime.incremental_preview_request import matching_preview_request
            if not matching_preview_request(expected, self._preview_revision,
                                            self.project_id, self.folder.text().strip()):
                return
            plan = data.get("plan") or {}
            assessment = data.get("incremental") or {}
            from rag.runtime.incremental_preview_view import describe_incremental_preview
            try:
                view = describe_incremental_preview(plan, assessment)
            except (ValueError, TypeError) as exc:
                self.candidates.clear()
                self.plan_summary.setText("Previa indisponivel: dados inconsistentes.")
                self.notice.setText("Nao foi possivel validar a previa: " + str(exc))
                return
            self.candidates.clear()
            for item in view["rows"]:
                self.candidates.addItem(f'[{item["status"]}] {item["path"]}')
            self.plan_summary.setText(view["summary"])
            from rag.runtime.incremental_preview_confirmation import revalidate_preview
            try:
                start = data.get("preview_start")
                if start is None:
                    raise ValueError("no valid candidate snapshot")
                revalidate_preview(start, self.project_id, self.folder.text().strip())
                self._preview_snapshot = start
            except (ValueError, OSError) as exc:
                self._preview_snapshot = None
                self.notice.setText("Previa nao confirmavel: " + str(exc))
            self.confirm_preview_btn.setEnabled(self._preview_snapshot is not None)
            self.review_auth_btn.setEnabled(self._preview_snapshot is not None)
            self.index_btn.setEnabled(False)

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
