import tempfile
import unittest
from pathlib import Path

from rag.runtime.index_request import (
    RagIndexAction,
    RagIndexExecutionUnavailableError,
    RagIndexScope,
    plan_rag_index,
    run_explicit_rag_index,
)


class RagIndexRequestTests(unittest.TestCase):
    def make_project(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "project"
        root.mkdir()
        (root / "README.md").write_text("# Project\n", encoding="utf-8")
        src = root / "src"
        src.mkdir()
        (src / "main.py").write_text("print('x')\n", encoding="utf-8")
        (root / "notes.bin").write_bytes(b"binary")
        (root / ".env").write_text("SECRET=x\n", encoding="utf-8")
        (root / "image.png").write_bytes(b"not-an-image")
        return root

    def test_plan_both_discovers_text_and_code_without_denied_paths(self):
        root = self.make_project()

        plan = plan_rag_index(
            "codebridge",
            root,
            scope=RagIndexScope.BOTH,
        )

        by_path = {item.path: item for item in plan.candidates}
        self.assertIn("README.md", by_path)
        self.assertTrue(by_path["README.md"].text_eligible)
        self.assertFalse(by_path["README.md"].code_eligible)
        self.assertIn("src/main.py", by_path)
        self.assertTrue(by_path["src/main.py"].code_eligible)
        self.assertNotIn(".env", by_path)
        self.assertNotIn("image.png", by_path)
        self.assertGreaterEqual(plan.denied_count, 2)

    def test_text_scope_excludes_code_only_file(self):
        root = self.make_project()
        plan = plan_rag_index(
            "codebridge",
            root,
            scope=RagIndexScope.TEXT,
        )
        self.assertEqual(
            [item.path for item in plan.candidates],
            ["README.md"],
        )

    def test_code_scope_excludes_document_only_file(self):
        root = self.make_project()
        plan = plan_rag_index(
            "codebridge",
            root,
            scope=RagIndexScope.CODE,
        )
        self.assertEqual(
            [item.path for item in plan.candidates],
            ["src/main.py"],
        )

    def test_explicit_paths_limit_scope(self):
        root = self.make_project()
        plan = plan_rag_index(
            "codebridge",
            root,
            paths=("src",),
        )
        self.assertEqual(
            [item.path for item in plan.candidates],
            ["src/main.py"],
        )

    def test_default_operation_is_plan_only(self):
        root = self.make_project()
        called = []

        result = run_explicit_rag_index(
            "codebridge",
            root,
            executor=lambda plan: called.append(plan) or {"ok": True},
        )

        self.assertEqual(result.action, RagIndexAction.PLAN)
        self.assertFalse(result.executed)
        self.assertIsNone(result.execution)
        self.assertEqual(called, [])

    def test_execute_true_requires_registered_executor(self):
        root = self.make_project()

        with self.assertRaises(RagIndexExecutionUnavailableError):
            run_explicit_rag_index(
                "codebridge",
                root,
                execute=True,
            )

    def test_execute_true_calls_executor_exactly_once(self):
        root = self.make_project()
        calls = []

        def executor(plan):
            calls.append(plan)
            return {
                "indexed_files": plan.candidate_count,
                "status": "DONE",
            }

        result = run_explicit_rag_index(
            "codebridge",
            root,
            execute=True,
            executor=executor,
        )

        self.assertEqual(result.action, RagIndexAction.EXECUTE)
        self.assertTrue(result.executed)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            result.execution["indexed_files"],
            result.plan.candidate_count,
        )

    def test_project_root_and_namespace_are_validated(self):
        root = self.make_project()
        with self.assertRaises(ValueError):
            plan_rag_index("CodeBridge", root)
        with self.assertRaises(ValueError):
            plan_rag_index("codebridge", root / "missing")

    def test_path_escape_is_rejected(self):
        root = self.make_project()
        with self.assertRaises(ValueError):
            plan_rag_index(
                "codebridge",
                root,
                paths=("../outside",),
            )


if __name__ == "__main__":
    unittest.main()
