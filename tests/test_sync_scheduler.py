"""Testes do SyncScheduler (tick + ciclo de vida), sem depender do app."""
import os
import sys
import threading
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.join(_ROOT, "app_rewrite")
if _APP not in sys.path:
    sys.path.insert(0, _APP)

from sync_scheduler import SyncScheduler


class SyncSchedulerTest(unittest.TestCase):
    def test_tick_chama_run_due(self):
        chamadas = []

        def run():
            chamadas.append(1)
            return [{"id": "sync1", "added": 2}]

        s = SyncScheduler(run_due=run)
        r = s.tick()
        self.assertEqual(chamadas, [1])
        self.assertEqual(r, [{"id": "sync1", "added": 2}])

    def test_tick_engole_excecao(self):
        def boom():
            raise RuntimeError("falhou")

        s = SyncScheduler(run_due=boom)
        self.assertIsNone(s.tick())

    def test_start_roda_e_stop_encerra(self):
        ev = threading.Event()

        def run():
            ev.set()
            return []

        s = SyncScheduler(run_due=run, interval_sec=5)
        s.start()
        try:
            self.assertTrue(ev.wait(2), "tick nao rodou")
            self.assertTrue(s.is_running())
        finally:
            s.stop()
        self.assertFalse(s.is_running())


if __name__ == "__main__":
    unittest.main()