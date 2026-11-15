"""Agendador que sincroniza em segundo plano os pares marcados como auto.

Uma thread daemon acorda a cada interval_sec (padrao 60s) e chama run_due() do
project_sync, que so sincroniza os pares cujo intervalo (ex.: 10 min) ja passou.
Nunca deixa excecao escapar do loop: erros sao registrados e o ciclo continua.
O app liga isto no boot (BridgeRuntime.start) e desliga no stop.
"""
import threading


def _default_run_due():
    import project_sync
    return project_sync.run_due()


class SyncScheduler:
    def __init__(self, run_due=None, interval_sec=60, log=None):
        self._run_due = run_due or _default_run_due
        self._interval = max(5, int(interval_sec or 60))
        self._stop = threading.Event()
        self._thread = None
        self._log = log or (lambda *a: None)

    def is_running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="codebridge-sync-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout=3):
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout)
        self._thread = None

    def tick(self):
        """Uma passada: sincroniza os pares due. Nunca levanta."""
        try:
            res = self._run_due()
            if res:
                self._log("sync automatico:", res)
            return res
        except Exception as exc:
            self._log("sync scheduler erro:", exc)
            return None

    def _loop(self):
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self._interval)
