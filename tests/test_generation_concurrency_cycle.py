"""Multi-process reading while generation activation and retirement compete."""
import multiprocessing as mp
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_activation import activate_test_generation, GenerationActivationError
from rag.runtime.generation_pointer import resolve_generation
from rag.runtime.generation_process_lock import GenerationBusy
from rag.runtime.generation_protected_session import (
    protected_generation_read, protected_generation_retirement,
)
from rag.runtime.generation_read_session import GenerationReadError
from test_generation_read_session import create_generation


def held_query(root, entered, release, results):
    try:
        with protected_generation_read(root) as session:
            entered.set()
            release.wait(8)
            db = session.open_sqlite()
            try:
                value = db.execute("SELECT generation FROM marker").fetchone()[0]
            finally:
                db.close()
            results.put((session.name, value))
    except BaseException as exc:
        results.put(("ERROR", str(exc)))
        entered.set()


class GenerationCycleTests(unittest.TestCase):
    def test_reader_stays_old_while_new_activates_and_retirement_waits(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "gen_one")
            create_generation(root, "gen_two")
            activate_test_generation(root, "gen_one")
            ctx = mp.get_context("spawn")
            entered, release = ctx.Event(), ctx.Event()
            results = ctx.Queue()
            reader = ctx.Process(target=held_query, args=(root, entered, release, results))
            reader.start()
            try:
                self.assertTrue(entered.wait(6), "reader did not start")
                activate_test_generation(root, "gen_two")
                self.assertEqual(resolve_generation(root).generation, "gen_two")
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root, "gen_one"):
                        pass
                with protected_generation_read(root) as new_session:
                    self.assertEqual(new_session.name, "gen_two")
                    db = new_session.open_sqlite()
                    try:
                        self.assertEqual(db.execute("SELECT generation FROM marker").fetchone()[0], "gen_two")
                    finally:
                        db.close()
            finally:
                release.set()
                reader.join(6)
                if reader.is_alive():
                    reader.terminate()
                    reader.join()
            self.assertEqual(reader.exitcode, 0)
            self.assertEqual(results.get(timeout=3), ("gen_one", "gen_one"))
            with protected_generation_retirement(root, "gen_one") as retired:
                self.assertTrue(retired.is_dir())
            self.assertTrue((root/"generations"/"gen_one").is_dir())

    def test_interruption_preserves_previous_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "gen_one")
            create_generation(root, "gen_two")
            activate_test_generation(root, "gen_one")
            with self.assertRaises(GenerationActivationError):
                activate_test_generation(root, "gen_two", fail_before_replace=True)
            self.assertEqual(resolve_generation(root).generation, "gen_one")
            self.assertFalse(list(root.glob(".active-generation.*.tmp")))


if __name__ == "__main__":
    unittest.main()
