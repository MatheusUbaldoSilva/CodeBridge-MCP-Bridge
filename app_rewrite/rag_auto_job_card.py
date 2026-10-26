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
from rag.runtime.auto_index_queue import default_queue_path, list_jobs, inspect_queue_operational, preferred_display_job
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
    prepare_requested = Signal(str)
    enable_requested = Signal(str)
    rollback_requested = Signal(str)

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
        self.details_toggle=QPushButton("▸ Diagnóstico e recursos")
        self.details_toggle.setCheckable(True)
        self.details_toggle.toggled.connect(self._toggle_diagnostics)
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
        self.runtime=QLabel("Perfil previsto: CODE GPU · TEXT CPU")
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
        canary_controls=QHBoxLayout()
        self.prepare_button=QPushButton("Preparar versão")
        self.enable_button=QPushButton("Habilitar leitura")
        self.rollback_button=QPushButton("Reverter habilitação")
        self.prepare_button.clicked.connect(
            lambda: self.prepare_requested.emit(self._job_id) if self._job_id else None
        )
        self.enable_button.clicked.connect(
            lambda: self.enable_requested.emit(self._job_id) if self._job_id else None
        )
        self.rollback_button.clicked.connect(
            lambda: self.rollback_requested.emit(self._job_id) if self._job_id else None
        )
        canary_controls.addWidget(self.prepare_button,1)
        canary_controls.addWidget(self.enable_button,1)
        canary_controls.addWidget(self.rollback_button,1)
        outer.addLayout(canary_controls)
        self.detail=QLabel("Nenhum worker automático será iniciado por este painel.")
        self.detail.setObjectName("RagAutoSmall")
        self.detail.setWordWrap(True)
        outer.addWidget(self.detail)
        self.alert=QLabel("")
        self.alert.setObjectName("RagAutoSmall")
        self.alert.setWordWrap(True)
        self.alert.setVisible(False)
        outer.addWidget(self.alert)
        outer.addWidget(self.details_toggle)
        self.diagnostics=QLabel("Diagnóstico não consultado")
        self.diagnostics.setObjectName("RagAutoSmall")
        self.diagnostics.setWordWrap(True)
        self.diagnostics.setVisible(False)
        outer.addWidget(self.diagnostics)
        self.history_toggle=QPushButton("▸ Histórico recente")
        self.history_toggle.setCheckable(True)
        self.history_toggle.toggled.connect(self._toggle_history)
        outer.addWidget(self.history_toggle)
        self.history_label=QLabel("Histórico não consultado")
        self.history_label.setObjectName("RagAutoSmall")
        self.history_label.setWordWrap(True)
        self.history_label.setVisible(False)
        outer.addWidget(self.history_label)
        self.queue_health=QLabel("Fila: aguardando consulta")
        self.queue_health.setObjectName("RagAutoSmall")
        self.queue_health.setWordWrap(True)
        outer.addWidget(self.queue_health)
        self.resource_sampled.connect(self._accept_resource_sample)
        self._history_timer=QTimer(self)
        self._history_timer.setInterval(15000)
        self._history_timer.timeout.connect(self._refresh_expanded_history)
        self._history_timer.start()
        self._resource_timer=QTimer(self)
        self._resource_timer.setInterval(15000)
        self._resource_timer.timeout.connect(self._request_resource_sample)
        self._resource_busy=False
        self._resource_sample=None
        self._resource_timer.start()
        self._queue_timer=QTimer(self)
        self._queue_timer.setInterval(30000)
        self._queue_timer.timeout.connect(self._refresh_queue_health)
        self._queue_timer.start()
        self._refresh_queue_health()
        self._timer=QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _refresh_queue_health(self) -> None:
        try:
            info=inspect_queue_operational(self.queue_path)
            if info.get("state")=="NOT_INITIALIZED":
                message="Fila ainda não inicializada"
            else:
                counts=info.get("by_state") or {}
                active=sum(counts.get(state,0) for state in ("RUNNING","PAUSE_REQUESTED","CANCEL_REQUESTED"))
                pending=counts.get("QUEUED",0)
                message=f'Fila: {info["jobs"]} jobs · {active} em operação · {pending} aguardando'
            self.queue_health.setText(message)
        except (OSError,ValueError,RuntimeError,KeyError) as exc:
            self.queue_health.setText("Fila indisponível: "+type(exc).__name__)

    def _toggle_history(self, expanded: bool) -> None:
        self.history_label.setVisible(expanded)
        self.history_toggle.setText("▾ Ocultar histórico" if expanded else "▸ Histórico recente")
        if expanded:
            self._refresh_history()

    def _refresh_expanded_history(self) -> None:
        if self.history_toggle.isChecked():
            self._refresh_history()

    def _refresh_history(self) -> None:
        try:
            from datetime import datetime
            jobs=list_jobs(self.queue_path,project_id=self.project_id,limit=8)
            pinned=preferred_display_job(self.queue_path,self.project_id)
            if pinned and pinned["state"] in ("RUNNING","PAUSE_REQUESTED","CANCEL_REQUESTED","VALIDATING"):
                if all(job["job_id"]!=pinned["job_id"] for job in jobs):
                    jobs=[pinned,*jobs]
            rows=[]
            for job in jobs:
                changed=job.get("updated_at_epoch")
                when=datetime.fromtimestamp(changed).strftime("%d/%m %H:%M") if changed else "sem data"
                rows.append(
                    f'{str(job["job_id"])[:12]} · {_LABELS.get(job["state"],job["state"])}'
                    f' · {job["file_count"]} arquivos · {when}'
                )
            self.history_label.setText("\n".join(rows) if rows else "Nenhum trabalho registrado neste projeto")
        except (OSError,ValueError,RuntimeError,KeyError) as exc:
            self.history_label.setText("Histórico indisponível: "+type(exc).__name__)

    def _request_resource_sample(self) -> None:
        if not self.details_toggle.isChecked() or self._resource_busy:
            return
        self._resource_busy=True
        import threading
        # Probe in a background thread; communicate only through Qt signals.
        threading.Thread(target=self._sample_resources,daemon=True).start()

    resource_sampled=Signal(object)

    def _sample_resources(self) -> None:
        from rag.runtime.auto_index_telemetry import _probe_system_resources
        try:
            value=_probe_system_resources()
        except Exception:
            value=(None,None)
        try:
            self.resource_sampled.emit(value)
        except RuntimeError:
            # The Qt widget may have been destroyed while the probe was running.
            return

    def _accept_resource_sample(self, value: object) -> None:
        self._resource_sample=value
        self._resource_busy=False
        if self.details_toggle.isChecked():
            self._refresh_diagnostics()

    def _toggle_diagnostics(self, expanded: bool) -> None:
        self.diagnostics.setVisible(expanded)
        self.details_toggle.setText("▾ Ocultar diagnóstico" if expanded else "▸ Diagnóstico e recursos")
        if expanded:
            self._refresh_diagnostics()
            self._request_resource_sample()

    def _refresh_diagnostics(self) -> None:
        if not self._job_id:
            self.diagnostics.setText("Nenhum job selecionado")
            return
        try:
            data=self._status
            if data is None or data.get("job_id")!=self._job_id:
                self.diagnostics.setText("Diagnóstico aguardando job atual")
                return
            import time
            from rag.runtime.auto_index_supervisor import inspect_index_supervisor
            lease=inspect_index_supervisor(self.queue_path)
            expiry=lease.get("lease_until_epoch")
            lease_expired=(lease.get("state")=="LEASE_RECORDED" and isinstance(expiry,(int,float)) and expiry<=time.time())
            lines=[
                f'Job: {data["job_id"]}',
                f'Estado: {_LABELS.get(data["state"],data["state"])}',
                f'TEXT: {data["text_vectors_done"]} vetores · CODE: {data["code_vectors_done"]} vetores',
                f'Supervisor reservado: {"sim" if data["supervisor_reserved"] else "não"}',
                f'Último evento: {data["last_event"] or "indisponível"}',
            ]
            if lease_expired:
                lines.append('Atenção: reserva do supervisor expirada; confira a recuperação do worker.')
            elif lease.get("state")=="LEASE_RECORDED" and lease.get("job_id")==self._job_id:
                lines.append('Reserva atual do job registrada no supervisor.')
            if data.get("last_error"):
                lines.append('Erro: '+str(data["last_error"]))
            if self._resource_sample:
                memory,gpu=self._resource_sample
                if memory:
                    lines.append(f'RAM livre: {memory["free_mib"]} / {memory["total_mib"]} MiB')
                if gpu:
                    lines.append(f'GPU: {gpu["used_mib"]} / {gpu["total_mib"]} MiB · uso {gpu["utilization_percent"]}%')
            self.diagnostics.setText("\n".join(lines))
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            self.diagnostics.setText("Diagnóstico indisponível: "+type(exc).__name__)

    def set_project(self,project_id: str) -> None:
        self.project_id=project_id
        self.project.setText(project_id)
        self._job_id=None
        self._launched_job_id=None
        self._launched_pid=None
        self._resource_sample=None
        self.refresh()

    def refresh(self) -> None:
        try:
            selected=preferred_display_job(self.queue_path,self.project_id)
            if selected is None:
                self._job_id=None
                self._status=None
                self._clear()
                if self.history_toggle.isChecked():
                    self._refresh_history()
                return
            self._job_id=selected["job_id"]
            self._status=read_auto_index_job_status(
                self.queue_path,self._job_id,probe_resources=False,
            )
            self._render(self._status)
            if self.details_toggle.isChecked():
                self._refresh_diagnostics()
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
        self.prepare_button.setEnabled(False)
        self.enable_button.setEnabled(False)
        self.rollback_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.detail.setText("Selecione arquivos e aprove a preparação de uma fila.")
        self.alert.setText("")
        self.alert.setVisible(False)

    def _render(self,data: dict) -> None:
        current=data["state"]
        warning={
            "FAILED":"Falha registrada: consulte o diagnóstico antes de retomar.",
            "PAUSE_REQUESTED":"Pausa solicitada: aguardando checkpoint seguro.",
            "CANCEL_REQUESTED":"Cancelamento solicitado: aguardando confirmação do worker.",
        }.get(current,"")
        if current in ("RUNNING","PAUSE_REQUESTED","CANCEL_REQUESTED","VALIDATING") and data.get("supervisor_lease_expired"):
            warning=(warning+" Reserva do worker expirada: revisar retomada antes de agir.").strip()
        if data.get("last_error"):
            warning=(warning+" "+str(data["last_error"])).strip()
        self.alert.setText(warning)
        self.alert.setVisible(bool(warning))
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
        canary_state="NOT_PREPARED"
        if current=="READY_FOR_REVIEW":
            try:
                from rag.runtime.auto_index_generation import _paths
                generation,snapshot=_paths(self.queue_path,self._job_id,self.project_id)
                if generation.is_dir() and snapshot.is_dir():
                    canary_state="PREPARED_NOT_REGISTERED"
                if self.queue_path==default_queue_path() and canary_state!="NOT_PREPARED":
                    from rag.runtime.auto_index_promotion import auto_canary_status
                    canary_state=auto_canary_status(self._job_id)["state"]
            except Exception:
                canary_state="UNAVAILABLE"
        self.prepare_button.setEnabled(
            current=="READY_FOR_REVIEW" and canary_state=="NOT_PREPARED"
        )
        self.enable_button.setEnabled(
            current=="READY_FOR_REVIEW" and canary_state=="PREPARED_NOT_REGISTERED"
        )
        self.rollback_button.setEnabled(
            current=="READY_FOR_REVIEW" and canary_state=="CANARY_ACTIVE"
        )
        if current=="QUEUED":
            self.detail.setText(
                "Arquivos aprovados. Use Iniciar indexação quando desejar executar o Jina."
            )
        elif current in ("PAUSE_REQUESTED","CANCEL_REQUESTED"):
            self.detail.setText(
                "Solicitação registrada. Aguardando confirmação do worker no checkpoint."
            )
        elif current=="READY_FOR_REVIEW":
            details={
                "NOT_PREPARED":"Índice concluído. Prepare a versão verificada para consulta isolada.",
                "PREPARED_NOT_REGISTERED":"Versão verificada; habilitação de leitura requer confirmação.",
                "CANARY_ACTIVE":"Canário em leitura isolada. Geração pública preservada.",
                "UNAVAILABLE":"Estado do candidato indisponível: confira integridade antes de habilitar.",
            }
            self.detail.setText(details.get(canary_state,"Estado não reconhecido."))
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
