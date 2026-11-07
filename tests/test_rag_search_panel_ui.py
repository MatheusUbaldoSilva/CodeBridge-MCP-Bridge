import os
import sys
from pathlib import Path
from unittest import TestCase

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
from PySide6.QtWidgets import QApplication  # noqa: E402
import rag_search_panel as module  # noqa: E402


def hit(path, kind, content, start=1, score=0.016, modes=("lexical", "vector"), stale=False):
    return {"content": content, "score": score, "retrieval_modes": list(modes), "stale": stale,
            "source_verification": {"status": "FRESH", "reason": "SHA_MATCH"},
            "metadata": {"path": path, "source_type": kind, "line_start": start,
                         "line_end": start + content.count("\n")}}


RESULTS = [
    hit("rag/runtime/undo.py", "CODE", "def rollback(tx):\n    # desfaz a exclusao\n    return tx", 10, 0.0164),
    hit("docs/README.md", "DOCUMENTATION", "Como desfazer uma exclusao\nUse o botao Desfazer.", 3, 0.0161),
    hit("rag/runtime/undo.py", "CODE", "def undo_all():\n    pass", 40, 0.0150),
]


class FakeSearch:
    def __init__(self, data=None, error=None):
        self.calls = []
        self.data = data if data is not None else {"results": RESULTS, "result_count": 3}
        self.error = error

    def __call__(self, query, project_id, top_k):
        self.calls.append((query, project_id, top_k))
        if self.error:
            raise RuntimeError(self.error)
        return self.data


class InlinePanel(module.KnowledgeSearchPanel):
    def _start(self, worker):
        worker()
        self._drain()


class SearchHelpersTest(TestCase):
    def test_terms_skip_short_and_stop_words(self):
        self.assertEqual(module.query_terms("como desfazer a exclusao do README.md"),
                         ["desfazer", "exclusao", "readme.md"])

    def test_mark_html_escapes_and_highlights(self):
        out = module.mark_html("<b>Desfazer</b> & ok", ["desfazer"])
        self.assertIn("&lt;b&gt;", out)
        self.assertIn(">Desfazer</span>", out)
        self.assertIn("&amp;", out)

    def test_snippet_starts_near_first_match(self):
        text = "a1\nb2\nc3\nachei aqui\nd4\ne5"
        self.assertEqual(module.snippet_lines(text, ["achei"]), ["c3", "achei aqui", "d4"])

    def test_group_by_file_keeps_rank_order(self):
        groups = module.group_hits(RESULTS)
        self.assertEqual([g["path"] for g in groups], ["rag/runtime/undo.py", "docs/README.md"])
        self.assertEqual([r for r, _ in groups[0]["hits"]], [1, 3])
        self.assertEqual(groups[0]["kind"], "CODE")
        self.assertEqual(groups[1]["kind"], "DOC")

    def test_labels(self):
        self.assertEqual(module.modes_label(RESULTS[0]), "palavras + significado")
        self.assertEqual(module.modes_label({"retrieval_modes": ["lexical"]}), "por palavras")
        self.assertEqual(module.modes_label({"retrieval_modes": ["VECTOR_TEXT_COSINE"]}), "por significado")
        self.assertEqual(module.modes_label({"retrieval_modes": ["LEXICAL_FTS5_BM25"]}), "por palavras")
        self.assertTrue(module.lines_label(RESULTS[0]).startswith("linhas 10"))
        self.assertEqual(module.split_path("a\\b\\c.py"), ("c.py", "a/b"))


class SearchPanelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make(self, search=None):
        search = search or FakeSearch()
        panel = InlinePanel(search_fn=search)
        panel.set_project("proj")
        return panel, search

    def test_empty_state_names_selected_project(self):
        panel, _ = self.make()
        self.assertTrue(panel.empty.isVisibleTo(panel))
        self.assertIn("proj", panel.empty.text())
        self.assertIn("Enter", panel.empty.text())

    def test_search_groups_cards_and_previews_first(self):
        panel, search = self.make()
        panel.query.setText("desfazer exclusao")
        self.assertTrue(panel.search())
        self.assertEqual(search.calls, [("desfazer exclusao", "proj", module.TOP_K)])
        self.assertEqual(len(panel.cards), 2)
        self.assertEqual(panel.cards[0].count.text(), "2 trechos")
        self.assertIs(panel.selected, panel.cards[0])
        html = panel.preview.toHtml()
        self.assertIn("rollback", html)
        self.assertIn("undo_all", html)
        self.assertIn(">40<", html.replace(" ", ""))
        self.assertIn("3 trechos em 2 arquivos", panel.summary.text())
        self.assertEqual(panel.filter_buttons["ALL"].text(), "Tudo (2)")

    def test_filter_and_selection(self):
        panel, _ = self.make()
        panel.search("desfazer")
        panel.set_filter("DOC")
        self.assertEqual([c.group["path"] for c in panel.cards], ["docs/README.md"])
        panel.set_filter("CODE")
        self.assertEqual(len(panel.cards), 1)
        panel.set_filter("ALL")
        panel._select(panel.cards[1])
        self.assertEqual(panel.preview_path.text(), "docs/README.md")
        self.assertIn("Use o botao Desfazer.", panel.selected_text())
        self.assertEqual(panel.copy_path(), "docs/README.md")

    def test_no_results_and_fallback_notice(self):
        panel, _ = self.make(FakeSearch({"results": [], "fallback_reason": "VECTOR_OFF"}))
        panel.search("inexistente")
        self.assertEqual(panel.cards, [])
        self.assertIn("Nada encontrado", panel.empty.text())
        self.assertTrue(panel.notice.isVisibleTo(panel))
        self.assertIn("palavras", panel.notice.text())

    def test_error_is_shown_and_button_released(self):
        panel, _ = self.make(FakeSearch(error="falhou feio"))
        panel.search("x y z")
        self.assertIn("falhou feio", panel.notice.text())
        self.assertTrue(panel.search_button.isEnabled())

    def test_stale_result_from_old_project_is_ignored(self):
        panel = module.KnowledgeSearchPanel(search_fn=FakeSearch())
        jobs = []
        panel._start = jobs.append
        panel.set_project("proj")
        panel.search("desfazer")
        panel.set_project("outro")
        jobs[0]()
        panel._drain()
        self.assertEqual(panel.cards, [])
        self.assertTrue(panel.search_button.isEnabled())

    def test_no_project_does_not_search(self):
        search = FakeSearch()
        panel = InlinePanel(search_fn=search)
        self.assertFalse(panel.search("algo"))
        self.assertEqual(search.calls, [])