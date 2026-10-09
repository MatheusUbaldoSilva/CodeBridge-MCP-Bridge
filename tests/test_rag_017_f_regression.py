"""RAG-017-F full-dataset independent metric and gate integrity."""
from pathlib import Path
import json
import unittest
from rag.benchmark.metrics import evaluate_ranked_paths

B=Path(__file__).resolve().parents[1]/"benchmarks"

def jsonl(path):
    return [json.loads(x) for x in (B/path).read_text(encoding="utf-8").splitlines() if x.strip()]

class Rag017FRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate=json.loads((B/"rag017f_regression_gate.json").read_text(encoding="utf-8"))
        cls.latest=json.loads((B/"rag017f_semantic_latest.json").read_text(encoding="utf-8"))
        cls.reference=json.loads((B/"rag014_readiness_report.json").read_text(encoding="utf-8"))
    def test_frozen_100_queries_have_ground_truth(self):
        queries=jsonl("rag014_dataset.jsonl")
        ground=jsonl("rag014_ground_truth.jsonl")
        self.assertEqual(len(queries),100)
        self.assertEqual({x["id"] for x in queries},{x["id"] for x in ground})
        self.assertEqual(set(self.latest["top10_paths"]),{x["id"] for x in ground})
        self.assertTrue(all(x["expected_paths"] for x in ground))
    def test_independent_metric_reconstruction(self):
        truth={x["id"]:x["expected_paths"] for x in jsonl("rag014_ground_truth.jsonl")}
        result=evaluate_ranked_paths(self.latest["top10_paths"],truth)
        for key,val in result.to_dict().items():
            self.assertAlmostEqual(float(val),float(self.gate["metrics"][key]),places=10)
    def test_thresholds_unchanged_from_frozen_reference(self):
        current=self.gate["thresholds"]
        old=self.reference["decision"]["thresholds"]
        for k in ("recall_at_5","recall_at_10","mrr"):
            self.assertEqual(current[f"{k}_min"],old[f"{k}_min"])
            self.assertEqual(self.gate["qualifiers"][k],self.gate["metrics"][k]>=current[f"{k}_min"])
    def test_no_false_production_ready_claim(self):
        if not all(self.gate["qualifiers"].values()):
            self.assertEqual(self.gate["quality_gate"],"BLOCKED")
            self.assertEqual(self.gate["production_gate"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
