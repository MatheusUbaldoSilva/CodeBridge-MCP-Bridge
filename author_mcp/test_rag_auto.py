"""Testa o codebridge_rag_auto unificado (dispatch por action)."""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mcp_server


class RagAutoTest(unittest.TestCase):
    def test_nove_antigos_removidos_e_um_unificado(self):
        names = {getattr(t, "name", "")
                 for t in mcp_server.mcp._tool_manager.list_tools()}
        self.assertIn("codebridge_rag_auto", names)
        antigos = [n for n in names if n.startswith("codebridge_rag_auto_")]
        self.assertEqual(antigos, [])

    def test_acao_invalida(self):
        r = mcp_server.codebridge_rag_auto(action="xyz")
        self.assertFalse(r["operation_ok"])
        self.assertIn("status|preview", r["error_message"])

    def test_roteia_status(self):
        try:
            import rag.runtime.auto_index_api as api
        except ModuleNotFoundError:
            self.skipTest("pacote rag indisponivel neste ambiente")
        orig = api.auto_status
        api.auto_status = lambda project_id=None, job_id=None: {
            "ok_fake": True, "pid": project_id}
        try:
            r = mcp_server.codebridge_rag_auto(action="status", project_id="projX")
        finally:
            api.auto_status = orig
        self.assertIn("projX", str(r))


if __name__ == "__main__":
    unittest.main()