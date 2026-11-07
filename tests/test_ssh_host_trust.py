"""Aceite de fingerprint SSH: primeira conexao, chave trocada e known_hosts."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
import paramiko
import ssh_host_trust as trust

KEY_A = paramiko.ECDSAKey.generate()
KEY_B = paramiko.ECDSAKey.generate()


def fetcher(key, seen=None):
    def fetch(host, port, timeout, prefer):
        if seen is not None:
            seen.append(list(prefer))
        return key
    return fetch


class HostTrustTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / ".ssh" / "known_hosts"

    def tearDown(self):
        self.tmp.cleanup()

    def test_label_and_fingerprint(self):
        self.assertEqual(trust.host_label("h", 22), "h")
        self.assertEqual(trust.host_label("h", 2222), "[h]:2222")
        self.assertTrue(trust.fingerprint(KEY_A).startswith("SHA256:"))
        self.assertNotIn("=", trust.fingerprint(KEY_A))

    def test_first_connection_is_unknown_then_accepted(self):
        info = trust.check("srv", 22, path=self.path, fetch=fetcher(KEY_A))
        self.assertEqual(info["state"], trust.UNKNOWN)
        done = trust.accept("srv", 22, info["fingerprint"], path=self.path, fetch=fetcher(KEY_A))
        self.assertEqual(done["state"], trust.TRUSTED)
        self.assertIn("srv " + KEY_A.get_name(), self.path.read_text(encoding="utf-8"))
        again = trust.check("srv", 22, path=self.path, fetch=fetcher(KEY_A))
        self.assertEqual(again["state"], trust.TRUSTED)

    def test_accept_refuses_other_fingerprint(self):
        with self.assertRaises(ValueError):
            trust.accept("srv", 22, "SHA256:outra", path=self.path, fetch=fetcher(KEY_A))
        self.assertFalse(self.path.exists())

    def test_custom_port_uses_bracket_label(self):
        info = trust.check("srv", 2222, path=self.path, fetch=fetcher(KEY_A))
        trust.accept("srv", 2222, info["fingerprint"], path=self.path, fetch=fetcher(KEY_A))
        self.assertIn("[srv]:2222 ", self.path.read_text(encoding="utf-8"))
        self.assertEqual(trust.check("srv", 22, path=self.path, fetch=fetcher(KEY_A))["state"],
                         trust.UNKNOWN)

    def test_changed_key_blocks_until_replace(self):
        self.path.parent.mkdir(parents=True)
        hashed = paramiko.HostKeys.hash_host("srv")
        self.path.write_text(
            "# comentario do usuario\n"
            f"outro {KEY_A.get_name()} {KEY_A.get_base64()}\n"
            f"srv {KEY_A.get_name()} {KEY_A.get_base64()}\n"
            f"{hashed} {KEY_A.get_name()} {KEY_A.get_base64()}",
            encoding="utf-8")
        info = trust.check("srv", 22, path=self.path, fetch=fetcher(KEY_B))
        self.assertEqual(info["state"], trust.CHANGED)
        self.assertIn(KEY_A.get_name(), info["known_fingerprints"])
        with self.assertRaises(PermissionError):
            trust.accept("srv", 22, info["fingerprint"], path=self.path, fetch=fetcher(KEY_B))
        done = trust.accept("srv", 22, info["fingerprint"], replace=True,
                            path=self.path, fetch=fetcher(KEY_B))
        self.assertEqual(done["state"], trust.TRUSTED)
        self.assertEqual(done["removed_entries"], 2)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("# comentario do usuario", text)
        self.assertIn("outro ", text)
        self.assertIn(KEY_B.get_base64(), text)
        self.assertEqual(text.count(KEY_A.get_base64()), 1)
        backup = self.path.with_name(self.path.name + trust.BACKUP_SUFFIX)
        self.assertEqual(backup.read_text(encoding="utf-8").count(KEY_A.get_base64()), 3)

    def test_known_type_is_requested_first(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(f"srv ssh-rsa {paramiko.RSAKey.generate(1024).get_base64()}\n",
                             encoding="utf-8")
        seen = []
        info = trust.check("srv", 22, path=self.path, fetch=fetcher(KEY_A, seen))
        self.assertEqual(seen[0][0], "rsa-sha2-512")
        self.assertEqual(info["state"], trust.CHANGED)


if __name__ == "__main__":
    unittest.main()