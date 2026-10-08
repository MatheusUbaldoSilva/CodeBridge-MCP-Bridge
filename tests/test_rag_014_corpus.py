import tempfile
import unittest
from pathlib import Path

from rag.benchmark.corpus import (
    build_lexical_benchmark_index,
    lexical_ranked_paths,
)
from rag.index.sqlite_schema import connect_rag_index


class Rag014BenchmarkCorpusTests(unittest.TestCase):
    def test_builds_real_fts5_corpus_with_production_chunkers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            docs = root / "docs"
            src = root / "src"
            docs.mkdir()
            src.mkdir()

            (docs / "guide.md").write_text(
                "# Guide\n\nunique benchmark phrase for retrieval\n",
                encoding="utf-8",
            )
            (src / "main.py").write_text(
                "def benchmark_symbol():\n"
                "    return 'code benchmark token'\n",
                encoding="utf-8",
            )

            db = root / "rag.sqlite3"
            stats = build_lexical_benchmark_index(
                root,
                db,
                paths=("docs", "src"),
            )

            self.assertEqual(stats.documents, 2)
            self.assertGreaterEqual(stats.chunks, 2)
            self.assertTrue(db.is_file())

            connection = connect_rag_index(db)
            try:
                paths = lexical_ranked_paths(
                    connection,
                    "unique benchmark phrase",
                    top_k=10,
                )
            finally:
                connection.close()

            self.assertIn("docs/guide.md", paths)

    def test_code_file_is_indexed_with_code_chunker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "worker.py").write_text(
                "def exact_worker_phrase():\n"
                "    return 'worker'\n",
                encoding="utf-8",
            )
            db = root / "rag.sqlite3"

            stats = build_lexical_benchmark_index(
                root,
                db,
                paths=("src",),
            )
            self.assertEqual(stats.documents, 1)

            connection = connect_rag_index(db)
            try:
                paths = lexical_ranked_paths(
                    connection,
                    "exact_worker_phrase",
                    top_k=10,
                )
            finally:
                connection.close()

            self.assertEqual(paths, ("src/worker.py",))


if __name__ == "__main__":
    unittest.main()
