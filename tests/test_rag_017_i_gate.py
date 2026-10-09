"""RAG-017-I frozen threshold and live-index gate integrity."""
import json
from pathlib import Path
import unittest
B=Path(__file__).resolve().parents[1]/"benchmarks"
def read(name):
    return json.loads((B/name).read_text(encoding="utf-8"))

class GateTests(unittest.TestCase):
    def test_thresholds_unchanged(self):
        gate=read("rag017i_production_gate.json")
        frozen=read("rag014_readiness_report.json")["decision"]["thresholds"]
        names={
            "recall_at_5":"recall_at_5_min",
            "recall_at_10":"recall_at_10_min",
            "mrr":"mrr_min",
            "cold_latency_ms":"cold_latency_ms_max",
            "warm_p95_ms":"warm_p95_ms_max",
            "ram_peak_bytes":"ram_peak_bytes_max",
            "vram_delta_mib":"vram_delta_mib_max",
            "index_size_bytes":"index_size_bytes_max",
            "persistent_index_size_bytes":"index_size_bytes_max",
        }
        for name,threshold in names.items():
            self.assertEqual(gate["checks"][name]["limit"],frozen[threshold])
    def test_fail_closed_if_quality_below_floor(self):
        gate=read("rag017i_production_gate.json")
        failed=[k for k,v in gate["checks"].items() if not v["passed"]]
        self.assertEqual(set(failed),{"recall_at_5","recall_at_10","mrr"})
        self.assertEqual(gate["production_gate"],"BLOCKED")
        self.assertEqual(gate["persistent"]["state"],"READY")
    def test_benchmark_and_persistent_evidence_distinct(self):
        gate=read("rag017i_production_gate.json")
        replay=read("rag017f_semantic_latest.json")
        self.assertEqual(gate["checks"]["recall_at_5"]["measured"],replay["metrics"]["recall_at_5"])
        self.assertEqual(gate["persistent"]["documents"],210)
        self.assertEqual(gate["persistent"]["chunks"],8761)
        self.assertIn("temporary",str(gate["limitations"]))
