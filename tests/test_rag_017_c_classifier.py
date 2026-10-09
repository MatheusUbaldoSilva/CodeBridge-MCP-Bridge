"""RAG-017-C general classification regression."""
import json
from pathlib import Path
import unittest
from rag.runtime.query_classifier import QueryRoute, classify_query
from rag.contracts import SourceType

class TestRag017CClassifier(unittest.TestCase):
    def test_brand_substring_not_a_code_hint(self):
        self.assertEqual(classify_query("Why was CodeBridge chosen as desktop platform").route,QueryRoute.TEXT)
    def test_code_implementation_question(self):
        self.assertEqual(classify_query("How is the rank fusion implemented for retriever").route,QueryRoute.CODE)
    def test_portuguese_implementation_question(self):
        self.assertEqual(classify_query("onde verifica se arquivo mudou depois da indexacao").route,QueryRoute.CODE)
    def test_documentation_remains_text(self):
        self.assertEqual(classify_query("What does the roadmap document about deployment").route,QueryRoute.TEXT)
    def test_mixed_source_scope_still_wins(self):
        self.assertEqual(classify_query("Where is the retriever",source_types=(SourceType.CODE,SourceType.DOCUMENTATION)).route,QueryRoute.HYBRID)
    def test_exact_path_is_still_lexical(self):
        self.assertEqual(classify_query("rag/runtime/query_classifier.py").route,QueryRoute.LEXICAL_ONLY)
    def test_route_audit_covers_dataset(self):
        path=Path(__file__).resolve().parents[1]/"benchmarks"/"rag017c_route_audit.json"
        report=json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(report["queries"]),100)
        self.assertEqual(report["route_changes"],sum(x["changed"] for x in report["queries"]))
        self.assertEqual(sum(report["route_counts_after"].values()),100)
if __name__=="__main__":unittest.main()
