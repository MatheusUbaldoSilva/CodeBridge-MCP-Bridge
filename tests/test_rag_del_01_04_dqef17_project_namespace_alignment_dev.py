"""F17 source-of-truth project ID rule for DEV deletion review."""
from unittest import TestCase

from rag.runtime.isolated_project_index import PROJECT_ID_PATTERN
from rag.runtime.knowledge_deletion_selection_contract_dev import (
    review_explicit_deletion_paths_dev as review,
)
from rag.runtime.knowledge_deletion_preview_binding_dev import (
    review_deletion_preview_binding_dev,
)


class ProjectIdNamespaceAlignmentDevTests(TestCase):
    def test_valid_router_names_accepted_as_source_only(self):
        valid=("ab","demo","my_project","q2-v1","a"+("x"*63),"a0")
        for project in valid:
            with self.subTest(project=project):
                self.assertIsNotNone(PROJECT_ID_PATTERN.fullmatch(project))
                result=review(project,["docs/a.txt"])
                self.assertFalse(result["activation_authorized"])
                self.assertEqual(result["count"],1)

    def test_public_project_and_case_aliases_rejected(self):
        for name in ("codebridge","CodeBridge","CODEBRIDGE","Codebridge"):
            with self.subTest(project=name),self.assertRaises(ValueError):
                review(name,["a.txt"])

    def test_traversal_and_platform_separators_rejected(self):
        for name in (".","..","a/..","a/.","a/b","a\\b","a:b"):
            with self.subTest(project=name),self.assertRaises(ValueError):
                review(name,["a.txt"])

    def test_one_letter_and_too_long_names_rejected(self):
        for name in ("a","x"*65,"b"*129):
            with self.subTest(project=name),self.assertRaises(ValueError):
                review(name,["a.txt"])

    def test_undocumented_names_rejected(self):
        for name in ("1demo","-demo","_demo","my project","my.project",
                     "MY_PROJECT","caf?","x+y","x@a","a\t"):
            with self.subTest(project=name),self.assertRaises(ValueError):
                review(name,["a.txt"])

    def test_whitespace_and_control_names_rejected(self):
        for name in (" demo","demo ","\ndemo","demo\n","demo\x00"):
            with self.subTest(project=repr(name)),self.assertRaises(ValueError):
                review(name,["a.txt"])

    def test_invalid_inputs_remain_rejected(self):
        for name in (None,False,True,0,[],{},b"demo"):
            with self.subTest(type=type(name)),self.assertRaises(ValueError):
                review(name,["a.txt"])

    def test_accepted_namespace_matches_router_pattern(self):
        candidates=("abc","a9","a_b","a-b","abc23","codebridge-test",
                    "a"*64)
        for project in candidates:
            with self.subTest(project=project):
                self.assertIsNotNone(PROJECT_ID_PATTERN.fullmatch(project))
                self.assertEqual(review(project,["doc.txt"])["count"],1)

    def test_strict_namespace_carries_to_f16(self):
        for name in ("a","CODEBRIDGE","foo/bar","DEMO"):
            with self.subTest(project=name),self.assertRaises(ValueError):
                review_deletion_preview_binding_dev(name,["a.txt"],{})

    def test_valid_selection_receipt_project_sensitive(self):
        x=review("demo-a",["docs/one.md"])["selection_sha256"]
        y=review("demo-b",["docs/one.md"])["selection_sha256"]
        self.assertNotEqual(x,y)

    def test_source_router_pattern_not_mutated(self):
        before=PROJECT_ID_PATTERN.pattern
        review("demo",["a.txt"])
        self.assertEqual(PROJECT_ID_PATTERN.pattern,before)
        self.assertEqual(before,r"^[a-z][a-z0-9_-]{1,63}$")
