"""Testa o modo bloqueante de codebridge_exec (block_until_done).

Com _safe_exchange monkeypatchado (sem servidor real): START->RUNNING,
STATUS repete RUNNING ate FINISHED, RESULT entrega a saida. Garante que
block_until_done=True fecha o comando numa unica chamada e que o padrao
(sem block) nao bloqueia.
"""
import unittest
from unittest.mock import patch

import mcp_server


def _fake_factory(status_ate_finish=2):
    estado = {"n": 0}

    def fake(op, payload=None, timeout=None):
        b = {"request_syn": {"request_id": "rq"},
             "response_syn": {"response_id": "rs"}}
        if op == "EXECUTION_V2_START":
            b["payload"] = {"operation_ok": True, "execution_id": "exec_t",
                            "state": "RUNNING", "target": "CMD"}
        elif op == "EXECUTION_V2_STATUS":
            estado["n"] += 1
            st = "RUNNING" if estado["n"] < status_ate_finish else "FINISHED"
            b["payload"] = {"operation_ok": True, "execution_id": "exec_t",
                            "state": st}
        elif op == "EXECUTION_V2_RESULT":
            b["payload"] = {"operation_ok": True, "state": "FINISHED",
                            "exit_code": 0, "output": "done",
                            "execution_id": "exec_t"}
        else:
            b["payload"] = {"operation_ok": True}
        return b

    return fake, estado


class BlockExecTest(unittest.TestCase):
    def test_bloqueante_fecha_em_uma_chamada(self):
        fake, estado = _fake_factory(2)
        with patch.object(mcp_server, "_safe_exchange", fake):
            r = mcp_server.codebridge_exec(
                "CMD", "echo x", block_until_done=True, block_max_ms=5000)
        self.assertEqual(r.state, "FINISHED")
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.output, "done")
        self.assertGreaterEqual(estado["n"], 1)

    def test_padrao_nao_bloqueia(self):
        fake, _ = _fake_factory(999)
        with patch.object(mcp_server, "_safe_exchange", fake):
            r = mcp_server.codebridge_exec("CMD", "echo x", wait_timeout_ms=0)
        self.assertEqual(r.state, "RUNNING")

    def test_block_max_ms_nao_pendura(self):
        fake, _ = _fake_factory(1)  # termina no 1o status
        with patch.object(mcp_server, "_safe_exchange", fake):
            r = mcp_server.codebridge_exec(
                "CMD", "echo x", block_until_done=True, block_max_ms=999999999)
        self.assertEqual(r.state, "FINISHED")


if __name__ == "__main__":
    unittest.main()
