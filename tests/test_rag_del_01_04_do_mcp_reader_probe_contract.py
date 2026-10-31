"""RAG-DEL-01.04-DO: source/MCP bridge probe contract, no live MCP network.

The installed plugin does not expose codebridge_rag_generation_probe yet.
These tests exercise a new-process DEV bridge, never claim live attestation.
"""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from author_mcp import rag_bridge
from rag.runtime.production_generation_lock import ProductionGenerationBusy


@contextmanager
def _synthetic_generation_reader():
    yield SimpleNamespace(generation="scratch-testgen")


def _mock_lock(*, exclusive=False, channel="generation"):
    @contextmanager
    def lock():
        if exclusive:
            raise ProductionGenerationBusy("synthetic cutover lock conflict")
        yield
    return lock()


def _unsafe_mock_lock(*, exclusive=False, channel="generation"):
    @contextmanager
    def lock():
        yield
    return lock()


class SourceOnlyMcpProbeTests(TestCase):
    def probe(self, lock_factory):
        with (
            patch("rag.runtime.production_generation_read.production_generation_read",
                  _synthetic_generation_reader),
            patch("rag.runtime.production_generation_lock.production_generation_lock",
                  lock_factory),
        ):
            return rag_bridge.inspect_rag_generation_readers()

    def test_source_reader_probe_cannot_authorize_deletion_or_cutover(self):
        row = self.probe(_mock_lock)
        self.assertTrue(row["writer_blocked_during_read"])
        self.assertEqual(row["generation"], "scratch-testgen")
        self.assertFalse(row["safe_to_activate"])
        self.assertFalse(row["child_semantic_execution_attested"])
        self.assertTrue(all(row["loaded_reader_functions"].values()))
        self.assertEqual(row["state"], "PUBLIC_READER_PROBE_PASS")

    def test_probe_refuses_success_when_writer_not_blocked(self):
        row = self.probe(_unsafe_mock_lock)
        self.assertFalse(row["writer_blocked_during_read"])
        self.assertEqual(row["state"], "PUBLIC_READER_PROBE_BLOCKED")
        self.assertFalse(row["safe_to_activate"])

    def test_tool_registered_read_only_without_importing_missing_mcp_package(self):
        source = (Path(__file__).resolve().parents[1]
                  / "author_mcp" / "mcp_server.py")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        found = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "codebridge_rag_generation_probe"
        ]
        self.assertEqual(len(found), 1)
        decor = next(
            d for d in found[0].decorator_list
            if isinstance(d, ast.Call)
            and isinstance(d.func, ast.Attribute)
            and d.func.attr == "tool"
        )
        keywords = {k.arg:k.value for k in decor.keywords}
        self.assertEqual(keywords["name"].value,
                         "codebridge_rag_generation_probe")
        self.assertIs(keywords["structured_output"].value, True)
        annot = keywords["annotations"]
        safety = {k.arg:k.value for k in annot.keywords}
        self.assertIs(safety["read_only_hint"].value, True)