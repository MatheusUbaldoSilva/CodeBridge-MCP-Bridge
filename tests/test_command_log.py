"""Registro diario de comandos (app_rewrite/command_log.py)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "app_rewrite"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import command_log as cl  # noqa: E402


def job(**kw):
    base = {
        "id": "abc", "target": "POWERSHELL5.1", "command": "git status",
        "state": "SUCCESS", "exit_code": 0,
        "created_at": "2026-11-13T23:49:00+00:00",
        "started_at": "2026-11-13T23:49:00+00:00",
        "finished_at": "2026-11-13T23:49:02+00:00",
        "output": "ok", "error_message": None,
    }
    base.update(kw)
    return base


class RedactTest(unittest.TestCase):
    def test_masks_secrets_keeps_rest(self):
        r = cl.redact('llama-server.exe -m q.gguf --api-key 3f9ac1 -ngl 99')
        self.assertIn("--api-key ****", r)
        self.assertIn("-ngl 99", r)              # resto intacto
        self.assertNotIn("3f9ac1", r)
        self.assertIn("--password ****", cl.redact('tool --password "senha secreta"'))
        self.assertEqual(cl.redact("token=abc123 outro=ok").split()[0], "token=****")
        self.assertIn("ftp://deploy:****@host", cl.redact("put ftp://deploy:p4ss@host/x"))
        self.assertIn("Authorization: Bearer ****", cl.redact("Authorization: Bearer eyJabc.def"))

    def test_empty(self):
        self.assertEqual(cl.redact(None), "")
        self.assertEqual(cl.redact(""), "")


class PathTest(unittest.TestCase):
    def test_day_file_local_date_and_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            when = datetime(2026, 11, 13, 20, 5).astimezone()
            p = cl.day_file(when=when, root=tmp)
            self.assertEqual(p.name, "commands-2026-11-13.jsonl")
            self.assertEqual(p.parent, Path(tmp) / "CodeBridge" / "command-log")


class EntryTest(unittest.TestCase):
    def test_entry_fields_and_no_project(self):
        e = cl.build_entry(job())
        self.assertEqual(e["tipo"], "powershell")
        self.assertEqual(e["exit"], 0)
        self.assertEqual(e["ms"], 2000)          # 2s de execucao
        self.assertEqual(e["comando"], "git status")
        self.assertIn("saida", e)
        self.assertNotIn("projeto", e)           # sem projeto
        self.assertNotIn("erro", e)              # sem erro -> campo ausente

    def test_full_command_not_truncated_but_redacted(self):
        cmd = "x " * 400 + "--api-key SEGREDO"
        e = cl.build_entry(job(command=cmd))
        self.assertEqual(len(e["comando"]), len(cl.redact(cmd)))  # completo
        self.assertNotIn("SEGREDO", e["comando"])

    def test_types_and_error_and_states(self):
        self.assertEqual(cl.build_entry(job(target="CMD"))["tipo"], "cmd")
        self.assertEqual(cl.build_entry(job(target="SSH"))["tipo"], "ssh")
        e = cl.build_entry(job(state="FAILED", exit_code=1, error_message="falhou tok=x"))
        self.assertEqual(e["estado"], "FAILED")
        self.assertEqual(e["exit"], 1)
        self.assertIn("erro", e)

    def test_output_summary_strips_ansi_and_redacts_and_truncates(self):
        out = "\x1b[m inicio " + "y" * 600 + " --password zzz fim"
        s = cl.build_entry(job(output=out))["saida"]
        self.assertNotIn("\x1b", s)
        self.assertIn("[...]", s)
        self.assertLessEqual(len(s), cl.OUTPUT_SUMMARY_CHARS + 10)


class RecordTest(unittest.TestCase):
    def test_appends_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(cl.record(job(), root=tmp))
            self.assertTrue(cl.record(job(command="dir", target="CMD"), root=tmp))
            path = cl.day_file(when=cl._local_dt(job()), root=tmp)
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["comando"], "git status")
            self.assertEqual(json.loads(lines[1])["tipo"], "cmd")

    def test_disabled_by_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[cl.ENABLED_ENV] = "0"
            try:
                self.assertFalse(cl.record(job(), root=tmp))
                self.assertFalse(list(Path(tmp).rglob("*.jsonl")))
            finally:
                del os.environ[cl.ENABLED_ENV]

    def test_never_raises_on_bad_job(self):
        self.assertFalse(cl.record(None))
        self.assertFalse(cl.record({"command": ""}))


if __name__ == "__main__":
    unittest.main()
