import unittest

from rag.benchmark.gate import (
    GIB,
    RagGoLiveObservation,
    RagGoLiveThresholds,
    evaluate_go_live,
)


class Rag014GoLiveGateTests(unittest.TestCase):
    def test_default_thresholds_are_frozen(self):
        thresholds = RagGoLiveThresholds()
        self.assertEqual(thresholds.recall_at_5_min, 0.80)
        self.assertEqual(thresholds.recall_at_10_min, 0.90)
        self.assertEqual(thresholds.mrr_min, 0.60)
        self.assertEqual(thresholds.cold_latency_ms_max, 20_000.0)
        self.assertEqual(thresholds.warm_p95_ms_max, 1_000.0)
        self.assertEqual(thresholds.ram_peak_bytes_max, 6 * GIB)
        self.assertEqual(thresholds.vram_delta_mib_max, 5_120)
        self.assertEqual(thresholds.index_size_bytes_max, 2 * GIB)

    def passing_observation(self):
        return RagGoLiveObservation(
            production_index_ready=True,
            semantic_metrics_available=True,
            recall_at_5=0.90,
            recall_at_10=0.95,
            mrr=0.75,
            cold_latency_ms=8_000,
            warm_p95_ms=500,
            ram_peak_bytes=4 * GIB,
            vram_delta_mib=3_000,
            index_size_bytes=500 * 1024 * 1024,
        )

    def test_good_observation_passes(self):
        decision = evaluate_go_live(self.passing_observation())
        self.assertTrue(decision.passed)
        self.assertEqual(decision.failed_checks, ())

    def test_missing_semantic_metrics_blocks_release(self):
        decision = evaluate_go_live(
            RagGoLiveObservation(
                production_index_ready=False,
                semantic_metrics_available=False,
            )
        )
        self.assertFalse(decision.passed)
        self.assertIn(
            "production_index:NOT_READY",
            decision.failed_checks,
        )
        self.assertIn(
            "semantic_metrics:NOT_AVAILABLE",
            decision.failed_checks,
        )
        self.assertIn(
            "recall_at_5:NOT_MEASURED",
            decision.failed_checks,
        )

    def test_quality_below_threshold_blocks_release(self):
        observation = self.passing_observation()
        observation = RagGoLiveObservation(
            **{
                **observation.__dict__,
                "recall_at_5": 0.79,
                "recall_at_10": 0.89,
                "mrr": 0.59,
            }
        )
        decision = evaluate_go_live(observation)
        self.assertFalse(decision.passed)
        self.assertTrue(
            any(item.startswith("recall_at_5:BELOW_THRESHOLD") for item in decision.failed_checks)
        )
        self.assertTrue(
            any(item.startswith("recall_at_10:BELOW_THRESHOLD") for item in decision.failed_checks)
        )
        self.assertTrue(
            any(item.startswith("mrr:BELOW_THRESHOLD") for item in decision.failed_checks)
        )

    def test_resource_or_latency_over_threshold_blocks_release(self):
        observation = self.passing_observation()
        observation = RagGoLiveObservation(
            **{
                **observation.__dict__,
                "cold_latency_ms": 20_001,
                "warm_p95_ms": 1_001,
                "ram_peak_bytes": 6 * GIB + 1,
                "vram_delta_mib": 5_121,
                "index_size_bytes": 2 * GIB + 1,
            }
        )
        decision = evaluate_go_live(observation)
        self.assertFalse(decision.passed)
        for prefix in (
            "cold_latency_ms:ABOVE_THRESHOLD",
            "warm_p95_ms:ABOVE_THRESHOLD",
            "ram_peak_bytes:ABOVE_THRESHOLD",
            "vram_delta_mib:ABOVE_THRESHOLD",
            "index_size_bytes:ABOVE_THRESHOLD",
        ):
            self.assertTrue(
                any(item.startswith(prefix) for item in decision.failed_checks)
            )


if __name__ == "__main__":
    unittest.main()
