"""Card "IAs" do topo: leitura dos llama-server e textos de status."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "app_rewrite"), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import ai_status  # noqa: E402

APP = QApplication.instance() or QApplication([])

QWEN_GPU = [r"C:\x\llama-server.exe", "-m", r"C:\ai\models\qwen2.5-coder-7b-instruct-q4_k_m.gguf",
            "--host", "127.0.0.1", "-ngl", "99", "-c", "8192"]
JINA_TEXT_CPU = [r"C:\llama\llama-server.exe", "-m", r"D:\m\v5-small-retrieval-Q4_K_M.gguf",
                 "--embedding", "--device", "none", "-ngl", "0"]
JINA_CODE_GPU = [r"C:\llama\llama-server.exe", "-m", r"D:\m\jina-code-embeddings-1.5b-Q8_0.gguf",
                 "--embedding", "--device", "CUDA0", "-ngl", "99"]


class FakeServer:
    def __init__(self, state="OFF", installed=True):
        self.state, self.installed = state, installed

    def is_installed(self):
        return self.installed


class FakeProc:
    def __init__(self, name, cmdline):
        self.info, self._cmdline = {"name": name}, cmdline

    def cmdline(self):
        if self._cmdline is None:
            raise PermissionError("acesso negado")
        return self._cmdline


class ParseTest(unittest.TestCase):
    def test_cmdline_model_and_device(self):
        self.assertEqual(ai_status.parse_cmdline(QWEN_GPU),
                         {"model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf", "device": "GPU"})
        self.assertEqual(ai_status.parse_cmdline(JINA_TEXT_CPU)["device"], "CPU")
        self.assertEqual(ai_status.parse_cmdline(JINA_CODE_GPU)["device"], "GPU")
        self.assertEqual(ai_status.parse_cmdline(["x", "-m", "a.gguf", "-ngl", "0"])["device"], "CPU")

    def test_scan_only_llama_servers_and_skips_denied(self):
        procs = [FakeProc("llama-server.exe", JINA_TEXT_CPU), FakeProc("python.exe", ["x"]),
                 FakeProc("llama-server.exe", None), FakeProc("explorer.exe", None)]
        found = ai_status.scan_llama_servers(lambda attrs: procs)
        self.assertEqual(found, [{"model": "v5-small-retrieval-q4_k_m.gguf", "device": "CPU"}])


class DescribeTest(unittest.TestCase):
    def test_rows_and_title(self):
        procs = [ai_status.parse_cmdline(QWEN_GPU), ai_status.parse_cmdline(JINA_TEXT_CPU)]
        rows = {r["key"]: r for r in ai_status.describe(FakeServer("READY"), procs)}
        self.assertEqual(rows["LOCAL"]["text"], "Ligada · GPU")
        self.assertEqual(rows["RAG_TEXT"]["text"], "Ativa · CPU")
        self.assertEqual(rows["RAG_CODE"]["text"], "Parada")
        self.assertEqual(ai_status.title_for(list(rows.values())), "IAS · 2 ATIVAS")

    def test_local_states(self):
        def local(server):
            return ai_status.describe(server, [])[0]["text"]
        self.assertEqual(local(FakeServer("OFF")), "Desligada")
        self.assertEqual(local(FakeServer("LOADING")), "Carregando…")
        self.assertEqual(local(FakeServer("ERROR")), "Erro")
        self.assertEqual(local(FakeServer("READY")), "Ligada")
        self.assertEqual(local(FakeServer(installed=False)), "Não instalada")
        self.assertEqual(local(None), "—")
        self.assertEqual(ai_status.title_for(ai_status.describe(FakeServer(), [])),
                         "IAS · NENHUMA ATIVA")


class CardTest(unittest.TestCase):
    def test_card_shows_status_and_opens_tab(self):
        clicks = []
        server = FakeServer("READY")
        card = ai_status.AiStatusCard(local_server=lambda: server, on_click=lambda: clicks.append(1),
                                      scan=lambda: [], interval_ms=60000)
        self.addCleanup(card.deleteLater)
        card.refresh_now([ai_status.parse_cmdline(QWEN_GPU), ai_status.parse_cmdline(JINA_CODE_GPU)])
        self.assertEqual(card.title.text(), "IAS · 2 ATIVAS")
        self.assertEqual(card.states["LOCAL"].text(), "Ligada · GPU")
        self.assertEqual(card.states["RAG_CODE"].text(), "Ativa · GPU")
        self.assertEqual(card.states["RAG_TEXT"].text(), "Parada")
        server.state = "OFF"
        card.refresh_now([])
        self.assertEqual(card.states["LOCAL"].text(), "Desligada")
        self.assertEqual(card.title.text(), "IAS · NENHUMA ATIVA")
        QTest.mouseClick(card, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
        self.assertEqual(clicks, [1])

    def test_background_scan_feeds_card(self):
        card = ai_status.AiStatusCard(local_server=lambda: None,
                                      scan=lambda: [ai_status.parse_cmdline(JINA_TEXT_CPU)],
                                      interval_ms=60000)
        self.addCleanup(card.deleteLater)
        card._scan_in_background()
        card.refresh_now()
        self.assertEqual(card.states["RAG_TEXT"].text(), "Ativa · CPU")
        self.assertFalse(card._scanning)


if __name__ == "__main__":
    unittest.main()
