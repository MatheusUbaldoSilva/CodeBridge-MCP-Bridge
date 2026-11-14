"""Testes de tool_hints.hint_for (dicas de proxima acao para erros)."""
import unittest

from tool_hints import hint_for


class HintForTest(unittest.TestCase):
    def test_timeout_aponta_para_wait(self):
        self.assertIn("codebridge_wait", hint_for("timed_out"))
        self.assertIn("codebridge_wait", hint_for("timeout"))

    def test_unavailable_por_substring(self):
        # casa mesmo embutido num nome de erro maior
        dica = hint_for("CodeBridgeUnavailable")
        self.assertIsNotNone(dica)
        self.assertIn("Repita", dica)

    def test_busy_menciona_stop(self):
        self.assertIn("codebridge_stop", hint_for("busy"))
        self.assertIn("codebridge_stop", hint_for("one_at_a_time"))

    def test_not_found_manda_reiniciar(self):
        self.assertIn("codebridge_exec", hint_for("not_found"))

    def test_desconhecido_sem_recuperavel_e_none(self):
        self.assertIsNone(hint_for("PowerShellCommandError"))

    def test_desconhecido_recuperavel_cai_no_generico(self):
        self.assertEqual(hint_for("algo_estranho", recoverable=True),
                         "Erro recuperavel: repita a mesma chamada.")

    def test_none_sem_recuperavel_e_none(self):
        self.assertIsNone(hint_for(None))
        self.assertIsNone(hint_for(""))

    def test_none_com_recuperavel_e_generico(self):
        self.assertEqual(hint_for(None, recoverable=True),
                         "Erro recuperavel: repita a mesma chamada.")

    def test_caixa_ignorada(self):
        self.assertEqual(hint_for("TIMED_OUT"), hint_for("timed_out"))


if __name__ == "__main__":
    unittest.main()
