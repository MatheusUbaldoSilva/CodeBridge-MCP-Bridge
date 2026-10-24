import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_scheduled_combined_retry_adapter import run_lab_retry


class ScheduledCombinedRetryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.lab=self.root/"disposable"
        self.lab.mkdir()
        self.config=self.root/"config.json"
        self.appdata=self.lab/"appdata"
        self.desktop=self.lab/"desktop"
        self.appdata.mkdir()
        self.desktop.mkdir()
        self.backups={}
        for name in ("snapshot","shell_snapshot","preimage"):
            source=self.root/(name+".bin")
            source.write_bytes(name.encode())
            self.backups[name]=str(source)
        self.config.write_text(json.dumps({
            "lab":str(self.lab), "appdata":str(self.appdata),
            "desktop":str(self.desktop), "installed":str(self.root/"installed"),
            "journal":str(self.root/"combined.jsonl"),
            "token":"b"*32, **self.backups}),encoding="utf-8")
        self.ledger=self.root/"retry.json"
        self.sha=hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.calls=0

    def invoke(self, worker=None, **changes):
        args=dict(config=self.config,retry_ledger=self.ledger,
                  transaction_sha256=self.sha,temp_root=self.root,
                  worker=worker or self.ok)
        args.update(changes)
        return run_lab_retry(**args)

    def ok(self, cfg):
        self.calls+=1
        self.assertEqual(Path(cfg),self.config)
        return {"verified":True,"production_modified":False}

    def test_success_is_durable_and_second_invoke_is_denied(self):
        first=self.invoke()
        self.assertTrue(first["verified"],first)
        self.assertEqual(first["attempt"],1)
        second=self.invoke()
        self.assertFalse(second["verified"])
        self.assertEqual(second["reason"],"DURABLE_TERMINAL_STATE")
        self.assertEqual(self.calls,1)
        self.assertEqual(json.loads(self.ledger.read_text())["attempts"],1)

    def test_two_failures_then_success_with_three_attempts(self):
        def worker(_):
            self.calls+=1
            if self.calls<3:
                return {"verified":False,"production_modified":False}
            return {"verified":True,"production_modified":False}
        self.assertFalse(self.invoke(worker=worker)["verified"])
        self.assertFalse(self.invoke(worker=worker)["verified"])
        proof=self.invoke(worker=worker)
        self.assertTrue(proof["verified"])
        self.assertEqual(proof["attempt"],3)
        self.assertEqual(self.invoke(worker=worker)["reason"],"DURABLE_TERMINAL_STATE")
        self.assertEqual(self.calls,3)

    def test_three_failures_block_fourth(self):
        for _ in range(3):
            self.assertEqual(self.invoke(worker=lambda _:{"verified":False,
                                  "production_modified":False})["reason"],
                             "COMBINED_RECOVERY_UNVERIFIED")
        self.assertEqual(self.invoke()["reason"],"RETRY_BUDGET_EXHAUSTED")
        self.assertEqual(self.calls,0)

    def test_claimed_success_modifying_production_refused(self):
        outcome=self.invoke(worker=lambda _:{"verified":True,"production_modified":True})
        self.assertEqual(outcome["reason"],"WORKER_PRODUCTION_SCOPE_UNVERIFIED")
        self.assertEqual(json.loads(self.ledger.read_text())["state"],"READY")

    def test_worker_exception_fails_closed(self):
        def fault(_):
            raise ValueError("test")
        self.assertEqual(self.invoke(worker=fault)["reason"],"LAB_RETRY_EXECUTION_FAILED")
        self.assertEqual(json.loads(self.ledger.read_text())["attempts"],1)

    def test_outside_config_no_reservation(self):
        result=self.invoke(config=Path(self.root.anchor)/"unsafe-config")
        self.assertEqual(result["reason"],"LAB_CONFIG_OR_LEDGER_SCOPE_INVALID")
        self.assertFalse(self.ledger.exists())

    def test_untrusted_lab_path_no_reservation(self):
        self.config.write_text(json.dumps({"lab":str(self.root)}),encoding="utf-8")
        self.sha=hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.assertEqual(self.invoke()["reason"],"DISPOSABLE_ROOT_REQUIRED")
        self.assertFalse(self.ledger.exists())

    def test_incomplete_config_does_not_reserve(self):
        self.config.write_text(json.dumps({"lab":str(self.lab)}),encoding="utf-8")
        self.sha=hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.assertEqual(self.invoke()["reason"],"RECOVERY_CONFIGURATION_INCOMPLETE")
        self.assertFalse(self.ledger.exists())

    def test_outside_backup_rejected(self):
        config=json.loads(self.config.read_text())
        config["snapshot"]=str(Path(self.root.anchor)/"outside.zip")
        self.config.write_text(json.dumps(config),encoding="utf-8")
        self.sha=hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.assertEqual(self.invoke()["reason"],"BACKUP_OUTSIDE_SCRATCH")
        self.assertFalse(self.ledger.exists())

    def test_config_symlink_lab_rejected(self):
        alias=self.root/"lab_alias"
        try:
            alias.symlink_to(self.lab,target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest("symlink unavailable")
        config=json.loads(self.config.read_text())
        config["lab"]=str(alias)
        self.config.write_text(json.dumps(config),encoding="utf-8")
        self.sha=hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.assertEqual(self.invoke()["reason"],"DISPOSABLE_ROOT_REQUIRED")
        self.assertFalse(self.ledger.exists())

    def test_outside_shell_rejected(self):
        config=json.loads(self.config.read_text())
        config["desktop"]=str(self.root)
        self.config.write_text(json.dumps(config),encoding="utf-8")
        self.sha=hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.assertEqual(self.invoke()["reason"],"SHELL_OUTSIDE_SCRATCH")
        self.assertFalse(self.ledger.exists())
    def test_config_mutation_during_worker_prevents_terminal(self):
        def mutating_worker(_):
            self.calls += 1
            self.config.write_bytes(self.config.read_bytes()+b" ")
            return {"verified":True,"production_modified":False}
        result=self.invoke(worker=mutating_worker)
        self.assertEqual(result["reason"],"CONFIG_CHANGED_DURING_WORKER")
        self.assertFalse(result["verified"])
        self.assertEqual(self.calls,1)
        self.assertEqual(json.loads(self.ledger.read_text())["attempts"],1)
        self.assertNotEqual(json.loads(self.ledger.read_text())["state"],"TERMINAL")

    def test_config_deleted_by_worker_refuses_terminal(self):
        def deleting_worker(_):
            self.config.unlink()
            return {"verified":True,"production_modified":False}
        result=self.invoke(worker=deleting_worker)
        self.assertEqual(result["reason"],"LAB_RETRY_EXECUTION_FAILED")
        self.assertNotEqual(json.loads(self.ledger.read_text())["state"],"TERMINAL")
    def test_config_mutation_after_binding_denied_without_reserve(self):
        raw=json.loads(self.config.read_text())
        raw["extra_untrusted_field"]="changed"
        self.config.write_text(json.dumps(raw),encoding="utf-8")
        self.assertEqual(self.invoke()["reason"],"TRANSACTION_CONFIG_SHA_MISMATCH")
        self.assertFalse(self.ledger.exists())
    def test_digest_substitution_rejected(self):
        self.assertTrue(self.invoke()["verified"])
        self.assertEqual(self.invoke(transaction_sha256="b"*64)["reason"],
                         "TRANSACTION_CONFIG_SHA_MISMATCH")
        self.assertEqual(self.calls,1)


if __name__=="__main__":
    unittest.main()