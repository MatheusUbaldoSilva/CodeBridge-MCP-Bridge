import tempfile
import unittest
from pathlib import Path
from installer.rag_p9b_external_lab_postverify import verify

class ExternalLabVerifyGuardTests(unittest.TestCase):
    def test_refuses_arbitrary_root(self):
        with tempfile.TemporaryDirectory() as root:
            r=verify(lab=root,snapshot="none",shell_snapshot="none",
                     appdata=root,desktop=root,registry_token="none",snapshot_sha256="0"*64,shell_sha256="0"*64,journal="none")
            self.assertEqual(r["reason"],"SCRATCH_LAB_ONLY")
    def test_refuses_invalid_token(self):
        with tempfile.TemporaryDirectory() as root:
            lab=Path(root)/"disposable"
            lab.mkdir()
            r=verify(lab=lab,snapshot="none",shell_snapshot="none",
                     appdata=lab,desktop=lab,registry_token="none",snapshot_sha256="0"*64,shell_sha256="0"*64,journal="none")
            self.assertEqual(r["reason"],"REGISTRY_TOKEN_INVALID")
    def test_refuses_bad_artifact_identity(self):
        import uuid
        with tempfile.TemporaryDirectory() as root:
            lab=Path(root)/"disposable"
            lab.mkdir()
            r=verify(lab=lab,snapshot="none",shell_snapshot="none",
                appdata=lab,desktop=lab,registry_token=uuid.uuid4().hex,
                snapshot_sha256="bad",shell_sha256="0"*64,journal="none")
            self.assertEqual(r["reason"],"ARTIFACT_IDENTITY_INVALID")

    def test_refuses_missing_journal_after_valid_artifacts(self):
        import hashlib,uuid
        with tempfile.TemporaryDirectory() as root:
            lab=Path(root)/"disposable"
            lab.mkdir()
            a=Path(root)/"a.zip"
            b=Path(root)/"b.zip"
            a.write_bytes(b"zip-a")
            b.write_bytes(b"zip-b")
            r=verify(lab=lab,snapshot=a,shell_snapshot=b,
                appdata=lab,desktop=lab,registry_token=uuid.uuid4().hex,
                snapshot_sha256=hashlib.sha256(a.read_bytes()).hexdigest(),
                shell_sha256=hashlib.sha256(b.read_bytes()).hexdigest(),
                journal=Path(root)/"missing.jsonl")
            self.assertEqual(r["reason"],"JOURNAL_CHAIN_INCOMPLETE")

    def test_refuses_mismatched_archive_hash(self):
        import hashlib,uuid
        with tempfile.TemporaryDirectory() as root:
            lab=Path(root)/"disposable"
            lab.mkdir()
            a=Path(root)/"archive-a.zip"
            b=Path(root)/"archive-b.zip"
            a.write_bytes(b"backup-a")
            b.write_bytes(b"backup-b")
            r=verify(lab=lab,snapshot=a,shell_snapshot=b,
                appdata=lab,desktop=lab,registry_token=uuid.uuid4().hex,
                snapshot_sha256="f"*64,
                shell_sha256=hashlib.sha256(b.read_bytes()).hexdigest(),
                journal=Path(root)/"not-used.jsonl")
            self.assertEqual(r["reason"],"ARTIFACT_DIGEST_MISMATCH")

if __name__=="__main__":unittest.main()
