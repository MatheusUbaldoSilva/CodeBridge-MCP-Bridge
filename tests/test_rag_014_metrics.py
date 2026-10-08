import tempfile
import unittest
from pathlib import Path

from rag.benchmark.metrics import (
    capture_resource_snapshot,
    directory_size_bytes,
    evaluate_ranked_paths,
    measure_latency_ms,
)


class Rag014MetricsTests(unittest.TestCase):
    def test_recall_and_mrr(self):
        ranked = {
            "q1": ("a", "b", "c"),
            "q2": ("x", "y", "z"),
            "q3": ("m", "n", "o"),
        }
        expected = {
            "q1": ("b",),
            "q2": ("x",),
            "q3": ("missing",),
        }

        metrics = evaluate_ranked_paths(ranked, expected)

        self.assertEqual(metrics.query_count, 3)
        self.assertAlmostEqual(metrics.recall_at_5, 2 / 3)
        self.assertAlmostEqual(metrics.recall_at_10, 2 / 3)
        self.assertAlmostEqual(metrics.mrr, (0.5 + 1.0) / 3)

    def test_recall_at_5_and_10_differ(self):
        ranked = {"q": tuple(f"p{i}" for i in range(1, 11))}
        expected = {"q": ("p8",)}

        metrics = evaluate_ranked_paths(ranked, expected)

        self.assertEqual(metrics.recall_at_5, 0.0)
        self.assertEqual(metrics.recall_at_10, 1.0)
        self.assertAlmostEqual(metrics.mrr, 1 / 8)

    def test_query_id_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_ranked_paths({"q1": ("a",)}, {"q2": ("a",)})

    def test_directory_size(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.bin").write_bytes(b"1234")
            nested = root / "nested"
            nested.mkdir()
            (nested / "b.bin").write_bytes(b"123456")
            self.assertEqual(directory_size_bytes(root), 10)

    def test_missing_index_path_has_zero_size(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                directory_size_bytes(Path(td) / "missing"),
                0,
            )

    def test_resource_snapshot_has_ram_and_index_size(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "index.bin").write_bytes(b"x" * 32)

            snapshot = capture_resource_snapshot((root,))

            self.assertGreater(snapshot.ram_rss_bytes, 0)
            self.assertEqual(snapshot.index_size_bytes, 32)
            self.assertTrue(
                snapshot.vram_used_mib is None
                or snapshot.vram_used_mib >= 0
            )

    def test_latency_measurement_returns_samples(self):
        samples = measure_latency_ms(lambda: 1 + 1, repeat=3)
        self.assertEqual(len(samples), 3)
        self.assertTrue(all(sample >= 0.0 for sample in samples))

    def test_invalid_repeat_is_rejected(self):
        with self.assertRaises(ValueError):
            measure_latency_ms(lambda: None, repeat=0)


if __name__ == "__main__":
    unittest.main()
