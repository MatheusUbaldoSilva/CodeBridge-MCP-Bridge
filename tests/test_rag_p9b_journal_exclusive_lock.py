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

def crashing_owner_worker(path, ready, die):
    with exclusive_journal_lock(path):
        ready.set()
        die.wait(10)
        os._exit(92)


def waiting_worker(path, done):
    with exclusive_journal_lock(path):
        done.put("recovered")

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
    def test_blocked_waiter_proceeds_after_owner_crash(self):
        with tempfile.TemporaryDirectory() as root:
            ctx=multiprocessing.get_context("spawn")
            path=str(Path(root)/"recovery.jsonl")
            ready=ctx.Event()
            die=ctx.Event()
            done=ctx.Queue()
            owner=ctx.Process(target=crashing_owner_worker,args=(path,ready,die))
            waiter=ctx.Process(target=waiting_worker,args=(path,done))
            owner.start()
            try:
                self.assertTrue(ready.wait(10))
                waiter.start()
                with self.assertRaises(queue.Empty):
                    done.get(timeout=0.5)
                self.assertTrue(waiter.is_alive())
                die.set()
                owner.join(timeout=10)
                self.assertEqual(owner.exitcode,92)
                self.assertEqual(done.get(timeout=10),"recovered")
                waiter.join(timeout=10)
                self.assertEqual(waiter.exitcode,0)
            finally:
                die.set()
                for process in (owner,waiter):
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