import multiprocessing as mp
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy


def held_reader(root, ready, release):
    with generation_lock(root, "gen_001"):
        ready.set()
        release.wait(8)


def crashing_reader(root, ready):
    with generation_lock(root, "gen_001"):
        ready.set()
        os._exit(29)


class ProcessLockTests(unittest.TestCase):
    def test_another_process_blocks_retirement_then_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            context = mp.get_context("spawn")
            ready, release = context.Event(), context.Event()
            worker = context.Process(target=held_reader, args=(root, ready, release))
            worker.start()
            try:
                self.assertTrue(ready.wait(6))
                with self.assertRaises(GenerationBusy):
                    with generation_lock(root, "gen_001", exclusive=True):
                        pass
            finally:
                release.set()
                worker.join(timeout=6)
                if worker.is_alive():
                    worker.terminate()
                    worker.join()
            self.assertEqual(worker.exitcode, 0)
            with generation_lock(root, "gen_001", exclusive=True):
                pass

    def test_lock_released_after_process_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            context = mp.get_context("spawn")
            ready = context.Event()
            worker = context.Process(target=crashing_reader, args=(root, ready))
            worker.start()
            try:
                self.assertTrue(ready.wait(6))
                worker.join(timeout=6)
                self.assertEqual(worker.exitcode, 29)
                with generation_lock(root, "gen_001", exclusive=True):
                    pass
            finally:
                if worker.is_alive():
                    worker.terminate()
                    worker.join()

    def test_rejects_other_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                with generation_lock(tmp, "gen_001"):
                    pass

if __name__ == "__main__":
    unittest.main()
