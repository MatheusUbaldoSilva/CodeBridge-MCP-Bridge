import tempfile
import unittest
from pathlib import Path

from rag.benchmark.restart import (
    RESTART_BASELINE_FILENAME,
    prepare_restart_probe,
    verify_restart_probe,
)


class Rag016RestartProbeTests(unittest.TestCase):
    def test_prepare_and_verify_persist_across_fresh_open(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "project"
            docs = project / "docs"
            src = project / "src"
            docs.mkdir(parents=True)
            src.mkdir(parents=True)

            (docs / "restart.md").write_text(
                "# Restart\n\npersistent restart marker documentation\n",
                encoding="utf-8",
            )
            (src / "restart.py").write_text(
                "def restart_probe():\n"
                "    return 'persistent restart marker code'\n",
                encoding="utf-8",
            )
            state = base / "state"

            prepared = prepare_restart_probe(
                project,
                state,
                paths=("docs", "src"),
            )
            verified = verify_restart_probe(state)

            self.assertEqual(verified, prepared)
            self.assertTrue((state / RESTART_BASELINE_FILENAME).is_file())
            self.assertTrue((state / "restart.sqlite3").is_file())
            self.assertTrue((state / "qdrant").is_dir())
            self.assertEqual(prepared.text_vector_points, 1)
            self.assertEqual(prepared.code_vector_points, 1)
            self.assertTrue(prepared.signature)

    def test_verify_fails_when_baseline_is_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                verify_restart_probe(Path(td))


if __name__ == "__main__":
    unittest.main()
