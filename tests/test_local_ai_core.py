"""IA Local: ferramentas, agente, cliente e ciclo de vida do servidor (sem modelo real)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

import local_ai_agent as agent_mod
import local_ai_client as client_mod
import local_ai_server as server_mod
import local_ai_tools as tools


def call(name, **arguments):
    return {"id": "c_" + name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "app").mkdir()
        (self.root / "app" / "main.py").write_text("\n".join("linha %d" % i for i in range(1, 501)))
        (self.root / ".env").write_text("SENHA=1")
        (self.root / ".git").mkdir()
        (self.root / "chave.pem").write_text("x")
        (self.root / "bin.dat").write_bytes(b"\x00\x01\x02")

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_numbers_lines_and_caps_at_300(self):
        text, note = tools.read_file(self.root, "app/main.py", 10, 1000)
        lines = text.splitlines()
        self.assertIn("app/main.py (linhas 10-309 de 500)", lines[0])
        self.assertEqual(len(lines) - 1, tools.MAX_READ_LINES)
        self.assertTrue(lines[1].strip().startswith("10  linha 10"))
        self.assertIn("linhas 10", note)

    def test_read_blocks_outside_project_and_sensitive_files(self):
        outside = Path(self.tmp.name).parent / "fora.txt"
        for bad in ("../fora.txt", str(outside), ".env", "chave.pem", ".git/config", "bin.dat"):
            with self.subTest(bad=bad), self.assertRaises(tools.ToolError):
                tools.read_file(self.root, bad)

    def test_read_without_project_root(self):
        with self.assertRaises(tools.ToolError):
            tools.read_file(None, "app/main.py")

    def test_list_dir_hides_git_and_secrets(self):
        text, note = tools.list_dir(self.root, ".")
        self.assertIn("app/", text)
        self.assertNotIn(".git", text)
        self.assertNotIn(".env", text)
        self.assertNotIn("chave.pem", text)
        self.assertEqual(note, "listou a pasta .")

    def test_rag_search_formats_hits(self):
        def fake(query, project, top_k):
            self.assertEqual((query, project, top_k), ("timer", "codebridge", tools.RAG_TOP_K))
            return {"results": [{"path": "a.py", "snippet": "def a(): pass"},
                                {"source_path": "b.md", "text": "B"}]}
        text, note, paths = tools.rag_search(fake, "codebridge", "timer")
        self.assertIn("[1] a.py", text)
        self.assertEqual(paths, ["a.py", "b.md"])
        self.assertEqual(note, "consultou a Central RAG (2 trechos)")

    def test_rag_path_from_metadata(self):
        fake = lambda q, p, k: {"results": [{"content": "x", "metadata": {"path": "rag/a.py"}}]}
        _text, _note, paths = tools.rag_search(fake, "codebridge", "q")
        self.assertEqual(paths, ["rag/a.py"])

    def test_rag_tool_only_offered_when_enabled(self):
        names = lambda enabled: [t["function"]["name"] for t in tools.tool_schemas(enabled)]
        self.assertIn(tools.TOOL_RAG, names(True))
        self.assertNotIn(tools.TOOL_RAG, names(False))

    def test_validate_command(self):
        ok = tools.validate_command({"terminal": "powershell", "comando": " dir ", "motivo": "x"})
        self.assertEqual(ok, {"terminal": "POWERSHELL5.1", "command": "dir", "reason": "x"})
        with self.assertRaises(tools.ToolError):
            tools.validate_command({"terminal": "BASH", "comando": "ls"})
        with self.assertRaises(tools.ToolError):
            tools.validate_command({"terminal": "CMD", "comando": "  "})


class FakeClient:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    def chat(self, messages, schemas, on_text=None, cancelled=None):
        self.requests.append(messages)
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(cancelled)
        if reply.get("content") and on_text:
            on_text(reply["content"])
        return {"content": reply.get("content", ""), "tool_calls": reply.get("tool_calls", [])}


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, terminal, command, cancelled):
        self.calls.append((terminal, command))
        return {"state": "FINISHED", "exit_code": 0, "output": "OK SAIDA"}


def drain(agent, until="turn_done", timeout=5, on_event=None):
    events, end = [], time.time() + timeout
    while time.time() < end:
        try:
            kind, data = agent.events.get(timeout=0.05)
        except Exception:
            continue
        events.append((kind, data))
        if on_event:
            on_event(kind, data)
        if kind == until:
            return events
    raise AssertionError("evento %s nao chegou: %r" % (until, events))


class AgentTest(unittest.TestCase):
    def make(self, replies, root=None, ready=(True, "")):
        self.client = FakeClient(replies)
        self.runner = FakeRunner()
        self.searches = []

        def search(query, project, top_k):
            self.searches.append(query)
            return {"results": [{"path": "doc.md", "snippet": "trecho"}]}

        return agent_mod.LocalAiAgent(
            client_factory=lambda: self.client, ensure_ready=lambda cancelled, status: ready,
            runner=self.runner, search_fn=search, project_id=lambda: "codebridge",
            project_root=lambda: root)

    def test_plain_answer_with_rag_context(self):
        agent = self.make([{"content": "Resposta."}])
        self.assertTrue(agent.send("como funciona?", rag_enabled=True))
        events = drain(agent)
        self.assertIn(("assistant_done", "Resposta."), events)
        self.assertEqual(self.searches, ["como funciona?"])
        sent_user = self.client.requests[0][-1]["content"]
        self.assertIn("[Trechos da Central RAG", sent_user)
        # o historico guarda a pergunta sem o contexto (economiza espaco)
        self.assertEqual(agent.history[0], {"role": "user", "content": "como funciona?"})

    def test_rag_disabled_skips_search(self):
        agent = self.make([{"content": "ok"}])
        agent.send("oi", rag_enabled=False)
        drain(agent)
        self.assertEqual(self.searches, [])

    def test_command_runs_only_after_approval(self):
        agent = self.make([
            {"content": "", "tool_calls": [call("executar_comando", terminal="POWERSHELL5.1",
                                                 comando="Get-Date", motivo="ver hora")]},
            {"content": "Feito."},
        ])
        agent.send("que horas?", rag_enabled=False)

        def on_event(kind, data):
            if kind == "approval":
                self.assertEqual(self.runner.calls, [])
                self.assertEqual(data["command"], "Get-Date")
                agent.approve("Get-Date -Format s")

        drain(agent, on_event=on_event)
        self.assertEqual(self.runner.calls, [("POWERSHELL5.1", "Get-Date -Format s")])
        tool_msg = [m for m in agent.history if m["role"] == "tool"][0]
        self.assertIn("OK SAIDA", tool_msg["content"])
        self.assertIn("editou", tool_msg["content"])

    def test_rejected_command_is_reported_to_model(self):
        agent = self.make([
            {"content": "", "tool_calls": [call("executar_comando", terminal="CMD", comando="dir", motivo="x")]},
            {"content": "Entendido."},
        ])
        agent.send("lista", rag_enabled=False)
        drain(agent, on_event=lambda k, d: agent.reject() if k == "approval" else None)
        self.assertEqual(self.runner.calls, [])
        tool_msg = [m for m in agent.history if m["role"] == "tool"][0]
        self.assertIn("recusou", tool_msg["content"])

    def test_cancel_while_waiting_for_approval_rolls_back(self):
        agent = self.make([
            {"content": "", "tool_calls": [call("executar_comando", terminal="CMD", comando="dir", motivo="x")]},
        ])
        agent.send("lista", rag_enabled=False)
        events = drain(agent, on_event=lambda k, d: agent.cancel() if k == "approval" else None)
        self.assertIn(("note", "interrompido"), events)
        self.assertEqual(agent.history, [])
        self.assertFalse(agent.running)

    def test_read_tool_is_scoped(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        Path(tmp.name, "a.txt").write_text("ola")
        agent = self.make([
            {"content": "", "tool_calls": [call("ler_arquivo", caminho="a.txt"),
                                           call("ler_arquivo", caminho="../x.txt")]},
            {"content": "Pronto."},
        ], root=tmp.name)
        agent.send("le", rag_enabled=False)
        drain(agent)
        results = [m["content"] for m in agent.history if m["role"] == "tool"]
        self.assertIn("ola", results[0])
        self.assertTrue(results[1].startswith("ERRO:"))

    def test_mentioned_files_are_read_automatically(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        Path(tmp.name, "app").mkdir()
        Path(tmp.name, "app", "repo_path.py").write_text("import sys\nRAIZ = 1\n")
        Path(tmp.name, ".env").write_text("SENHA=1")
        agent = self.make([{"content": "Explicado."}], root=tmp.name)
        agent.send("Leia app/repo_path.py e o .env, e veja inexistente.py.", rag_enabled=False)
        events = drain(agent)
        sent_user = self.client.requests[0][-1]["content"]
        self.assertIn("RAIZ = 1", sent_user)
        self.assertNotIn("SENHA", sent_user)
        self.assertTrue(any(k == "note" and "leu app/repo_path.py" in d for k, d in events))
        self.assertEqual(agent.history[0]["content"],
                         "Leia app/repo_path.py e o .env, e veja inexistente.py.")

    def test_not_ready_reports_error(self):
        agent = self.make([], ready=(False, "Memória insuficiente"))
        agent.send("oi")
        events = drain(agent)
        self.assertIn(("error", "Memória insuficiente"), events)
        self.assertEqual(agent.history, [])

    def test_steps_are_limited(self):
        loop = {"content": "", "tool_calls": [call("listar_pasta", caminho=".")]}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        agent = self.make([loop] * agent_mod.MAX_STEPS, root=tmp.name)
        agent.send("x", rag_enabled=False)
        events = drain(agent)
        self.assertTrue(any(k == "note" and "passos" in d for k, d in events))

    def test_strip_tool_json_from_answer(self):
        text = ('Use isto:\n\n{"terminal":"POWERSHELL5.1","comando":"dir","motivo":"x"}\n\n'
                'Fim. {"a": 1} fica.\n{"chave": 2}')
        self.assertEqual(agent_mod.strip_tool_json(text),
                         'Use isto:\n\nFim. {"a": 1} fica.\n{"chave": 2}')

    def test_trim_history_drops_oldest_whole_turns(self):
        history = []
        for i in range(10):
            history += [{"role": "user", "content": "p%d " % i + "x" * 3000},
                        {"role": "assistant", "content": "r%d" % i}]
        trimmed = agent_mod.trim_history(history, budget=10000)
        self.assertEqual(trimmed[0]["role"], "user")
        self.assertTrue(trimmed[-1]["content"].startswith("r9"))
        self.assertLessEqual(sum(agent_mod.message_chars(m) for m in trimmed), 10000)


class ClientParsingTest(unittest.TestCase):
    def test_text_tool_call_fallback(self):
        content = 'Vou ler.\n<tool_call>{"name": "ler_arquivo", "arguments": {"caminho": "a.py"}}</tool_call>'
        cleaned, calls = client_mod.parse_text_tool_calls(content)
        self.assertEqual(cleaned, "Vou ler.")
        self.assertEqual(calls[0]["function"]["name"], "ler_arquivo")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), {"caminho": "a.py"})

    def test_raw_json_tool_call_fallback(self):
        raw = '{\n  "name": "executar_comando",\n  "arguments": {"terminal": "CMD", "comando": "dir", "motivo": "x"}\n}'
        for content in (raw, "```json\n" + raw + "\n```"):
            cleaned, calls = client_mod.parse_text_tool_calls(content)
            self.assertEqual(cleaned, "")
            self.assertEqual(calls[0]["function"]["name"], "executar_comando")
        cleaned, calls = client_mod.parse_text_tool_calls('Exemplo: {"a": 1}')
        self.assertEqual((cleaned, calls), ('Exemplo: {"a": 1}', []))

    def test_stream_deltas_are_merged(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"Ol"}}]}',
            'data: {"choices":[{"delta":{"content":"a"}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1","function":{"name":"listar_pasta","arguments":"{\\"cam"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"inho\\": \\".\\"}"}}]}}]}',
            "data: [DONE]",
        ]
        pieces = []
        result = client_mod.LocalAiClient._read_stream(
            [(l + "\n").encode() for l in lines], pieces.append, lambda: False)
        self.assertEqual(result["content"], "Ola")
        self.assertEqual(pieces, ["Ol", "a"])
        self.assertEqual(json.loads(result["tool_calls"][0]["function"]["arguments"]), {"caminho": "."})


class FakeProc:
    pid = 4242

    def __init__(self):
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.returncode = -9


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.exe, self.model = base / "llama-server.exe", base / "m.gguf"
        self.exe.write_text("x")
        self.model.write_text("x")
        self.now = [1000.0]
        self.procs = []
        self.memory = {"vram_total_mb": 6144, "vram_used_mb": 0, "ram_total_mb": 7900, "ram_used_mb": 5000}
        self.old = (server_mod.LOG_FILE, server_mod.PID_FILE)
        server_mod.LOG_FILE, server_mod.PID_FILE = base / "log.txt", base / "pid"

    def tearDown(self):
        server_mod.LOG_FILE, server_mod.PID_FILE = self.old
        self.tmp.cleanup()

    def make(self):
        def popen(cmd, **kwargs):
            self.cmd = cmd
            proc = FakeProc()
            self.procs.append(proc)
            return proc
        return server_mod.LocalAiServer(
            exe=self.exe, model=self.model, settings=Path(self.tmp.name) / "s.json",
            popen=popen, health=lambda port, key: True, clock=lambda: self.now[0],
            memory=lambda: dict(self.memory))

    def test_default_mode_is_on_demand_and_persists(self):
        server = self.make()
        self.assertEqual(server.mode, "ON_DEMAND")
        server.set_mode("OFF")
        self.assertEqual(self.make().mode, "OFF")

    def test_start_builds_local_only_command_and_becomes_ready(self):
        server = self.make()
        self.assertTrue(server.start())
        self.assertTrue(server.wait_ready(timeout=5))
        self.assertIn("127.0.0.1", self.cmd)
        self.assertIn("--api-key", self.cmd)
        self.assertIn("--jinja", self.cmd)
        server.stop()
        self.assertTrue(self.procs[0].terminated)
        self.assertEqual(server.state, server_mod.STATE_OFF)

    def test_idle_shutdown_only_in_on_demand_and_not_while_busy(self):
        server = self.make()
        server.start()
        server.wait_ready(timeout=5)
        self.now[0] += server_mod.IDLE_SECONDS - 60
        self.assertEqual(server.idle_seconds_left(), 60)
        server.busy = True
        self.now[0] += 120
        server.tick()
        self.assertEqual(server.state, server_mod.STATE_READY)
        server.busy = False
        server.tick()
        self.assertEqual(server.state, server_mod.STATE_OFF)

    def test_mode_on_never_idles_out(self):
        server = self.make()
        server.set_mode("ON")
        server.wait_ready(timeout=5)
        self.now[0] += server_mod.IDLE_SECONDS * 3
        server.tick()
        self.assertEqual(server.state, server_mod.STATE_READY)
        server.stop()

    def test_refuses_to_start_without_memory(self):
        self.memory["vram_used_mb"] = 2000
        server = self.make()
        self.assertFalse(server.start())
        self.assertIn("placa de vídeo", server.error)
        self.memory.update(vram_used_mb=0, ram_used_mb=7500)
        self.assertFalse(server.start())
        self.assertIn("RAM", server.error)
        self.assertEqual(self.procs, [])

    def test_crash_is_reported(self):
        server = self.make()
        server.start()
        server.wait_ready(timeout=5)
        self.procs[0].returncode = 3
        server.tick()
        self.assertEqual(server.state, server_mod.STATE_ERROR)
        self.assertIn("3", server.error)

    def test_not_installed(self):
        self.model.unlink()
        server = self.make()
        self.assertFalse(server.start())
        self.assertIn("não instalado", server.error)


if __name__ == "__main__":
    unittest.main()
