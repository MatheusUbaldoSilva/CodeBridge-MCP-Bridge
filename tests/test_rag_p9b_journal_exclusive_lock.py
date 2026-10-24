import multiprocessing
import os
import queue
import tempfile
import unittest
from pathlib import Path

from installer.rag_p9b_journal_exclusive_lock import exclusive_journal_lock


def lock_worker(path, gate, result):
    with exclusive_journal_lock(path):
        result.put("entered")
        gate.wait(8)


def hard_crash_lock_worker(path, result):
    with exclusive_journal_lock(path):
        result.put("acquired")
        result.close()
        result.join_thread()
        os._exit(91)

class ExclusiveLockTests(unittest.TestCase):
    def test_lock_sidecar_survives_reentry(self):
        with tempfile.TemporaryDirectory() as root:
            journal=Path(root)/"transaction.jsonl"
            with exclusive_journal_lock(journal):
                self.assertTrue(journal.with_name(journal.name+".lock").is_file())
            with exclusive_journal_lock(journal):
                pass

    def test_parallel_process_waits_for_release(self):
        with tempfile.TemporaryDirectory() as root:
            ctx=multiprocessing.get_context("spawn")
            path=str(Path(root)/"transaction.jsonl")
            gate=ctx.Event()
            result=ctx.Queue()
            process=ctx.Process(target=lock_worker,args=(path,gate,result))
            process.start()
            try:
                self.assertEqual(result.get(timeout=10),"entered")
                self.assertTrue(process.is_alive())
                gate.set()
                process.join(timeout=12)
                self.assertEqual(process.exitcode,0)
                with exclusive_journal_lock(path):
                    pass
            finally:
                gate.set()
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

    def test_second_process_cannot_enter_held_lock(self):
        with tempfile.TemporaryDirectory() as root:
            ctx=multiprocessing.get_context("spawn")
            path=str(Path(root)/"transaction.jsonl")
            gate=ctx.Event()
            result=ctx.Queue()
            with exclusive_journal_lock(path):
                process=ctx.Process(target=lock_worker,args=(path,gate,result))
                process.start()
                try:
                    with self.assertRaises(queue.Empty):
                        result.get(timeout=0.5)
                    self.assertTrue(process.is_alive())
                finally:
                    gate.set()
            process.join(timeout=10)
            self.assertEqual(process.exitcode,0)
            self.assertEqual(result.get(timeout=5),"entered")
    def test_hard_crash_releases_os_lock(self):
        with tempfile.TemporaryDirectory() as root:
            ctx=multiprocessing.get_context("spawn")
            path=str(Path(root)/"recovery.jsonl")
            result=ctx.Queue()
            process=ctx.Process(target=hard_crash_lock_worker,args=(path,result))
            process.start()
            try:
                self.assertEqual(result.get(timeout=10),"acquired")
                process.join(timeout=10)
                self.assertEqual(process.exitcode,91)
                with exclusive_journal_lock(path):
                    self.assertTrue(Path(path+".lock").is_file())
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
    def test_symlink_sidecar_refused(self):
        with tempfile.TemporaryDirectory() as root:
            a=Path(root)/"journal.jsonl"
            b=Path(root)/"other"
            b.write_bytes(b"x")
            try:
                a.with_name(a.name+".lock").symlink_to(b)
            except (OSError,NotImplementedError):
                self.skipTest("symlinks not permitted on this filesystem")
            with self.assertRaisesRegex(ValueError,"JOURNAL_LOCK_PATH_INVALID"):
                with exclusive_journal_lock(a):
                    pass