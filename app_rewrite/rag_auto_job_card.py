"""RAG-AUTO-01.7: dark progress card matching the approved UI concept.

An explicit DEV GUI component backed by real job data. It cannot launch
models or publish an index. Integration into RagPanel is a separate gated step.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from rag.runtime.auto_index_controls import request_auto_index_control
from rag.runtime.auto_index_queue import default_queue_path, list_jobs
from rag.runtime.auto_index_telemetry import read_auto_index_job_status


_LABELS = {
    "DRAFT":"Rascunho",
    "AWAITING_APPROVAL":"Aguardando aprovação",
    "QUEUED":"Aguardando executor",
    "RUNNING":"Indexando",
    "PAUSE_REQUESTED":"Solicitando pausa",
    "PAUSED":"Pausado",
    "CANCEL_REQUESTED":"Solicitando cancelamento",
    "CANCELLED":"Cancelado",
    "VALIDATING":"Validando",
    "READY_FOR_REVIEW":"Índice pronto para revisão",
    "FAILED":"Falha de indexação",
}
_STYLE = """
QFrame#RagAutoJobCard {
    background: #070707;
    border: 1px solid #303030;
    border-radius: 16px;
}
QFrame#RagAutoJobCard QLabel {
    color: #dedede;
    border: 0;
    background: transparent;
}
QFrame#RagAutoJobCard QLabel#RagAutoTitle {
    font-size: 18px;
    font-weight: 700;
}
QFrame#RagAutoJobCard QLabel#RagAutoProject {
    font-size: 14px;
    font-weight: 650;
}
QFrame#RagAutoJobCard QLabel#RagAutoSmall {
    color: #aaaaaa;
    font-size: 11px;
}
QFrame#RagAutoJobCard QProgressBar {
    border: 0;
    border-radius: 6px;
    height: 12px;
    background: #252525;
    color: transparent;
    text-align: center;
}
QFrame#RagAutoJobCard QProgressBar::chunk {
    background-color: #198a72;
    border-radius: 6px;
}
QFrame#RagAutoJobCard QPushButton {
    color: #dedede;
    background: #090909;
    border: 1px solid #444444;
    border-radius: 15px;
    min-height: 34px;
    font-size: 12px;
    font-weight: 600;
}
QFrame#RagAutoJobCard QPushButton:disabled {
    color: #777777;
    border-color: #252525;
}
QFrame#RagAutoJobCard QPushButton:hover:enabled {
    border-color: #198a72;
}
"""


class RagAutoJobCard(QFrame):
    job_changed = Signal(str, str)

    def __init__(
        self, parent: QWidget | None=None, *,
        queue_path: Path | None=None, project_id: str="codebridge",
    ):
        super().__init__(parent)
        self.setObjectName("RagAutoJobCard")
        self.setStyleSheet(_STYLE)
        self.queue_path=Path(queue_path) if queue_path is not None else default_queue_path()
        self.project_id=project_id
        self._job_id: str | None=None
        self._status: dict | None=None
        self._launched_job_id: str | None=None
        self._launched_pid: int | None=None
        outer=QVBoxLayout(self)
        outer.setContentsMargins(18,17,18,16)
        outer.setSpacing(11)
        title=QHBoxLayout()
        self.header=QLabel("Meus conhecimentos")
        self.header.setObjectName("RagAutoTitle")
        self.environment=QLabel("Projeto DEV")
        self.environment.setObjectName("RagAutoSmall")
        title.addWidget(self.header,1)
        title.addWidget(self.environment)
        outer.addLayout(title)
        self.subtitle=QLabel("Indexação automática — fila e progresso")
        self.subtitle.setObjectName("RagAutoSmall")
        outer.addWidget(self.subtitle)
        self.project=QLabel(project_id)
        self.project.setObjectName("RagAutoProject")
        outer.addWidget(self.project)
        self.sources=QLabel("Nenhum trabalho na fila")
        self.sources.setObjectName("RagAutoSmall")
        outer.addWidget(self.sources)
        progress_title=QHBoxLayout()
        self.status=QLabel("Sem trabalho de indexação")
        self.percent=QLabel("--%")
        progress_title.addWidget(self.status,1)
        progress_title.addWidget(self.percent)
        outer.addLayout(progress_title)
        self.bar=QProgressBar()
        self.bar.setRange(0,1000)
        self.bar.setTextVisible(False)
        self.bar.setValue(0)
        outer.addWidget(self.bar)
        counts=QHBoxLayout()
        self.counts=QLabel("Sem contadores disponíveis")
        self.counts.setObjectName("RagAutoSmall")
        self.runtime=QLabel("Jina CODE · GPU · ubatch 32 | TEXT · CPU")
        self.runtime.setObjectName("RagAutoSmall")
        counts.addWidget(self.counts,1)
        counts.addWidget(self.runtime)
        outer.addLayout(counts)
        controls=QHBoxLayout()
        self.start_button=QPushButton("Iniciar indexação")
        self.start_button.clicked.connect(self._request_start)
        self.pause_button=QPushButton("Pausar")
        self.cancel_button=QPushButton("Cancelar trabalho")
        self.pause_button.clicked.connect(self._request_pause_or_resume)
        self.cancel_button.clicked.connect(self._request_cancel)
        controls.addWidget(self.start_button,1)
        controls.addWidget(self.pause_button,1)
        controls.addWidget(self.cancel_button,1)
        outer.addLayout(controls)
        self.detail=QLabel("Nenhum worker automático será iniciado por este painel.")
        self.detail.setObjectName("RagAutoSmall")
        self.detail.setWordWrap(True)
        outer.addWidget(self.detail)
        self._timer=QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def set_project(self,project_id: str) -> None:
        self.project_id=project_id
        self.project.setText(project_id)
        self._job_id=None
        self._launched_job_id=None
        self._launched_pid=None
        self.refresh()

    def refresh(self) -> None:
        try:
            jobs=list_jobs(self.queue_path,project_id=self.project_id,limit=1)
            if not jobs:
                self._job_id=None
                self._status=None
                self._clear()
                return
            selected=jobs[0]
            self._job_id=selected["job_id"]
            self._status=read_auto_index_job_status(
                self.queue_path,self._job_id,probe_resources=False,
            )
            self._render(self._status)
        except Exception as exc:
            self._job_id=None
            self._status=None
            self._clear()
            self.detail.setText("Fila indisponível: "+type(exc).__name__)

    def _clear(self) -> None:
        self.sources.setText("Nenhum trabalho na fila")
        self.status.setText("Sem trabalho de indexação")
        self.percent.setText("--%")
        self.bar.setValue(0)
        self.counts.setText("Sem contadores disponíveis")
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.detail.setText("Selecione arquivos e aprove a preparação de uma fila.")

    def _render(self,data: dict) -> None:
        current=data["state"]
        self.status.setText(_LABELS.get(current,current))
        self.sources.setText(
            f'{data["file_count"]} arquivos · {data["chunk_count"]} trechos'
        )
        if data["percent_known"]:
            percent=data["percent"]
            self.percent.setText(f'{percent:.2f}%'.replace(".",","))
            self.bar.setValue(round(percent*10))
            self.counts.setText(
                f'{data["vectors_done"]:,} / {data["vectors_expected"]:,} embeddings'
                    .replace(",","." )
            )
        else:
            self.percent.setText("--%")
            self.bar.setValue(0)
            self.counts.setText("Aguardando inventário e contagem real de chunks")
        recently_launched=False
        if current=="QUEUED" and self._launched_job_id==self._job_id:
            import psutil
            try:
                process=psutil.Process(self._launched_pid)
                arguments=process.cmdline()
                recently_launched=(
                    "rag.runtime.auto_index_runner" in arguments
                    and self._job_id in arguments and process.is_running()
                )
            except (psutil.Error,TypeError,ValueError):
                recently_launched=False
            if not recently_launched:
                self._launched_job_id=None
                self._launched_pid=None
        self.start_button.setEnabled(
            current=="QUEUED" and data["reviewed"] and not recently_launched
        )
        self.pause_button.setText("Retomar" if current=="PAUSED" else "Pausar")
        self.pause_button.setEnabled(current in ("QUEUED","RUNNING","PAUSED"))
        self.cancel_button.setEnabled(current in (
            "DRAFT","AWAITING_APPROVAL","QUEUED","RUNNING",
            "PAUSE_REQUESTED","PAUSED"
        ))
        if current=="QUEUED":
            self.detail.setText(
                "Arquivos aprovados. O executor automático ainda não foi liberado."
            )
        elif current in ("PAUSE_REQUESTED","CANCEL_REQUESTED"):
            self.detail.setText(
                "Solicitação registrada. Aguardando confirmação do worker no checkpoint."
            )
        elif current=="READY_FOR_REVIEW":
            self.detail.setText(
                "Concluído em staging. Publicação exige autorização e rollback."
            )
        else:
            self.detail.setText(
                "Controle persistente: não altera a geração pública do RAG."
            )

    def _request_start(self) -> None:
        if not self._status or not self._job_id or self._status["state"]!="QUEUED":
            return
        answer=QMessageBox.question(
            self,"Iniciar indexação real",
            "Iniciar o worker Jina para os arquivos já aprovados?\n\n"
            "CODE: GPU CUDA (ubatch 32). TEXT: CPU.\n"
            "Os embeddings serão gravados somente em um índice isolado.\n"
            "A geração pública não será substituída.\n"
            "É possível solicitar pausa na fronteira de um lote.",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No,
        )
        if answer!=QMessageBox.Yes:
            return
        self.start_button.setEnabled(False)
        try:
            from rag.runtime.auto_index_launch import launch_approved_auto_job
            outcome=launch_approved_auto_job(
                self.queue_path,self._job_id,execute=True,
                operator_approved=True,
                confirmation="RAG_AUTO_LAUNCH:"+self._job_id,
            )
        except (OSError,ValueError,PermissionError,RuntimeError) as exc:
            self.detail.setText("Falha ao iniciar indexação: "+str(exc))
            self.start_button.setEnabled(True)
            return
        self.refresh()
        if outcome["state"]=="PROCESS_STARTED_UNVERIFIED":
            self._launched_job_id=self._job_id
            self._launched_pid=int(outcome["pid"])
            self.start_button.setEnabled(False)
            self.detail.setText(
                "Processo iniciado. Progresso conferido no SQLite/Qdrant; "
                "PID "+str(outcome["pid"])
            )
        else:
            self.detail.setText("Início adiado: memória insuficiente.")
        self.job_changed.emit(self._job_id,outcome["state"])

    def request_graceful_pause(self) -> bool:
        """Request a safe batch-boundary stop when the app is closing."""
        if not self._job_id:
            return False
        from rag.runtime.auto_index_queue import get_job
        state=get_job(self.queue_path,self._job_id)
        if state is None or state["state"]!="RUNNING":
            return False
        request_auto_index_control(
            self.queue_path,self._job_id,"PAUSE",
            operator_requested=True,control_enabled=True,
        )
        return True

    def _request_pause_or_resume(self) -> None:
        if not self._status or not self._job_id:
            return
        action="RESUME" if self._status["state"]=="PAUSED" else "PAUSE"
        self._apply_control(action)

    def _request_cancel(self) -> None:
        if not self._job_id or not self._status:
            return
        answer=QMessageBox.question(
            self,"Cancelar indexação",
            "Cancelar o trabalho selecionado? Os vetores já gravados "
            "não serão apagados automaticamente.",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No,
        )
        if answer==QMessageBox.Yes:
            self._apply_control("CANCEL")

    def _apply_control(self,action: str) -> None:
        if not self._job_id:
            return
        try:
            result=request_auto_index_control(
                self.queue_path,self._job_id,action,
                operator_requested=True,control_enabled=True,
            )
        except (OSError,ValueError,PermissionError,RuntimeError) as exc:
            self.detail.setText(
                "Controle não aplicado: "+str(exc)
            )
            self.refresh()
            return
        self.refresh()
        self.job_changed.emit(self._job_id,result["state"])
