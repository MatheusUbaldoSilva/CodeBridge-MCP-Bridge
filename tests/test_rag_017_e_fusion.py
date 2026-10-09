"""RAG-017-E fusion and dedup evidence invariants."""
import json
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]/"benchmarks"

class Rag017EFusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads((BASE/"rag017e_fusion_ablation.json").read_text(encoding="utf-8"))
    def test_all_frozen_queries_covered(self):
        rows=self.report["queries"]
        self.assertEqual(len(rows),100)
        self.assertEqual(len({r["id"] for r in rows}),100)
    def test_diversity_counts_are_derived_from_paths(self):
        for r in self.report["queries"]:
            self.assertEqual(r["duplicated_path_slots"],len(r["rrf_top10"])-len(set(r["rrf_top10"])))
            distinct=list(dict.fromkeys(r["rrf_top10"]))
            exp=set(r["expected"])
            self.assertEqual(r["diversified_hit5"],bool(exp.intersection(distinct[:5])))
            self.assertEqual(r["diversified_hit10"],bool(exp.intersection(distinct[:10])))
    def test_aggregation_consistent(self):
        stats=self.report["statistics"]
        rows=self.report["queries"]
        self.assertEqual(stats["queries"],len(rows))
        for field in ("rrf_hit5","rrf_hit10","final_hit5","final_hit10","offline_unique_path_hit5","offline_unique_path_hit10","dedup_dropped_expected"):
            row_field={"final_hit5":"baseline_hit5","final_hit10":"baseline_hit10","offline_unique_path_hit5":"diversified_hit5","offline_unique_path_hit10":"diversified_hit10"}.get(field,field)
            self.assertEqual(stats[field],sum(r[row_field] for r in rows))
        self.assertAlmostEqual(stats["mean_duplicate_path_slots"],sum(r["duplicated_path_slots"] for r in rows)/len(rows))

if __name__=="__main__":
    unittest.main()
