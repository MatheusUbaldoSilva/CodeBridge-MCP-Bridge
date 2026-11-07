"""Textos do bloco de status (Servidor MCP, Tunel seguro, Comando em execucao)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_rewrite"))
import status_text as st


class StatusTextTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(st.terminal_name("POWERSHELL5.1"), "PowerShell 5.1")
        self.assertEqual(st.terminal_name("ssh"), "Linux (SSH)")
        self.assertEqual(st.state_name("RUNNING"), "rodando")
        self.assertEqual(st.overall_text("READY"), "Estado geral: PRONTO")
        self.assertNotIn("Autoral", st.MCP_TITLE)

    def test_services(self):
        self.assertEqual(st.service_text("Servidor MCP", "ONLINE", pid=10200),
                         "Servidor MCP: ONLINE" + st.DOT + "PID 10200")
        self.assertIn("erro: x", st.service_text("T", "OFFLINE", error="x"))
        self.assertEqual(st.api_text(True, "127.0.0.1", 58958),
                         "API local: ONLINE" + st.DOT + "127.0.0.1:58958")

    def test_elapsed(self):
        self.assertTrue(st.elapsed_text(12).endswith("12 s"))
        self.assertTrue(st.elapsed_text(125).endswith("2 min 05 s"))
        self.assertTrue(st.elapsed_text(3780).endswith("1 h 03 min"))

    def test_preview_cuts_and_counts(self):
        cmd = "\n\n  cd C:\\x; git status  \nlinha2\n\nlinha3\n"
        first, extra = st.command_preview(cmd)
        self.assertTrue(first.startswith("cd C:\\x; git status"))
        self.assertTrue(first.endswith(st.ELLIPSIS))
        self.assertEqual(extra, 2)
        long_first, _ = st.command_preview("x" * 300, width=50)
        self.assertEqual(len(long_first), 50)

    def test_active_text(self):
        rich, tip = st.active_text("POWERSHELL5.1", "RUNNING", "Get-Date\n<b>x</b>",
                                   started_at=100, now=112, stop_requested=True,
                                   internal_id="exec_abc")
        self.assertIn(st.ACTIVE_TITLE + ": PowerShell 5.1", rich)
        self.assertIn("12 s", rich)
        self.assertIn("parada solicitada", rich)
        self.assertNotIn("Get-Date", rich)
        self.assertNotIn("<br>", rich)
        self.assertIn("Get-Date", tip)
        self.assertNotIn("exec_abc", rich)
        self.assertIn("exec_abc", tip)
        self.assertIn("<b>x</b>", tip)
        self.assertEqual(st.active_text()[0], st.ACTIVE_TITLE + ": nenhum")

    def test_tooltip_is_limited(self):
        tip = st.command_tooltip("\n".join(str(i) for i in range(100)), max_lines=5)
        self.assertEqual(tip.splitlines()[:5], ["0", "1", "2", "3", "4"])
        self.assertTrue(tip.endswith(st.ELLIPSIS))


if __name__ == "__main__":
    unittest.main()