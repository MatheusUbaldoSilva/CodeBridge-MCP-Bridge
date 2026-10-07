import unittest

from rag.contracts import SourceType
from rag.runtime.query_classifier import QueryRoute, classify_query


class RagQueryClassifierTests(unittest.TestCase):
    def test_exact_symbol_is_lexical_only(self):
        result = classify_query("GetMoveSpeedProvenance")
        self.assertEqual(result.route, QueryRoute.LEXICAL_ONLY)

    def test_commit_hash_is_lexical_only(self):
        result = classify_query("34f2b53")
        self.assertEqual(result.route, QueryRoute.LEXICAL_ONLY)

    def test_code_path_is_lexical_only(self):
        result = classify_query("rag/models/code_embedding.py")
        self.assertEqual(result.route, QueryRoute.LEXICAL_ONLY)

    def test_natural_language_code_question_routes_code(self):
        result = classify_query("onde controla cancelamento do runtime")
        self.assertEqual(result.route, QueryRoute.CODE)

    def test_code_snippet_routes_code(self):
        result = classify_query("def cancel_current(self):\n    self.send_ctrl_c()")
        self.assertEqual(result.route, QueryRoute.CODE)

    def test_documentation_question_routes_text(self):
        result = classify_query("o que o handoff diz sobre memória")
        self.assertEqual(result.route, QueryRoute.TEXT)

    def test_mixed_code_and_docs_routes_hybrid(self):
        result = classify_query("onde o código implementa o que está no handoff")
        self.assertEqual(result.route, QueryRoute.HYBRID)

    def test_code_source_scope_routes_code(self):
        result = classify_query("cancelamento", source_types=(SourceType.CODE,))
        self.assertEqual(result.route, QueryRoute.CODE)

    def test_mixed_source_scope_routes_hybrid(self):
        result = classify_query(
            "cancelamento",
            source_types=(SourceType.CODE, SourceType.DOCUMENTATION),
        )
        self.assertEqual(result.route, QueryRoute.HYBRID)

    def test_text_source_scope_routes_text(self):
        result = classify_query(
            "cancelamento",
            source_types=(SourceType.AUDIT, SourceType.LOG),
        )
        self.assertEqual(result.route, QueryRoute.TEXT)

    def test_default_is_text(self):
        result = classify_query("como funciona o projeto")
        self.assertEqual(result.route, QueryRoute.TEXT)
        self.assertEqual(result.reasons, ("default_text",))

    def test_blank_query_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_query("   ")

    def test_invalid_source_type_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_query("query", source_types=("CODE",))


if __name__ == "__main__":
    unittest.main()
