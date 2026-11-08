"""Aba IA Local (Qt offscreen) com servidor, modelo e terminal falsos."""
import json
import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import local_ai_panel as panel_mod
import local_ai_server as srv

APP = QApplication.instance() or QApplication([])


class FakeServer:
    def __init__(self, mode="ON_DEMAND", installed=True):
        self.mode, self.installed = mode, installed
        self.state, self.error, self.busy = srv.STATE_OFF, "", False
        self.port, self.api_key = 1, "k"
        self.starts = 0

    def is_installed(self):
        return self.installed

    def is_running(self):
        return self.state in (srv.STATE_LOADING, srv.STATE_READY)

    def idle_seconds_left(self):
        return 540 if self.state == srv.STATE_READY and self.mode == "ON_DEMAND" else None

    def set_mode(self, mode):
        self.mode = mode
        if mode == "OFF":
            self.stop()
        elif mode == "ON":
            self.start()

    def start(self):
        self.starts += 1
        self.state = srv.STATE_READY
        return True

    def stop(self):
        self.state = srv.STATE_OFF

    def tick(self):
        pass

    def touch(self):
        pass

    def wait_ready(self, timeout=0, cancelled=None):
        return self.state == srv.STATE_READY


class ScriptedClient:
    def __init__(self, replies):
        self.replies = replies
        self.decide_requests, self.pending = [], []

    def decide(self, messages, schema):
        """Le os scripts antigos: resposta com tool_calls vira decisao; texto vira 'responder'."""
        self.decide_requests.append((messages, schema))
        if not self.pending and self.replies and self.replies[0].get("tool_calls"):
            for item in self.replies.pop(0)["tool_calls"]:
                args = json.loads(item["function"]["arguments"])
                args["acao"] = item["function"]["name"]
                args.setdefault("motivo", "teste")
                self.pending.append(args)
        if self.pending:
            return self.pending.pop(0)
        return {"acao": "responder", "motivo": "teste"}

    def chat(self, messages, schemas, on_text=None, cancelled=None):
        reply = self.replies.pop(0)
        if reply.get("content") and on_text:
            on_text(reply["content"])
        return {"content": reply.get("content", ""), "tool_calls": reply.get("tool_calls", [])}


class Runner:
    def __init__(self):
        self.calls = []

    def run(self, terminal, command, cancelled):
        self.calls.append((terminal, command))
        return {"state": "FINISHED", "exit_code": 0, "output": "saida ok"}


def pump(panel, condition, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        APP.processEvents()
        panel._tick()
        if condition():
            return True
        time.sleep(0.02)
    return False


class LocalAiPanelTest(unittest.TestCase):
    def make(self, replies, **server_kwargs):
        self.server = FakeServer(**server_kwargs)
        self.runner = Runner()
        client = ScriptedClient(replies)
        panel = panel_mod.LocalAiPanel(
            None, project_id=lambda: "codebridge", project_root=lambda: None,
            search_fn=lambda q, p, k: {"results": [{"path": "doc.md", "snippet": "x"}]},
            server=self.server, runner=self.runner, client_factory=lambda: client)
        self.addCleanup(panel.shutdown)
        return panel

    def test_modes_and_badge(self):
        panel = self.make([])
        self.assertTrue(panel.mode_buttons["ON_DEMAND"].isChecked())
        self.assertIn("liga ao enviar", panel.status.text())
        self.assertEqual(panel_mod.badge(self.server)[0], "IA: OFF")
        panel.choose_mode("ON")
        self.assertTrue(panel.mode_buttons["ON"].isChecked())
        self.assertEqual(panel_mod.badge(self.server)[0], "IA: ON")
        panel.choose_mode("OFF")
        self.assertEqual(self.server.state, srv.STATE_OFF)
        self.assertFalse(panel.send_button.isEnabled())

    def test_on_demand_starts_on_first_message_and_answers(self):
        panel = self.make([{"content": "Use `git status`."}])
        self.assertFalse(panel.use_rag.isChecked())  # padrao: desmarcada
        panel.use_rag.setChecked(True)
        panel.input.setPlainText("como vejo mudancas?")
        panel.send()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertEqual(self.server.starts, 1)
        html_text = panel.chat.toHtml()
        self.assertIn("como vejo mudancas?", html_text)
        self.assertIn("git status", html_text)
        self.assertIn("consultou a Central RAG", html_text)
        self.assertIn("desliga em 9 min", panel.status.text())
        self.assertIn("nenhuma", panel.folder_label.text())

    def test_approval_card_edit_and_run(self):
        call = {"id": "c1", "type": "function", "function": {
            "name": "executar_comando",
            "arguments": json.dumps({"terminal": "CMD", "comando": "dir", "motivo": "listar"})}}
        panel = self.make([{"content": "", "tool_calls": [call]}, {"content": "Listado."}])
        panel.use_rag.setChecked(False)
        panel.input.setPlainText("lista a pasta")
        panel.send()
        self.assertTrue(pump(panel, lambda: (not panel.card.isHidden())))
        self.assertIn("CMD", panel.card_title.text())
        self.assertEqual(panel.card_command.toPlainText(), "dir")
        self.assertTrue(panel.card_command.isReadOnly())
        self.assertEqual(self.runner.calls, [])
        panel.edit_command()
        self.assertFalse(panel.card_command.isReadOnly())
        panel.card_command.setPlainText("dir /b")
        panel.approve_command()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertEqual(self.runner.calls, [("CMD", "dir /b")])
        self.assertFalse((not panel.card.isHidden()))
        self.assertIn("Listado.", panel.chat.toHtml())

    def test_reject_and_clear(self):
        call = {"id": "c1", "type": "function", "function": {
            "name": "executar_comando",
            "arguments": json.dumps({"terminal": "CMD", "comando": "del x", "motivo": "?"})}}
        panel = self.make([{"content": "", "tool_calls": [call]}, {"content": "Ok, não vou."}])
        panel.input.setPlainText("apaga")
        panel.send()
        self.assertTrue(pump(panel, lambda: (not panel.card.isHidden())))
        panel.reject_command()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertEqual(self.runner.calls, [])
        self.assertIn("recusou", panel.chat.toHtml())
        panel.clear()
        self.assertEqual(panel.blocks, [])
        self.assertEqual(panel.agent.history, [])

    def test_unchecked_rag_is_never_searched(self):
        searches = []
        self.server = FakeServer()
        client = ScriptedClient([{"content": "Python 3.13."}])
        panel = panel_mod.LocalAiPanel(
            None, project_id=lambda: "codebridge", project_root=lambda: None,
            search_fn=lambda q, p, k: searches.append(q) or {"results": []},
            server=self.server, runner=Runner(), client_factory=lambda: client)
        self.addCleanup(panel.shutdown)
        panel.use_rag.setChecked(False)
        panel.input.setPlainText("Qual a versão do Python instalada?")
        panel.send()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertEqual(searches, [])
        self.assertNotIn("consultou a Central RAG", panel.chat.toHtml())
        schema = client.decide_requests[0][1]
        self.assertNotIn("buscar_central_rag", schema["properties"]["acao"]["enum"])

    def test_chat_looks_like_claude_app(self):
        import local_ai_chat as chat_mod
        call = {"id": "c1", "type": "function", "function": {
            "name": "executar_comando",
            "arguments": json.dumps({"terminal": "CMD", "comando": "dir", "motivo": "listar"})}}
        panel = self.make([{"content": "", "tool_calls": [call]}, {"content": "Pronto."}])
        panel.input.setPlainText("rode dir")
        panel.send()
        self.assertTrue(pump(panel, lambda: not panel.card.isHidden()))
        panel.approve_command()
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertEqual([b[0] for b in panel.blocks], ["user", "activity", "output", "assistant"])
        text = panel.chat.toHtml()
        self.assertNotIn("Você:", text)
        self.assertNotIn("IA:", text)
        widgets = [w for _sig, w in panel.chat.items]
        bubble, activity, output, answer = widgets
        self.assertIsInstance(output, chat_mod._Output)
        self.assertIn("saida ok", output.text())  # saida real do terminal, inteira
        self.assertIsInstance(bubble, chat_mod._UserBubble)
        self.assertEqual(bubble.layout().itemAt(0).spacerItem() is not None, True)  # balao a direita
        self.assertIn("Usou o CodeBridge", activity.header.text())
        self.assertIn("executou 1 comando", activity.header.text())
        self.assertFalse(activity.expanded)  # fechado por padrao
        activity.header.click()
        self.assertTrue(activity.expanded)
        self.assertIn("executando no CMD: dir", activity.details.text())
        self.assertIn("Pronto.", answer.text())
        panel.clear()
        panel._tick()
        self.assertEqual(panel.chat.items, [])

    def test_composer_like_claude_app(self):
        panel = self.make([{"content": "Ok."}])
        self.assertNotIn("Shift", panel.input.placeholderText())
        self.assertIs(panel.use_rag.parent(), panel.composer)
        self.assertIs(panel.send_button.parent(), panel.composer)
        self.assertFalse(panel.send_button.isEnabled())  # vazio: nao envia
        one_line = panel.input.height()
        panel.input.setPlainText("a\nb\nc\nd")
        self.assertGreater(panel.input.height(), one_line)  # cresce com o texto
        self.assertTrue(panel.send_button.isEnabled())
        panel.input.setPlainText("\n".join("x" * 30))
        self.assertLessEqual(panel.input.height(),
                             panel_mod.INPUT_MAX_LINES * panel.input.fontMetrics().lineSpacing() + 10)
        panel.input.setPlainText("oi")
        panel.send()
        panel._tick()
        self.assertTrue(panel.stop_button.isHidden() is False or not panel.agent.running)
        self.assertTrue(pump(panel, lambda: not panel.agent.running))
        self.assertTrue(panel.stop_button.isHidden())
        self.assertFalse(panel.send_button.isHidden())
        self.assertEqual(panel.input.height(), one_line)  # volta para 1 linha

    def test_short_bubble_stays_on_one_line(self):
        import local_ai_chat as chat_mod
        short = chat_mod._UserBubble("executar ls no terminal ssh")
        short.fit(800)
        limit = int(800 * chat_mod.BUBBLE_MAX_RATIO)
        text_width = short.label.fontMetrics().horizontalAdvance("executar ls no terminal ssh")
        self.assertLess(short.label.maximumWidth(), limit)  # nao estica ate o limite
        self.assertGreaterEqual(short.label.maximumWidth(), text_width + 24)  # cabe numa linha com o padding
        long = chat_mod._UserBubble("palavra " * 80)
        long.fit(800)
        self.assertEqual(long.label.maximumWidth(), limit)  # texto longo quebra no limite

    def test_activity_summary_texts(self):
        import local_ai_chat as chat_mod
        notes = ["leu app/a.py, linhas 1–10", "leu app/b.py, linhas 1–5", "listou a pasta tests",
                 "consultou a Central RAG (3 trechos): x", "executando no PowerShell: dir",
                 "comando terminou (concluído, código 0)"]
        self.assertEqual(chat_mod.activity_summary(notes),
                         "Usou o CodeBridge · leu 2 arquivos · listou 1 pasta · "
                         "consultou a Central RAG · executou 1 comando")
        self.assertIn("comando recusado", chat_mod.activity_summary(["você recusou o comando"]))

    def test_not_installed_message(self):
        panel = self.make([], installed=False)
        self.assertIn("não instalado", panel.chat.toHtml())

    def test_format_message_code_blocks(self):
        out = panel_mod.format_message("Veja:\n```powershell\nGet-Date <x>\n```\nfim `a`")
        self.assertIn("<pre", out)
        self.assertIn("Get-Date &lt;x&gt;", out)
        self.assertIn("<code", out)
        self.assertIn("pre-wrap", out)
        self.assertNotIn("<br><pre", out)
        md = panel_mod.format_message("### Titulo\n- item **forte**\n  - sub")
        self.assertIn('<b style="color:#dfe7ee;">Titulo</b>', md)
        self.assertIn("\u2022 item <b>forte</b>", md)
        self.assertNotIn("###", md)


if __name__ == "__main__":
    unittest.main()
