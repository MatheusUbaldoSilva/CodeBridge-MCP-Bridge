from unittest import TestCase
from unittest.mock import patch
from rag.runtime.knowledge_deletion_review import build_deletion_review,DeletionReviewError

class ReviewTests(TestCase):
    def base(self):
        return {"project_id":"demo","generation":"old","source_revision":"a"*64,
            "selected_paths":["a.cpp"],"documents_to_remove":1,
            "chunks_to_remove":2,"documents_to_preserve":3,
            "review_sha256":"b"*64,"deletion_authorized":False,
            "candidate_created":False,"public_pointer_updated":False}
    @patch("rag.runtime.knowledge_deletion_review.preview_knowledge_removal")
    def test_builds_review_without_removing(self, api):
        api.return_value=self.base()
        result=build_deletion_review("demo",["a.cpp"])
        self.assertFalse(result["execution_enabled"])
        self.assertFalse(result["source_files_modified"])
        self.assertIn("SIMULAÇÃO",result["display_text"])
        api.assert_called_once_with("demo",["a.cpp"])
    @patch("rag.runtime.knowledge_deletion_review.preview_knowledge_removal")
    def test_public_rejected_without_call(self, api):
        with self.assertRaises(DeletionReviewError):
            build_deletion_review("codebridge",["a.cpp"])
        api.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_review.preview_knowledge_removal")
    def test_duplicates_rejected(self, api):
        with self.assertRaises(DeletionReviewError):
            build_deletion_review("demo",["a.cpp","a.cpp"])
        api.assert_not_called()
    @patch("rag.runtime.knowledge_deletion_review.preview_knowledge_removal")
    def test_invalid_preview_rejected(self, api):
        item=self.base();item["deletion_authorized"]=True
        api.return_value=item
        with self.assertRaises(DeletionReviewError):
            build_deletion_review("demo",["a.cpp"])
    @patch("rag.runtime.knowledge_deletion_review.preview_knowledge_removal")
    def test_selection_mismatch_rejected(self, api):
        item=self.base();item["selected_paths"]=["other.cpp"]
        api.return_value=item
        with self.assertRaises(DeletionReviewError):
            build_deletion_review("demo",["a.cpp"])
