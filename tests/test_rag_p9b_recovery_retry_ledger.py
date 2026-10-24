import json
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_recovery_retry_ledger import reserve_disposable_retry


def child_reserve(path, sha, result):
    result.put(reserve_disposable_retry(path, transaction_sha256=sha,
                                        temp_root=str(Path(path).parent)))


def crashing_worker(path, sha, output):
    result=reserve_disposable_retry(path, transaction_sha256=sha,
                                    temp_root=str(Path(path).parent))
    output.put(result)
    output.close()
    output.join_thread()
    os._exit(87)

class RetryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / "recovery.json"
        self.sha = "a" * 64

    def reserve(self, **overrides):
        args=dict(path=self.ledger, transaction_sha256=self.sha, temp_root=self.root)
        args.update(overrides)
        return reserve_disposable_retry(**args)

    def test_three_durable_attempts_then_review(self):
        for attempt in range(1, 4):
            result = self.reserve()
            self.assertTrue(result["reserved"], result)
            self.assertEqual(result["attempt"], attempt)
            self.assertFalse(result["cutover_authorized"])
        stopped = self.reserve()
        self.assertFalse(stopped["reserved"])
        self.assertEqual(stopped["state"], "P9B_RECOVERY_REVIEW_REQUIRED")
        self.assertEqual(json.loads(self.ledger.read_text())["attempts"], 3)

    def test_transaction_substitution_refused_without_update(self):
        self.reserve()
        before = self.ledger.read_bytes()
        self.assertEqual(self.reserve(transaction_sha256="b"*64)["reason"],
                         "LEDGER_IDENTITY_OR_SCHEMA_MISMATCH")
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_corrupt_json_refused(self):
        self.ledger.write_bytes(b"{bad json")
        before=self.ledger.read_bytes()
        self.assertEqual(self.reserve()["reason"], "LEDGER_UNVERIFIED")
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_duplicate_json_keys_refused(self):
        self.ledger.write_text('{"attempts":1,"attempts":2}', encoding="utf-8")
        self.assertEqual(self.reserve()["reason"], "LEDGER_UNVERIFIED")

    def test_scope_escape_refused(self):
        dest=Path(self.root.anchor)/"outside_p9b_retry.json"
        self.assertEqual(self.reserve(path=dest)["reason"], "RETRY_PATH_NOT_DISPOSABLE")

    def test_invalid_sha_refused(self):
        self.assertEqual(self.reserve(transaction_sha256="invalid")["reason"],
                         "TRANSACTION_SHA_INVALID")
        self.assertFalse(self.ledger.exists())

    def test_preexisting_temp_collision_refused_without_modification(self):
        self.ledger.with_name(self.ledger.name+".pending").write_bytes(b"unexpected")
        self.assertEqual(self.reserve()["reason"], "RETRY_TEMP_COLLISION")
        self.assertFalse(self.ledger.exists())

    def test_hard_crash_does_not_erase_reserved_attempt(self):
        ctx=multiprocessing.get_context("spawn")
        result=ctx.Queue()
        process=ctx.Process(target=crashing_worker,
                            args=(str(self.ledger),self.sha,result))
        process.start()
        try:
            response=result.get(timeout=12)
            self.assertEqual(response["attempt"],1)
            process.join(timeout=10)
            self.assertEqual(process.exitcode,87)
            resumed=self.reserve()
            self.assertTrue(resumed["reserved"])
            self.assertEqual(resumed["attempt"],2)
            self.assertEqual(json.loads(self.ledger.read_text())["attempts"],2)
        finally:
            if process.is_alive(): process.terminate()
            process.join(timeout=5)
    def test_two_processes_reserve_distinct_attempts(self):
        ctx=multiprocessing.get_context("spawn")
        result=ctx.Queue()
        processes=[ctx.Process(target=child_reserve,
                   args=(str(self.ledger),self.sha,result)) for _ in range(2)]
        try:
            for process in processes: process.start()
            outputs=[result.get(timeout=15) for _ in processes]
            self.assertEqual(sorted(x["attempt"] for x in outputs), [1,2])
            for process in processes:
                process.join(timeout=10)
                self.assertEqual(process.exitcode,0)
            self.assertEqual(json.loads(self.ledger.read_text())["attempts"],2)
        finally:
            for process in processes:
                if process.is_alive(): process.terminate()
                process.join(timeout=5)


if __name__=="__main__":
    unittest.main()