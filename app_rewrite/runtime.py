import json
import os
import secrets
import threading
import time

from api_server import BridgeAPI
from author_mcp_manager import AuthorMCPManager
from constants import APP_NAME, APP_VERSION, DATA_DIR, DEFAULT_HOST, RUNTIME_FILE
from executor import ExecutionEngine
from external_prepare_store import ExternalPrepareStore, ExternalPrepareConflict, command_hash
from external_execute_store import ExternalExecuteStore, ExternalExecuteConflict
from execution_ledger import ExecutionLedger, ExecutionLedgerConflict
from terminal_errors import PowerShellCommandCancelled
from job_store import JobStore
from migration import migrate_legacy_ssh_once
from terminal_manager import TerminalManager


class BridgeRuntime:
    def __init__(self):
        self.store = JobStore()
        self.terminals = TerminalManager()
        self.instance_id = secrets.token_hex(16)
        self.external_prepares = ExternalPrepareStore(DATA_DIR / 'author_prepared.db')
        self.external_executions = ExternalExecuteStore(DATA_DIR / 'author_executions.db')
        self.execution_ledger = ExecutionLedger(DATA_DIR / 'executions_v2.db')
        self._phase5b_lock = threading.RLock()
        self._phase5b_workers = {}
        self._phase5b_active_execution_id = None
        self._external_prepare_lock = threading.RLock()
        self._external_prepared_request_id = None
        self._external_prepared_target = None
        self._external_prepared_command = None
        self._external_workers_lock = threading.RLock()
        self._external_workers = {}
        self.auto_execute = self.terminals.config.load_auto_execute()
        self.auto_preview_seconds = 0.35
        self.engine = ExecutionEngine(self.store, self.terminals)
        self.author_mcp = AuthorMCPManager()
        self.token = secrets.token_urlsafe(32)
        self.api = BridgeAPI(self, host=DEFAULT_HOST, port=0, token=self.token)
        self.started_at = None
        self._started = False

    @property
    def started(self):
        return self._started
    def start(self):
        if self._started:
            return False

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        migrate_legacy_ssh_once()
        self.external_executions.recover_stale(self.instance_id)
        self.execution_ledger.interrupt_incomplete_from_other_runtime(self.instance_id)

        self.terminals.start()
        self.engine.start()
        self.api.start()

        self.started_at = time.time()
        self._started = True
        self._write_runtime_file()
        self.author_mcp.start()
        return True

    def _write_runtime_file(self):
        payload = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "pid": os.getpid(),
            "host": self.api.host,
            "port": self.api.port,
            "token": self.token,
            "started_at": self.started_at,
        }
        temp = RUNTIME_FILE.with_suffix(".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(RUNTIME_FILE)

    def set_auto_execute(self, enabled):
        self.auto_execute = bool(enabled)
        self.terminals.config.save_auto_execute(self.auto_execute)
        return self.auto_execute

    def dispatch_external(self, request_id, target, command):
        request_id = str(request_id or "").strip()
        if not request_id:
            raise ValueError("request_id obrigatorio")
        target = self.terminals.normalize_target(target)
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise ValueError("command invalido")

        digest = command_hash(command)
        previous_prepare = self.external_prepares.get(request_id)
        if previous_prepare is not None:
            if previous_prepare["target"] != target or previous_prepare["command_hash"] != digest:
                raise ExternalPrepareConflict("request_id reutilizado com target/comando diferente")
        previous_execution = self.external_executions.get_by_prepared(request_id)
        if previous_execution is not None:
            state = previous_execution["state"]
            if state in ("FINISHED", "FAILED"):
                prepared = self._external_prepare_result(previous_prepare, duplicate=True) if previous_prepare else {
                    "request_id": request_id, "target": target, "command_hash": digest,
                    "state": "ALREADY_EXECUTED", "prepared_at": None,
                    "duplicate": True, "enter_sent": True,
                }
                prepared["enter_sent"] = True
                return {
                    "mode": "REPLAY",
                    "auto_execute": bool(self.auto_execute),
                    "preview_seconds": self.auto_preview_seconds,
                    "prepared": prepared,
                    "execution": self._external_execution_result(previous_execution, duplicate=True),
                }
            raise RuntimeError("estado de execucao incerto; comando nao sera repetido automaticamente")

        auto = bool(self.auto_execute)
        prepared = self.prepare_external(request_id, target, command)
        result = {
            "mode": "AUTO" if auto else "MANUAL",
            "auto_execute": auto,
            "preview_seconds": self.auto_preview_seconds,
            "prepared": prepared,
            "execution": None,
        }
        if not auto:
            return result
        time.sleep(self.auto_preview_seconds)
        result["execution"] = self.execute_external(f"{request_id}__execute", request_id)
        return result

    def start_external_async(self, request_id, target, command):
        request_id = str(request_id or "").strip()
        if not request_id:
            raise ValueError("request_id obrigatorio")
        target = self.terminals.normalize_target(target)
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise ValueError("command invalido")
        digest = command_hash(command)
        previous = self.external_executions.get_by_prepared(request_id)
        if previous is not None:
            if previous["target"] != target or previous["command_hash"] != digest:
                raise ExternalExecuteConflict("request_id associado a outro target/comando")
            prepared_row = self.external_prepares.get(request_id)
            prepared = self._external_prepare_result(prepared_row, duplicate=True) if prepared_row else {
                "request_id": request_id, "target": target, "command_hash": digest,
                "state": "ALREADY_EXECUTED", "prepared_at": None, "duplicate": True,
                "enter_sent": previous["state"] in ("EXECUTING", "FINISHED", "FAILED"),
            }
            return {"mode": "REPLAY", "auto_execute": bool(self.auto_execute),
                    "preview_seconds": self.auto_preview_seconds, "prepared": prepared,
                    "execution": self._external_execution_result(previous, duplicate=True)}
        prepared = self.prepare_external(request_id, target, command)
        execution_id = f"{request_id}__execute"
        if not self.auto_execute:
            return {"mode": "MANUAL", "auto_execute": False,
                    "preview_seconds": self.auto_preview_seconds, "prepared": prepared,
                    "execution": {"execution_request_id": execution_id,
                                  "prepared_request_id": request_id, "target": target,
                                  "command_hash": digest, "state": "PREPARED",
                                  "duplicate": False, "enter_sent": False}}
        with self._external_prepare_lock:
            row, created = self.external_executions.reserve(
                execution_id, request_id, target, digest, self.instance_id
            )
        if created:
            worker = threading.Thread(
                target=self._run_external_async,
                args=(execution_id, request_id, target, command, self.auto_preview_seconds),
                name=f"CodeBridgeAsync-{execution_id[-12:]}", daemon=True,
            )
            with self._external_workers_lock:
                self._external_workers[execution_id] = worker
            worker.start()
        return {"mode": "ASYNC", "auto_execute": True,
                "preview_seconds": self.auto_preview_seconds, "prepared": prepared,
                "execution": self._external_execution_result(row, duplicate=not created)}

    def _run_external_async(self, execution_id, prepared_request_id, target, command, delay):
        try:
            if delay > 0:
                time.sleep(delay)
            with self._external_prepare_lock:
                row = self.external_executions.get_by_execution(execution_id)
                if row is None or row["state"] != "RESERVED":
                    return
                if self._external_prepared_request_id != prepared_request_id:
                    self.external_executions.mark_failed(
                        execution_id, error_type="PreparedStateLost",
                        error_message="comando preparado nao esta mais ativo; Enter nao foi enviado"
                    )
                    return
                self.external_executions.mark_executing(execution_id, self.instance_id)
                def capture(text):
                    self.external_executions.append_output(execution_id, text)
                try:
                    output = self.terminals.execute_prepared(target, command, on_output=capture)
                    self.external_executions.mark_finished(execution_id, output=output, exit_code=0)
                except Exception as exc:
                    self.external_executions.mark_failed(
                        execution_id, output=getattr(exc, "output", "") or "",
                        exit_code=getattr(exc, "exit_code", None),
                        error_type=type(exc).__name__, error_message=str(exc),
                    )
                finally:
                    self._external_prepared_request_id = None
                    self._external_prepared_target = None
                    self._external_prepared_command = None
        finally:
            with self._external_workers_lock:
                self._external_workers.pop(execution_id, None)

    def execution_status_external(self, execution_id, cursor=0, max_chars=65536):
        execution_id = str(execution_id or "").strip()
        if not execution_id:
            raise ValueError("execution_id obrigatorio")
        row = self.external_executions.get_by_execution(execution_id)
        if row is None:
            raise ValueError("execution_id nao encontrado")
        delta = self.external_executions.read_output(execution_id, cursor, max_chars)
        result = self._external_execution_result(row, duplicate=False)
        result["output_delta"] = delta["text"]
        result["output_cursor"] = delta["cursor"]
        result["output_has_more"] = delta["has_more"]
        result["complete"] = row["state"] in ("FINISHED", "FAILED")
        return result

    def start_phase5b_local(self, request_id, target, command):
        request_id = str(request_id or "").strip()
        if not request_id:
            raise ValueError("request_id obrigatorio")
        target = self.terminals.normalize_target(target)
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise ValueError("command invalido")
        digest = command_hash(command)
        with self._phase5b_lock:
            existing = self.execution_ledger.get_by_request(request_id)
            if existing is not None:
                if existing["target"] != target or existing["command_hash"] != digest:
                    raise ExecutionLedgerConflict("request_id reutilizado com target/comando diferente")
                result = dict(existing); result["duplicate"] = True
                return result
            status = self.terminals.status()
            if status.get("active_target") or status.get("prepared_target"):
                raise RuntimeError("terminal ocupado ou ja possui comando preparado")
            execution_id = "exec_" + secrets.token_hex(16)
            row, _ = self.execution_ledger.create(execution_id, request_id, target, digest, self.instance_id)
            try:
                self.terminals.prepare(target, command)
            except Exception as exc:
                self.execution_ledger.transition(execution_id, "FAILED", runtime_instance=self.instance_id, error_type=type(exc).__name__, error_message=str(exc))
                raise
            worker = threading.Thread(target=self._run_phase5b_local, args=(execution_id, target, command), name=f"CodeBridgeV2-{execution_id[-10:]}", daemon=True)
            self._phase5b_workers[execution_id] = worker
            worker.start()
            result = dict(row); result["duplicate"] = False
            return result

    def _run_phase5b_local(self, execution_id, target, command):
        try:
            if self.auto_preview_seconds > 0:
                time.sleep(self.auto_preview_seconds)
            with self._phase5b_lock:
                row = self.execution_ledger.get(execution_id)
                if row is None or row["state"] != "CREATED":
                    return
                self.execution_ledger.transition(execution_id, "RUNNING", runtime_instance=self.instance_id)
                self._phase5b_active_execution_id = execution_id
            def capture_output(text):
                self.execution_ledger.append_output(execution_id, text)
            try:
                output = self.terminals.execute_prepared(target, command, on_output=capture_output)
                self.execution_ledger.sync_output(execution_id, output)
                self.execution_ledger.transition(execution_id, "FINISHED", runtime_instance=self.instance_id, exit_code=0, output=output)
            except Exception as exc:
                output = getattr(exc, "output", "") or ""
                self.execution_ledger.sync_output(execution_id, output)
                cancelled = "cancel" in type(exc).__name__.lower()
                self.execution_ledger.transition(execution_id, "CANCELLED" if cancelled else "FAILED", runtime_instance=self.instance_id, exit_code=getattr(exc, "exit_code", None), error_type=type(exc).__name__, error_message=str(exc), output=output)
        finally:
            with self._phase5b_lock:
                self._phase5b_workers.pop(execution_id, None)
                if self._phase5b_active_execution_id == execution_id:
                    self._phase5b_active_execution_id = None

    def phase5c_execution_status(self, execution_id):
        execution_id = str(execution_id or "").strip()
        if not execution_id:
            raise ValueError("execution_id obrigatorio")
        row = self.execution_ledger.get(execution_id)
        if row is None:
            raise KeyError(execution_id)
        return {
            "execution_id": row["execution_id"],
            "request_id": row["request_id"],
            "target": row["target"],
            "state": row["state"],
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "complete": row["state"] in ("FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"),
        }

    def phase5c_execution_result(self, execution_id):
        execution_id = str(execution_id or "").strip()
        if not execution_id:
            raise ValueError("execution_id obrigatorio")
        row = self.execution_ledger.get(execution_id)
        if row is None:
            raise KeyError(execution_id)
        terminal = row["state"] in ("FINISHED", "FAILED", "CANCELLED", "INTERRUPTED")
        return {
            "execution_id": row["execution_id"],
            "state": row["state"],
            "ready": terminal,
            "output": row.get("output") or "" if terminal else "",
            "exit_code": row.get("exit_code") if terminal else None,
            "error_type": row.get("error_type") if terminal else None,
            "error_message": row.get("error_message") if terminal else None,
            "finished_at": row.get("finished_at") if terminal else None,
        }

    def phase5f_execution_output(self, execution_id, cursor=0, max_chars=32768):
        execution_id=str(execution_id or "").strip()
        if not execution_id:
            raise ValueError("execution_id obrigatorio")
        return self.execution_ledger.read_output(
            execution_id, cursor=cursor, max_chars=max_chars
        )

    def stop_phase5d_execution(self, execution_id):
        execution_id = str(execution_id or "").strip()
        if not execution_id:
            raise ValueError("execution_id obrigatorio")
        with self._phase5b_lock:
            row = self.execution_ledger.get(execution_id)
            if row is None:
                raise KeyError(execution_id)
            state = row["state"]
            if state in ("FINISHED", "FAILED", "CANCELLED", "INTERRUPTED"):
                return {"execution_id": execution_id, "cancelled": False, "state": state, "reason": "already_terminal"}
            target = self.terminals.normalize_target(row["target"])
            if state == "CREATED":
                if execution_id not in self._phase5b_workers:
                    raise RuntimeError("execucao CREATED sem worker associado")
                if self.terminals.status().get("prepared_target") != target:
                    raise RuntimeError("execucao CREATED nao corresponde ao comando preparado")
                if not self.terminals.discard_prepared():
                    raise RuntimeError("nao foi possivel descartar comando preparado")
                row = self.execution_ledger.transition(execution_id, "CANCELLED", runtime_instance=self.instance_id, error_type="ExecutionCancelledBeforeStart", error_message="execucao cancelada antes do Enter")
                return {"execution_id": execution_id, "cancelled": True, "state": row["state"], "reason": "cancelled_before_start"}
            if state != "RUNNING":
                raise RuntimeError(f"estado nao cancelavel: {state}")
            if self._phase5b_active_execution_id != execution_id:
                raise RuntimeError("execution_id nao corresponde a execucao ativa")
            cancelled = bool(self.terminals.cancel_active())
            return {"execution_id": execution_id, "cancelled": cancelled, "state": "RUNNING", "reason": "ctrl_c_sent" if cancelled else "cancel_failed"}

    def submit(self, target, command):
        target = self.terminals.normalize_target(target)
        job = self.store.create(target, command)
        self.terminals.announce(target, f"[PENDING] aguardando aprovacao\n> {command}")
        return job

    def prepare_external(self, request_id, target, command):
        request_id = str(request_id or "").strip()
        if not request_id:
            raise ValueError("request_id obrigatorio")
        target = self.terminals.normalize_target(target)
        if not isinstance(command, str) or not command.strip() or "\x00" in command:
            raise ValueError("command invalido")

        with self._external_prepare_lock:
            row, created = self.external_prepares.reserve(
                request_id, target, command, self.instance_id
            )
            status = self.terminals.status()
            same_runtime = row["runtime_instance"] == self.instance_id
            if not created and same_runtime:
                if row["state"] == "PREPARED" and status.get("prepared_target") == target:
                    self._external_prepared_request_id = request_id
                    self._external_prepared_target = target
                    self._external_prepared_command = command
                    return self._external_prepare_result(row, duplicate=True)
                if row["state"] in ("PREPARING", "PREPARED"):
                    raise RuntimeError(
                        "estado de preparacao incerto; comando nao sera repetido automaticamente"
                    )
            elif not created and not same_runtime:
                row = self.external_prepares.reset_for_new_runtime(
                    request_id, self.instance_id
                )

            status = self.terminals.status()
            if status.get("active_target") or status.get("prepared_target"):
                raise RuntimeError("terminal ocupado ou ja possui comando preparado")
            self.external_prepares.mark_preparing(request_id, self.instance_id)
            try:
                self.terminals.prepare(target, command)
            except Exception as exc:
                self.external_prepares.mark_failed(request_id, str(exc))
                raise
            row = self.external_prepares.mark_prepared(request_id, self.instance_id)
            self._external_prepared_request_id = request_id
            self._external_prepared_target = target
            self._external_prepared_command = command
            return self._external_prepare_result(row, duplicate=False)

    @staticmethod
    def _external_prepare_result(row, duplicate=False):
        return {
            "request_id": row["request_id"],
            "target": row["target"],
            "command_hash": row["command_hash"],
            "state": row["state"],
            "prepared_at": row.get("prepared_at"),
            "duplicate": bool(duplicate),
            "enter_sent": False,
        }

    def discard_external(self, request_id=None):
        with self._external_prepare_lock:
            status = self.terminals.status()
            if any(bool((status.get(name) or {}).get("executing")) for name in ("powershell", "cmd", "ssh")):
                raise RuntimeError("comando em execucao; use stop em vez de discard")
            active_id = self._external_prepared_request_id
            if active_id is None:
                return {"discarded": False, "reason": "no_external_prepared_command"}
            if request_id and str(request_id) != active_id:
                raise RuntimeError("request_id nao corresponde ao comando preparado")
            discarded = bool(self.terminals.discard_prepared())
            if discarded:
                self.external_prepares.mark_discarded(active_id)
                self._external_prepared_request_id = None
                self._external_prepared_target = None
                self._external_prepared_command = None
            return {"discarded": discarded, "request_id": active_id}

    def execute_external(self, execution_request_id, prepared_request_id):
        execution_request_id = str(execution_request_id or "").strip()
        prepared_request_id = str(prepared_request_id or "").strip()
        if not execution_request_id or not prepared_request_id:
            raise ValueError("execution_request_id e prepared_request_id obrigatorios")
        with self._external_prepare_lock:
            existing = self.external_executions.get_by_prepared(prepared_request_id)
            if self._external_prepared_request_id != prepared_request_id:
                if existing and existing["state"] in ("FINISHED", "FAILED"):
                    return self._external_execution_result(existing, duplicate=True)
                raise RuntimeError("prepared_request_id nao corresponde ao comando preparado")
            target = self._external_prepared_target
            command = self._external_prepared_command
            if not target or not command:
                raise RuntimeError("metadados do comando preparado indisponiveis")
            row, created = self.external_executions.reserve(
                execution_request_id, prepared_request_id, target,
                command_hash(command), self.instance_id,
            )
            if not created:
                if row["state"] in ("FINISHED", "FAILED"):
                    return self._external_execution_result(row, duplicate=True)
                raise RuntimeError(
                    "estado de execucao incerto; Enter nao sera repetido automaticamente"
                )
            self.external_executions.mark_executing(execution_request_id, self.instance_id)
            try:
                output = self.terminals.execute_prepared(target, command)
                row = self.external_executions.mark_finished(
                    execution_request_id, output=output, exit_code=0
                )
            except Exception as exc:
                row = self.external_executions.mark_failed(
                    execution_request_id,
                    output=getattr(exc, "output", "") or "",
                    exit_code=getattr(exc, "exit_code", None),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            finally:
                self._external_prepared_request_id = None
                self._external_prepared_target = None
                self._external_prepared_command = None
            return self._external_execution_result(row, duplicate=False)

    @staticmethod
    def _external_execution_result(row, duplicate=False):
        return {
            "execution_request_id": row["execution_request_id"],
            "prepared_request_id": row["prepared_request_id"],
            "target": row["target"],
            "command_hash": row["command_hash"],
            "state": row["state"],
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "output": row.get("output") or "",
            "exit_code": row.get("exit_code"),
            "error_type": row.get("error_type"),
            "error_message": row.get("error_message"),
            "duplicate": bool(duplicate),
            "enter_sent": row["state"] in ("EXECUTING", "FINISHED", "FAILED"),
        }

    def stop_active(self):
        status = self.terminals.status()
        executing = any(
            bool((status.get(name) or {}).get("executing"))
            for name in ("powershell", "cmd", "ssh")
        )
        # Durante execute_prepared o prepared_target continua preenchido.
        # Execucao ativa precisa receber Ctrl+C, nunca descarte de linha.
        if executing:
            return bool(self.terminals.cancel_active())
        if status.get("prepared_target") and self._external_prepared_request_id:
            result = self.discard_external(self._external_prepared_request_id)
            return bool(result.get("discarded"))
        if status.get("active_target"):
            return bool(self.terminals.cancel_active())
        return bool(self.engine.cancel(None))

    def approve(self, job_id):
        job = self.store.approve(job_id)
        self.terminals.announce(job["target"], "[APPROVED] aguardando preparacao")
        self.engine.wake()
        return job

    def cancel(self, job_id):
        return self.engine.cancel(job_id)

    def snapshot(self):
        terminals = self.terminals.status()
        counts = self.store.counts()
        author_mcp = self.author_mcp.status()
        overall = (
            "READY"
            if terminals["powershell"]["online"]
            and terminals["cmd"]["online"]
            else "DEGRADED"
        )
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "overall": overall,
            "author_mcp": author_mcp,
            "api": {
                "online": self.api.running,
                "host": self.api.host,
                "port": self.api.port,
            },
            "terminals": terminals,
            "auto_execute": bool(self.auto_execute),
            "queue": counts,
            "executor": {
                "running": self.engine.running,
                "active_job_id": self.engine.active_job_id,
            },
        }

    def stop(self):
        if not self._started:
            return True

        try:
            self.author_mcp.stop()
        finally:
            try:
                self.api.stop()
            finally:
                try:
                    self.engine.stop(wait=True, timeout=5)
                finally:
                    try:
                        self.terminals.close()
                    finally:
                        pass

        self._started = False
        try:
            RUNTIME_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return True
