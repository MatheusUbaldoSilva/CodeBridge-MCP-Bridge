import multiprocessing as mp
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_process_lock import generation_lock, GenerationBusy

def reader(root, ready, release):
    with generation_lock(root, "one"):
        ready.set()
        release.wait(5)

class SharedLockTests(unittest.TestCase):
    def test_two_processes_read_concurrently(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "codebridge-rag-generation-test"
            root.mkdir()
            ctx = mp.get_context("spawn")
            ready = [ctx.Event(), ctx.Event()]
            release = ctx.Event()
            workers = [ctx.Process(target=reader, args=(root, ready[i], release)) for i in range(2)]
            for worker in workers:
                worker.start()
            try:
                self.assertTrue(all(event.wait(3) for event in ready))
                with self.assertRaises(GenerationBusy):
                    with generation_lock(root, "one", exclusive=True):
                        pass
            finally:
                release.set()
                for worker in workers:
                    worker.join(4)
                    if worker.is_alive():
                        worker.terminate()
                        worker.join()
            self.assertEqual([worker.exitcode for worker in workers], [0, 0])
            with generation_lock(root, "one", exclusive=True):
                pass

if __name__ == "__main__":
    unittest.main()
