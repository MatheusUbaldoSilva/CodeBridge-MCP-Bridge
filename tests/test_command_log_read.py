"""Leitura/resumo do log diario (command_log.read_day/render_day/summarize_day)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "app_rewrite"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import command_log as cl  # noqa: E402


def job(**kw):
    base = {
        "target": "POWERSHELL5.1", "command": "git status", "state": "SUCCESS",
        "exit_code": 0, "created_at": "2026-11-14T09:30:00-03:00",
        "started_at": "2026-11-14T09:30:00-03:00",
        "finished_at": "2026-11-14T09:30:02-03:00", "output": "ok",
    }
    base.update(kw)
    return base


class ReadTest(unittest.TestCase):
    def test_read_render_summarize(self):
        with tempfile.TemporaryDirectory() as tmp:
            cl.record(job(), root=tmp)
            cl.record(job(command="dir", target="CMD", state="FAILED", exit_code=1,
                          error_message="erro"), root=tmp)
            cl.record(job(command="ssh ubuntu@192.168.1.11 uptime", target="SSH"), root=tmp)
            day = cl._local_dt(job())
            date = day.strftime("%Y-%m-%d")

            self.assertIn(date, cl.available_days(root=tmp))
            entries = cl.read_day(date, root=tmp)
            self.assertEqual(len(entries), 3)

            texto = cl.render_day(entries)
            self.assertIn("git status", texto)
            self.assertIn("ssh ubuntu@192.168.1.11 uptime", texto)
            self.assertIn("x(1)", texto)        # a falha marcada
            self.assertIn("09:30", texto)        # horario local

            resumo = cl.summarize_day(entries)
            self.assertEqual(resumo["total"], 3)
            self.assertEqual(resumo["falhas"], 1)
            self.assertEqual(resumo["por_tipo"], {"powershell": 1, "cmd": 1, "ssh": 1})
            self.assertEqual(resumo["primeiro"], "09:30")

    def test_missing_day_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cl.read_day("2000-01-01", root=tmp), [])
            self.assertEqual(cl.available_days(root=tmp), [])
            self.assertEqual(cl.summarize_day([])["total"], 0)

    def test_cli_list_and_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            cl.record(job(), root=tmp)
            date = cl._local_dt(job()).strftime("%Y-%m-%d")
            self.assertEqual(cl._main(["--list", "--root", tmp]), 0)
            self.assertEqual(cl._main(["--day", date, "--root", tmp]), 0)
            self.assertEqual(cl._main(["--day", date, "--summary", "--root", tmp]), 0)


if __name__ == "__main__":
    unittest.main()
