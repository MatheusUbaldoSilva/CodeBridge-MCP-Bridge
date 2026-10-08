import tempfile
import unittest
from pathlib import Path

from rag.benchmark.soak import run_storage_retrieval_soak


class Rag016SoakTests(unittest.TestCase):
    def test_repeated_index_and_query_cycles_are_stable(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / "project"
            docs = project / "docs"
            src = project / "src"
            docs.mkdir(parents=True)
            src.mkdir(parents=True)

            document = docs / "guide.md"
            code = src / "worker.py"
            document.write_text(
                "# Soak Guide\n\n"
                "stable soak marker documentation\n",
                encoding="utf-8",
            )
            code.write_text(
                "def soak_worker():\n"
                "    return 'stable soak marker code'\n",
                encoding="utf-8",
            )
            document_before = document.read_bytes()
            code_before = code.read_bytes()

            result = run_storage_retrieval_soak(
                project,
                index_cycles=3,
                query_cycles=25,
                paths=("docs", "src"),
                working_directory=base / "index",
            )

            self.assertEqual(result.index_cycles, 3)
            self.assertEqual(result.query_cycles, 25)
            self.assertEqual(result.documents, 2)
            self.assertGreaterEqual(result.chunks, 2)
            self.assertEqual(result.text_vector_points, 1)
            self.assertEqual(result.code_vector_points, 1)
            self.assertTrue(result.stable_signature)
            self.assertGreater(result.sqlite_size_bytes, 0)
            self.assertGreater(result.qdrant_size_bytes, 0)
            self.assertGreater(result.total_index_size_bytes, 0)
            self.assertGreaterEqual(result.elapsed_seconds, 0.0)
            self.assertEqual(document.read_bytes(), document_before)
            self.assertEqual(code.read_bytes(), code_before)

    def test_invalid_cycle_counts_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            with self.assertRaises(ValueError):
                run_storage_retrieval_soak(
                    project,
                    index_cycles=0,
                    query_cycles=1,
                )
            with self.assertRaises(ValueError):
                run_storage_retrieval_soak(
                    project,
                    index_cycles=1,
                    query_cycles=0,
                )


if __name__ == "__main__":
    unittest.main()
