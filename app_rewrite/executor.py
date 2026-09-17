import threading
import time


class ExecutionEngine:
    def __init__(self, store, terminals, poll_interval=0.10, preview_seconds=0.35):
        self.store = store
        self.terminals = terminals
        self.poll_interval = float(poll_interval)
        self.preview_seconds = float(preview_seconds)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._lock = threading.RLock()
        self._active_job_id = None
        self._cancel_requested = set()

    @property
    def active_job_id(self):
        with self._lock:
            return self._active_job_id

    @property
    def running(self):
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def start(self):
        if self.running:
            return False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="CodeBridgeMCPExecutor", daemon=True
        )
        self._thread.start()
        return True

    def wake(self):
        self._wake.set()
    def stop(self, wait=True, timeout=5):
        self._stop.set()
        self._wake.set()
        try:
            self.terminals.cancel_active()
        except Exception:
            pass
        thread = self._thread
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        return not self.running

    def cancel(self, job_id=None):
        active = self.active_job_id
        if active is not None and (job_id is None or job_id == active):
            with self._lock:
                self._cancel_requested.add(active)
            return bool(self.terminals.cancel_active())
        if job_id is None:
            return False
        return self.store.cancel_pending(job_id)

    def _is_cancel_requested(self, job_id):
        with self._lock:
            return job_id in self._cancel_requested

    def _clear_cancel(self, job_id):
        with self._lock:
            self._cancel_requested.discard(job_id)

    def _loop(self):
        while not self._stop.is_set():
            job = self.store.claim_next()
            if job is None:
                self._wake.wait(self.poll_interval)
                self._wake.clear()
                continue
            self._run_job(job)
        with self._lock:
            self._thread = None
    def _run_job(self, job):
        job_id = job["id"]
        target = job["target"]
        command = job["command"]
        with self._lock:
            self._active_job_id = job_id
        prepared_at = None
        try:
            self.terminals.prepare(target, command)
            prepared_at = time.monotonic()
            self.store.mark_prepared(job_id)
            self.store.wait_for_field(job_id, "prepared_visible_at", timeout=1.0)

            remaining = self.preview_seconds - (time.monotonic() - prepared_at)
            if remaining > 0:
                time.sleep(remaining)

            if self._is_cancel_requested(job_id):
                self.store.finish(job_id, "CANCELLED", exit_code=130)
                self.terminals.announce(target, "[CANCELLED] antes do Enter")
                return

            self.store.mark_running(job_id)
            output = self.terminals.execute_prepared(target, command)
            self.store.finish(job_id, "SUCCESS", output=output, exit_code=0)
            self.terminals.announce(target, "[SUCCESS] exit_code=0")
        except Exception as exc:
            output = getattr(exc, "output", "") or ""
            exit_code = getattr(exc, "exit_code", None)
            name = type(exc).__name__
            lowered = name.lower()
            if self._is_cancel_requested(job_id) or "cancel" in lowered:
                state = "CANCELLED"
                if exit_code is None:
                    exit_code = 130
            elif "interrupt" in lowered:
                state = "INTERRUPTED"
            else:
                state = "FAILED"
            try:
                self.store.finish(
                    job_id, state, output=output, exit_code=exit_code,
                    error_type=name, error_message=str(exc),
                )
            except Exception:
                pass
            self.terminals.announce(target, f"[{state}] {name}: {exc}")
        finally:
            if prepared_at is not None and self.terminals.status().get("prepared_target"):
                try:
                    self.terminals.discard_prepared()
                except Exception:
                    pass
            self._clear_cancel(job_id)
            with self._lock:
                self._active_job_id = None
            time.sleep(0)
