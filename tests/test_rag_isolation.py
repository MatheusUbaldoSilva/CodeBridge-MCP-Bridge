import ast
import importlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
AUTHOR = ROOT / "author_mcp"

for path in (APP, AUTHOR, ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


CRITICAL_MCP_TOOLS = {
    "codebridge_exec",
    "codebridge_wait",
    "codebridge_stop",
    "codebridge_read_batch",
    "codebridge_prepare",
    "codebridge_execute_prepared",
    "codebridge_discard",
}

CRITICAL_SOURCE_FILES = (
    AUTHOR / "mcp_server.py",
    AUTHOR / "runtime_client.py",
    AUTHOR / "adapter_server.py",
    APP / "api_server.py",
    APP / "executor.py",
    APP / "execution_ledger.py",
    APP / "external_prepare_store.py",
    APP / "external_execute_store.py",
    APP / "read_only_batch.py",
)


class RagImportFailureFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "rag" or fullname.startswith("rag."):
            raise ModuleNotFoundError(
                "simulated total RAG failure",
                name=fullname,
            )
        return None


class RagUnavailable:
    def __enter__(self):
        self.finder = RagImportFailureFinder()
        sys.meta_path.insert(0, self.finder)
        for name in list(sys.modules):
            if name == "rag" or name.startswith("rag."):
                sys.modules.pop(name, None)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.finder in sys.meta_path:
            sys.meta_path.remove(self.finder)


def _imports_from(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _function_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


class RagIsolationTests(unittest.TestCase):
    def test_critical_execution_sources_do_not_import_rag(self):
        for path in CRITICAL_SOURCE_FILES:
            with self.subTest(path=path.name):
                self.assertNotIn("rag", _imports_from(path))

    def test_public_mcp_execution_tools_remain_declared(self):
        functions = _function_names(AUTHOR / "mcp_server.py")
        self.assertTrue(
            CRITICAL_MCP_TOOLS.issubset(functions),
            CRITICAL_MCP_TOOLS - functions,
        )

    def test_runtime_bridge_imports_when_rag_is_totally_unavailable(self):
        module_names = (
            "executor",
            "execution_ledger",
            "external_prepare_store",
            "external_execute_store",
            "read_only_batch",
            "api_server",
            "runtime_client",
            "adapter_server",
        )
        for name in module_names:
            sys.modules.pop(name, None)

        with RagUnavailable():
            for name in module_names:
                with self.subTest(module=name):
                    module = importlib.import_module(name)
                    self.assertIsNotNone(module)

    def test_read_only_batch_still_executes_when_rag_is_down(self):
        sys.modules.pop("read_only_batch", None)
        with RagUnavailable():
            module = importlib.import_module("read_only_batch")
            result = module.execute_read_only_batch([
                {"id": "version", "kind": "VERSION"},
            ])

        self.assertTrue(result["complete"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["ok_count"], 1)
        self.assertEqual(result["error_count"], 0)

    def test_execution_engine_still_runs_when_rag_is_down(self):
        sys.modules.pop("executor", None)

        class FakeStore:
            def __init__(self):
                self.states = []

            def mark_prepared(self, job_id):
                self.states.append(("prepared", job_id))

            def wait_for_field(self, job_id, field, timeout=1.0):
                return True

            def mark_running(self, job_id):
                self.states.append(("running", job_id))

            def finish(
                self,
                job_id,
                state,
                output="",
                exit_code=None,
                error_type=None,
                error_message=None,
            ):
                self.states.append(
                    ("finished", job_id, state, output, exit_code)
                )

        class FakeTerminals:
            def __init__(self):
                self.prepared = None
                self.executed = None

            def prepare(self, target, command):
                self.prepared = (target, command)

            def execute_prepared(self, target, command):
                self.executed = (target, command)
                return "RAG-INDEPENDENT"

            def status(self):
                return {"prepared_target": None}

            def discard_prepared(self):
                self.prepared = None

        with RagUnavailable():
            executor = importlib.import_module("executor")
            store = FakeStore()
            terminals = FakeTerminals()
            engine = executor.ExecutionEngine(
                store,
                terminals,
                preview_seconds=0,
            )
            engine._run_job({
                "id": "job-rag-isolation",
                "target": "POWERSHELL5.1",
                "command": "Write-Output RAG-INDEPENDENT",
            })

        self.assertEqual(
            terminals.executed,
            (
                "POWERSHELL5.1",
                "Write-Output RAG-INDEPENDENT",
            ),
        )
        self.assertIn(
            (
                "finished",
                "job-rag-isolation",
                "SUCCESS",
                "RAG-INDEPENDENT",
                0,
            ),
            store.states,
        )

    def test_execution_ledgers_initialize_when_rag_is_down(self):
        for name in (
            "execution_ledger",
            "external_prepare_store",
            "external_execute_store",
        ):
            sys.modules.pop(name, None)

        with tempfile.TemporaryDirectory() as temp, RagUnavailable():
            execution_ledger = importlib.import_module(
                "execution_ledger"
            )
            prepare_store = importlib.import_module(
                "external_prepare_store"
            )
            execute_store = importlib.import_module(
                "external_execute_store"
            )

            ledger = execution_ledger.ExecutionLedger(
                Path(temp) / "executions.db"
            )
            prepared = prepare_store.ExternalPrepareStore(
                Path(temp) / "prepared.db"
            )
            executed = execute_store.ExternalExecuteStore(
                Path(temp) / "external.db"
            )

            self.assertIsNone(ledger.get("missing"))
            self.assertIsNone(prepared.get("missing"))
            self.assertIsNone(
                executed.get_by_execution("missing")
            )


if __name__ == "__main__":
    unittest.main()
