"""Testa o preenchimento de next_action na base ProtocolOutcome.

next_action e preenchido por um model_validator na base, a partir do
error_type/execution_recoverable, usando tool_hints.hint_for. Garante que a
dica chega nos resultados de exec (subclasse de ProtocolOutcome) sem o servidor
precisar setar nada em cada ponto de erro.
"""
import unittest

import mcp_server


def _exec(payload):
    ex = {"request_syn": {"request_id": "r"}, "response_syn": {"response_id": "s"}}
    return mcp_server._exec_result(
        ex, payload, target="POWERSHELL5.1", output_mode="NORMAL",
        wait_timeout_ms=1000,
    )


class NextActionTest(unittest.TestCase):
    def test_transporte_recuperavel_tem_dica_especifica(self):
        r = _exec({"operation_ok": False, "state": "ERROR",
                   "error_type": "CodeBridgeUnavailable",
                   "error_message": "timed out", "execution_recoverable": True})
        self.assertIsNotNone(r.next_action)
        self.assertIn("Repita", r.next_action)

    def test_erro_desconhecido_recuperavel_cai_no_generico(self):
        r = _exec({"operation_ok": False, "state": "FAILED",
                   "error_type": "PowerShellCommandError",
                   "error_message": "x", "execution_recoverable": True})
        self.assertEqual(r.next_action,
                         "Erro recuperavel: repita a mesma chamada.")

    def test_sucesso_sem_next_action(self):
        r = _exec({"operation_ok": True, "state": "FINISHED",
                   "exit_code": 0, "output": "ok"})
        self.assertIsNone(r.next_action)

    def test_resultado_e_subclasse_da_base(self):
        r = _exec({"operation_ok": True, "state": "FINISHED",
                   "exit_code": 0, "output": "ok"})
        self.assertIsInstance(r, mcp_server.ProtocolOutcome)


if __name__ == "__main__":
    unittest.main()
