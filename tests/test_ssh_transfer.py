"""Transferencia SFTP (com SFTP falso sobre pasta local) e telas SSH."""
import os
import posixpath
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
import ssh_transfer as st


class _Attr:
    def __init__(self, name, info):
        self.filename = name
        self.st_mode = info.st_mode
        self.st_size = info.st_size
        self.st_mtime = info.st_mtime


class _File:
    def __init__(self, handle):
        self._h = handle

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._h.close()

    def set_pipelined(self, flag):
        pass

    def prefetch(self, size=None):
        pass

    def read(self, n):
        return self._h.read(n)

    def write(self, data):
        self._h.write(data)


class FakeSftp:
    def __init__(self, root):
        self.root = Path(root)

    def _p(self, path):
        return self.root / str(path).lstrip("/")

    def normalize(self, path):
        if path in (".", ""):
            return "/home"
        return posixpath.normpath(path if path.startswith("/") else "/home/" + path)

    def stat(self, path):
        return os.stat(self._p(path))

    def lstat(self, path):
        return os.lstat(self._p(path))

    def listdir_attr(self, path):
        return [_Attr(e.name, os.lstat(e.path)) for e in os.scandir(self._p(path))]

    def mkdir(self, path):
        os.mkdir(self._p(path))

    def open(self, path, mode):
        return _File(open(self._p(path), mode))

    def posix_rename(self, a, b):
        os.replace(self._p(a), self._p(b))

    def rename(self, a, b):
        os.rename(self._p(a), self._p(b))

    def remove(self, path):
        os.remove(self._p(path))

    def utime(self, path, times):
        os.utime(self._p(path), times)

    def close(self):
        pass


class _Transport:
    def is_active(self):
        return True


class FakeClient:
    def get_transport(self):
        return _Transport()

    def close(self):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.remote_root = base / "remote"
        (self.remote_root / "home").mkdir(parents=True)
        self.local = base / "local"
        (self.local / "pasta" / "sub").mkdir(parents=True)
        (self.local / "pasta" / "a.txt").write_text("ola", encoding="utf-8")
        (self.local / "pasta" / "sub" / "b.bin").write_bytes(os.urandom(700000))
        (self.local / "solto.txt").write_text("solto", encoding="utf-8")
        self.opener = lambda: (FakeClient(), FakeSftp(self.remote_root))

    def tearDown(self):
        self.tmp.cleanup()

    def remote(self, rel):
        return self.remote_root / "home" / rel


class TransferTests(Base):
    def test_upload_folder_and_file(self):
        ch = st.SshFileChannel(self.opener)
        ticks = []
        result = ch.transfer(st.UPLOAD, [str(self.local / "pasta"), str(self.local / "solto.txt")],
                             "/home", progress=ticks.append)
        self.assertEqual(result["files"], 3)
        self.assertEqual(self.remote("pasta/sub/b.bin").read_bytes(),
                         (self.local / "pasta" / "sub" / "b.bin").read_bytes())
        self.assertEqual(self.remote("solto.txt").read_text(encoding="utf-8"), "solto")
        self.assertFalse(list(self.remote_root.rglob("*" + st.PART)))
        self.assertEqual(ticks[-1]["done_bytes"], ticks[-1]["total_bytes"])

    def test_conflict_then_overwrite(self):
        ch = st.SshFileChannel(self.opener)
        ch.transfer(st.UPLOAD, [str(self.local / "solto.txt")], "/home")
        (self.local / "solto.txt").write_text("novo", encoding="utf-8")
        with self.assertRaises(st.TransferConflict) as ctx:
            ch.transfer(st.UPLOAD, [str(self.local / "solto.txt")], "/home")
        self.assertEqual(ctx.exception.paths, ["/home/solto.txt"])
        self.assertEqual(self.remote("solto.txt").read_text(encoding="utf-8"), "solto")
        result = ch.transfer(st.UPLOAD, [str(self.local / "solto.txt")], "/home", overwrite=True)
        self.assertEqual(result["overwritten"], 1)
        self.assertEqual(self.remote("solto.txt").read_text(encoding="utf-8"), "novo")

    def test_download_folder(self):
        ch = st.SshFileChannel(self.opener)
        ch.transfer(st.UPLOAD, [str(self.local / "pasta")], "/home")
        back = self.local / "volta"
        back.mkdir()
        result = ch.transfer(st.DOWNLOAD, ["/home/pasta"], str(back))
        self.assertEqual(result["files"], 2)
        self.assertEqual((back / "pasta" / "a.txt").read_text(encoding="utf-8"), "ola")
        self.assertFalse(list(back.rglob("*" + st.PART)))

    def test_cancel_leaves_no_partial_file(self):
        ch = st.SshFileChannel(self.opener)
        with self.assertRaises(st.TransferCancelled):
            ch.transfer(st.UPLOAD, [str(self.local / "pasta")], "/home",
                        cancelled=lambda: True)
        self.assertFalse(list(self.remote_root.rglob("*" + st.PART)))

    def test_missing_destination_and_bad_direction(self):
        ch = st.SshFileChannel(self.opener)
        with self.assertRaises(OSError):
            ch.transfer(st.UPLOAD, [str(self.local / "solto.txt")], "/nao/existe")
        with self.assertRaises(ValueError):
            ch.transfer("SIDEWAYS", ["x"], "/home")
        with self.assertRaises(ValueError):
            ch.transfer(st.UPLOAD, [], "/home")

    def test_windows_names(self):
        self.assertIsNone(st.windows_name_problem("ok.txt"))
        self.assertIsNotNone(st.windows_name_problem("a:b.txt"))
        self.assertIsNotNone(st.windows_name_problem("CON.txt"))
        self.assertIsNotNone(st.windows_name_problem("fim."))

    def test_list_remote_dirs_first(self):
        ch = st.SshFileChannel(self.opener)
        ch.transfer(st.UPLOAD, [str(self.local / "pasta")], "/home")
        path, items = ch.list_remote("/home/pasta")
        self.assertEqual(path, "/home/pasta")
        self.assertEqual([i["name"] for i in items], ["sub", "a.txt"])
        self.assertEqual(ch.home(), "/home")


class RegistryTests(Base):
    def wait(self, reg, tid):
        for _ in range(200):
            status = reg.status(tid)
            if status["state"] != "RUNNING":
                return status
            time.sleep(0.02)
        self.fail("transferencia nao terminou")

    def test_done_conflict_and_recent(self):
        reg = st.TransferRegistry(self.opener)
        first = reg.start(st.UPLOAD, [str(self.local / "solto.txt")], "/home", origin="IA")
        self.assertEqual(self.wait(reg, first["id"])["state"], "DONE")
        second = reg.start(st.UPLOAD, [str(self.local / "solto.txt")], "/home")
        status = self.wait(reg, second["id"])
        self.assertEqual(status["state"], "CONFLICT")
        self.assertEqual(status["conflicts"], ["/home/solto.txt"])
        recent = reg.recent(5)
        self.assertEqual([r["id"] for r in recent], [second["id"], first["id"]])
        self.assertEqual(recent[1]["origin"], "IA")
        with self.assertRaises(KeyError):
            reg.status("nada")


class UiTests(Base):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_hostkey_box_states(self):
        from ssh_hostkey_box import HostKeyBox
        answers = []
        box = HostKeyBox(confirm=lambda info: answers.pop(0))
        emitted = []
        box.accept_requested.connect(lambda info, replace: emitted.append(replace))
        base = {"host": "srv", "port": 22, "key_type": "ssh-ed25519", "fingerprint": "SHA256:x"}
        box.show_info(dict(base, state="UNKNOWN"))
        self.assertFalse(box.accept_btn.isHidden())
        self.assertTrue(box.replace_btn.isHidden())
        self.assertIn("SHA256:x", box.details.text())
        self.assertIn("ssh_host_ed25519_key.pub", box.details.text())
        box.accept_btn.click()
        self.assertEqual(emitted, [False])
        box.show_info(dict(base, state="CHANGED", known_fingerprints={"ssh-ed25519": "SHA256:old"}))
        self.assertTrue(box.accept_btn.isHidden())
        self.assertFalse(box.replace_btn.isHidden())
        self.assertIn("SHA256:old", box.details.text())
        answers.extend([False, True])
        box.replace_btn.click()
        self.assertEqual(emitted, [False])
        box.replace_btn.click()
        self.assertEqual(emitted, [False, True])
        box.show_info(dict(base, state="TRUSTED"))
        self.assertTrue(box.accept_btn.isHidden())
        self.assertTrue(box.replace_btn.isHidden())

    def test_transfer_panel_send_and_conflict_retry(self):
        from ssh_transfer_panel import SshTransferPanel

        class Reg:
            def __init__(self):
                self.calls = []
                self.states = {}

            def start(self, direction, sources, destination, overwrite=False, origin="TELA"):
                tid = str(len(self.calls))
                self.calls.append((direction, sources, destination, overwrite, origin))
                self.states[tid] = {"id": tid, "state": "RUNNING", "direction": direction,
                                    "sources": sources, "destination": destination}
                return self.states[tid]

            def status(self, tid):
                return self.states[tid]

            def cancel(self, tid):
                return True

            def recent(self, n):
                return []

        reg = Reg()
        panel = SshTransferPanel(reg, lambda: st.SshFileChannel(self.opener),
                                 ask_overwrite=lambda conflicts: True,
                                 local_start=str(self.local))
        panel.timer.stop()
        names = [panel.local.list.item(i).text() for i in range(panel.local.list.count())]
        self.assertTrue(names[0].startswith("pasta"))
        panel.remote.path.setText("/home")
        panel.local.list.item(0).setSelected(True)
        panel.send_selected()
        self.assertEqual(reg.calls[0][:4], ("UPLOAD", [str(self.local / "pasta")], "/home", False))
        self.assertEqual(reg.calls[0][4], "TELA")
        self.assertFalse(panel.local.action_btn.isEnabled())
        reg.states["0"] = dict(reg.states["0"], state="CONFLICT", conflicts=["/home/pasta/a.txt"])
        panel._poll()
        self.assertEqual(reg.calls[1][3], True)
        reg.states["1"] = dict(reg.states["1"], state="DONE",
                               result={"files": 2, "bytes": 10, "skipped": []})
        panel._poll()
        self.assertTrue(panel.local.action_btn.isEnabled())
        self.assertIn("Pronto: 2 arquivos", panel.progress_label.text())
        panel.close()


if __name__ == "__main__":
    unittest.main()