"""Testes do motor project_sync com um SFTP fake (sem servidor real)."""
import os
import sys
import stat as _stat
import tempfile
import unittest
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.join(_ROOT, "app_rewrite")
if _APP not in sys.path:
    sys.path.insert(0, _APP)

import project_sync as ps


class FakeAttr:
    def __init__(self, filename, mode, size=0, mtime=0):
        self.filename = filename
        self.st_mode = mode
        self.st_size = size
        self.st_mtime = mtime


def _dir(name):
    return FakeAttr(name, _stat.S_IFDIR | 0o755)


def _file(name, size, mtime):
    return FakeAttr(name, _stat.S_IFREG | 0o644, size, mtime)


class FakeSFTP:
    def __init__(self, tree):
        self.tree = tree
        self.gets = []

    def listdir_attr(self, path):
        path = path.rstrip("/")
        filhos = {}
        for p, (content, mtime) in self.tree.items():
            if p.startswith(path + "/"):
                rest = p[len(path) + 1:]
                head = rest.split("/")[0]
                if "/" in rest:
                    filhos[head] = ("dir", None)
                else:
                    filhos[head] = ("file", (content, mtime))
        out = []
        for nome, (kind, info) in filhos.items():
            if kind == "dir":
                out.append(_dir(nome))
            else:
                content, mtime = info
                out.append(_file(nome, len(content), mtime))
        return out

    def get(self, remote, local):
        content, _mtime = self.tree[remote]
        with open(local, "wb") as f:
            f.write(content)
        self.gets.append(remote)


def _connector(sftp):
    return lambda timeout=15: (None, sftp)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "project-sync.json")

    def test_add_list_remove(self):
        p = ps.add_pair("/root/proj", "C:/dest", project_id="proj", path=self.cfg)
        self.assertEqual(p["id"], "sync1")
        self.assertEqual(len(ps.list_pairs(self.cfg)), 1)
        self.assertTrue(ps.remove_pair("sync1", path=self.cfg))
        self.assertEqual(ps.list_pairs(self.cfg), [])

    def test_set_auto(self):
        ps.add_pair("/r", "/l", path=self.cfg)
        ps.set_auto("sync1", True, path=self.cfg)
        self.assertTrue(ps.list_pairs(self.cfg)[0]["auto"])


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "project-sync.json")
        self.local = os.path.join(self.tmp, "dest")
        self.pair = {"id": "sync1", "remote": "/root/proj", "local": self.local}

    def test_primeira_sync_baixa_tudo(self):
        sftp = FakeSFTP({
            "/root/proj/a.txt": (b"aaa", 1000),
            "/root/proj/sub/b.py": (b"print(1)", 1000),
        })
        r = ps.sync_pair(self.pair, sftp=sftp)
        self.assertEqual(r["added"], 2)
        self.assertTrue((Path(self.local) / "a.txt").exists())
        self.assertTrue((Path(self.local) / "sub" / "b.py").exists())

    def test_segunda_sync_pula_inalterados(self):
        sftp = FakeSFTP({"/root/proj/a.txt": (b"aaa", 1000)})
        ps.sync_pair(self.pair, sftp=sftp)
        r = ps.sync_pair(self.pair, sftp=sftp)
        self.assertEqual(r["added"], 0)
        self.assertEqual(r["skipped"], 1)

    def test_arquivo_alterado_rebaixa(self):
        sftp = FakeSFTP({"/root/proj/a.txt": (b"aaa", 1000)})
        ps.sync_pair(self.pair, sftp=sftp)
        sftp.tree["/root/proj/a.txt"] = (b"aaaa-novo", 2000)
        r = ps.sync_pair(self.pair, sftp=sftp)
        self.assertEqual(r["updated"], 1)
        self.assertEqual((Path(self.local) / "a.txt").read_bytes(), b"aaaa-novo")

    def test_aditivo_nunca_apaga_local(self):
        sftp = FakeSFTP({"/root/proj/a.txt": (b"aaa", 1000)})
        ps.sync_pair(self.pair, sftp=sftp)
        extra = Path(self.local) / "meu_local.txt"
        extra.write_text("nao apague")
        ps.sync_pair(self.pair, sftp=sftp)
        self.assertTrue(extra.exists())

    def test_sync_by_id_atualiza_last_sync(self):
        ps.add_pair("/root/proj", self.local, path=self.cfg)
        sftp = FakeSFTP({"/root/proj/a.txt": (b"x", 1000)})
        ps.sync_by_id("sync1", connector=_connector(sftp), path=self.cfg)
        self.assertIsNotNone(ps.list_pairs(self.cfg)[0]["last_sync"])


class DueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "project-sync.json")

    def test_due_respeita_auto_e_intervalo(self):
        ps.add_pair("/r1", "/l1", interval_min=10, auto=True, path=self.cfg)
        ps.add_pair("/r2", "/l2", interval_min=10, auto=False, path=self.cfg)
        due = ps.due_pairs(now=5000, path=self.cfg)
        self.assertEqual([p["id"] for p in due], ["sync1"])
        ps._update_pair("sync1", {"last_sync": 5000}, path=self.cfg)
        self.assertEqual(ps.due_pairs(now=5100, path=self.cfg), [])
        self.assertEqual(
            [p["id"] for p in ps.due_pairs(now=5000 + 601, path=self.cfg)],
            ["sync1"])


if __name__ == "__main__":
    unittest.main()