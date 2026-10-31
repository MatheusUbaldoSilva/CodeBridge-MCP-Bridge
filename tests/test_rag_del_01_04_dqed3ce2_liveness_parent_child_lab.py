"""DQ-E-D-3C-E-2: kill parent/child on Windows and verify scratch locks."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time

from rag.runtime.production_generation_lock import (
    production_generation_lock,ProductionGenerationBusy,
)
from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    bounded_catalog_mutex_lab,LaboratoryCatalogBusy,
)


_WRITER = r"""
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock,ProductionGenerationBusy
import sys
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"CodeBridge"/"rag"/"rag_index.sqlite3"):
    try:
        with production_generation_lock(exclusive=True,channel="generation"):
            print("WRITER_ALLOWED")
    except ProductionGenerationBusy:
        print("WRITER_BUSY")
"""


class ParentChildLivenessWin32LabTests(TestCase):
    def setUp(self):
        temporary=TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_liveness"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        self.vector_dir=self.db.parent/"qdrant"
        self.vector_dir.mkdir()
        self.vector=self.vector_dir/"vectors.bin"
        self.vector.write_bytes(b"qdrant-probe")
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.execute("INSERT INTO rag_documents VALUES ('private-lab','test.py')")
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"lab":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"liveness-v1",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.before=(self.catalog.read_bytes(),self.db.read_bytes(),
                     self.manifest.read_bytes(),self.vector.read_bytes())

    def start_parent(self):
        return subprocess.Popen(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,
        )

    def ready(self,proc):
        line=proc.stdout.readline().strip()
        self.assertTrue(line.startswith("PARENT_READY "),line)
        return int(line.split()[-1])

    def writer(self):
        return subprocess.run(
            [sys.executable,"-c",_WRITER,str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=8,
        )

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def assert_original_artifacts(self):
        self.assertEqual(
            (self.catalog.read_bytes(),self.db.read_bytes(),
             self.manifest.read_bytes(),self.vector.read_bytes()),
            self.before,
        )

    def test_clean_parent_ack_child_response_and_lock_release(self):
        parent=self.start_parent()
        try:
            child_pid=self.ready(parent)
            self.assertGreater(child_pid,0)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            result,error=parent.communicate(input="ACK\n",timeout=8)
            self.assertEqual(parent.returncode,0,error)
            self.assertIn("PARENT_CONFIRMED",result)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
            self.assertFalse((self.root/"lab-child-termination.json").exists())
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_killed_parent_closes_pipe_child_fails_and_locks_release(self):
        parent=self.start_parent()
        marker=self.root/"lab-child-termination.json"
        try:
            child_pid=self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            parent.kill()
            parent.communicate(timeout=5)
            self.assertNotEqual(parent.returncode,0)
            # Existence can precede a completed JSON write on Windows.
            # Wait for a valid marker without weakening the required state.
            marker_state=None
            for _ in range(150):
                if marker.is_file():
                    try:
                        marker_state=json.loads(marker.read_text())["state"]
                    except (json.JSONDecodeError,KeyError,OSError):
                        marker_state=None
                    if marker_state is not None:
                        break
                time.sleep(0.03)
            self.assertIn(marker_state,
                          {"PARENT_PIPE_CLOSED","PARENT_PROCESS_EXITED"})
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_killed_child_is_fail_closed_and_parent_unlocks(self):
        parent=self.start_parent()
        try:
            child_pid=self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            os.kill(child_pid,signal.SIGTERM)
            out,err=parent.communicate(input="ACK\n",timeout=8)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_vector_tamper_during_child_wait_rejected_after_ack(self):
        parent=self.start_parent()
        marker=self.root/"lab-child-termination.json"
        try:
            self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            self.vector.write_bytes(b"DIFFERENT___")
            out,err=parent.communicate(input="ACK\n",timeout=8)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertTrue(marker.is_file())
            self.assertEqual(json.loads(marker.read_text())["state"],
                             "CHILD_VECTOR_DRIFT")
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
            self.vector.write_bytes(self.before[3])
        self.assert_original_artifacts()

    def test_wrong_ack_does_not_complete_semantic_session(self):
        parent=self.start_parent()
        try:
            self.ready(parent)
            out,err=parent.communicate(input="INVALID\n",timeout=8)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)

    def test_parent_rejects_non_scratch_root_before_spawn(self):
        parent=subprocess.run(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(Path.home())],
            cwd=str(Path(__file__).resolve().parents[1]),
            input="",capture_output=True,text=True,timeout=8,
        )
        self.assertNotEqual(parent.returncode,0)
        self.assertNotIn("PARENT_READY",parent.stdout)

    def test_parent_ack_deadline_releases_all_locks(self):
        parent=self.start_parent()
        try:
            self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            # Parent must timeout on its own, not wait indefinitely on stdin.
            parent.wait(timeout=9)
            parent.communicate(timeout=3)
            self.assertNotEqual(parent.returncode,0)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_child_refuses_existing_evidence_path_not_overwritten(self):
        marker=self.root/"lab-child-termination.json"
        marker.write_text('{"protected":true}',encoding="utf-8")
        parent=self.start_parent()
        try:
            self.ready(parent)
            parent.kill()
            parent.communicate(timeout=5)
            for _ in range(100):
                if self.writer().stdout.find("WRITER_ALLOWED")>=0: break
                time.sleep(0.02)
            self.assertEqual(marker.read_text(encoding="utf-8"),
                             '{"protected":true}')
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)


    def test_worker_supervised_mode_never_falls_back_to_semantic_model(self):
        from rag.runtime import isolated_project_worker
        from unittest.mock import patch
        with (
            patch.object(sys,"argv",[
                "worker","--pinned-scratch-supervised",str(self.root),"12345","123456789",
            ]),
            patch.object(isolated_project_worker,"resolve_isolated_project",
                         side_effect=AssertionError("legacy catalog resolver used")),
            patch.object(isolated_project_worker,"search_persistent_semantic",
                         side_effect=AssertionError("actual model invoked")),
            patch("rag.runtime.knowledge_deletion_liveness_child_lab.run_supervised_scratch_child_lab")
            as supervised,
        ):
            isolated_project_worker.main()
        supervised.assert_called_once_with(str(self.root),"12345","123456789")

    def test_worker_supervised_mode_rejects_invalid_cli_arity_and_self_pid(self):
        from rag.runtime import isolated_project_worker
        from unittest.mock import patch
        for argv in (
            ["worker","--pinned-scratch-supervised"],
            ["worker","--pinned-scratch-supervised",str(self.root)],
            ["worker","--pinned-scratch-supervised",str(self.root),"not-a-pid","12345"],
            ["worker","--pinned-scratch-supervised",str(self.root),str(os.getpid()),"12345"],
            ["worker","--pinned-scratch-supervised",str(self.root),"0","12345"],
            ["worker","--pinned-scratch-supervised",str(self.root),"123","extra"],
            ["worker","--pinned-scratch-supervised",str(self.root),"123","12345","extra"],
        ):
            with self.subTest(argv=argv):
                with (
                    patch.object(sys,"argv",argv),
                    patch.object(isolated_project_worker,"resolve_isolated_project",
                                 side_effect=AssertionError("legacy resolver reached")),
                ):
                    with self.assertRaises(PermissionError):
                        isolated_project_worker.main()

    def test_exact_response_correlation_refuses_replay_and_cross_project(self):
        from types import SimpleNamespace
        from rag.runtime.knowledge_deletion_liveness_parent_lab import (
            validate_supervised_scratch_response_lab,
        )
        pin=SimpleNamespace(project_id="private-lab",generation_id="private_liveness",
                            nonce="a"*32)
        request=SimpleNamespace(pin=pin,request_digest=lambda:"b"*64)
        receipt=SimpleNamespace(tree_sha256="c"*64)
        valid={
            "state":"LAB_CHILD_COMPLETED_WHILE_PARENT_PIPE_OPEN",
            "project_id":pin.project_id,
            "generation_id":pin.generation_id,
            "nonce":pin.nonce,
            "request_sha256":request.request_digest(),
            "tree_sha256":receipt.tree_sha256,
            "challenge_sha256":"d"*64,
            "operational_use_allowed":False,
            "activation_authorized":False,
        }
        validate_supervised_scratch_response_lab(valid,request,receipt,"d"*64)
        for key,value in (
            ("project_id","foreign-lab"),
            ("generation_id","replayed-generation"),
            ("nonce","0"*32),
            ("request_sha256","0"*64),
            ("tree_sha256","0"*64),
            ("challenge_sha256","0"*64),
            ("state","LAB_OPERATIONAL_SUCCESS"),
            ("operational_use_allowed",True),
            ("activation_authorized",True),
            ("extra",123),
        ):
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError,"response mismatch"):
                    validate_supervised_scratch_response_lab(
                        {**valid,key:value},request,receipt,"d"*64,
                    )
        for malformed in (None,[],{"state":"LAB_CHILD_COMPLETED_WHILE_PARENT_PIPE_OPEN"}):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(RuntimeError,"response mismatch"):
                    validate_supervised_scratch_response_lab(
                        malformed,request,receipt,"d"*64,
                    )

    def test_journal_appearing_during_supervised_child_wait_fails_closed(self):
        parent=self.start_parent()
        journal=self.root/"rag-del-supervised-race.journal.json"
        try:
            self.ready(parent)
            self.assertIn("WRITER_BUSY",self.writer().stdout)
            journal.write_text('{"state":"ROLLED_BACK"}',encoding="utf-8")
            out,err=parent.communicate(input="ACK\n",timeout=9)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertTrue(journal.exists())
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
            journal.unlink(missing_ok=True)
        self.assert_original_artifacts()

    def test_catalog_change_during_supervised_child_wait_rejected(self):
        parent=self.start_parent()
        original=self.catalog.read_bytes()
        try:
            self.ready(parent)
            mutated=json.loads(original)
            mutated["projects"]["private-lab"]["source_revision"]="changed"
            self.catalog.write_text(json.dumps(mutated),encoding="utf-8")
            out,err=parent.communicate(input="ACK\n",timeout=9)
            self.assertNotEqual(parent.returncode,0,(out,err))
            self.assertNotIn("PARENT_CONFIRMED",out)
            self.assertIn("WRITER_ALLOWED",self.writer().stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
            self.catalog.write_bytes(original)
        self.assert_original_artifacts()


    def test_one_shot_scratch_ack_parser_rejects_reused_nonce_and_bad_challenges(self):
        from hashlib import sha256
        from rag.runtime.knowledge_deletion_liveness_child_lab import (
            _parse_one_shot_scratch_ack_lab,
        )
        nonce="a"*32
        one="b"*64
        good="ACK "+nonce+" "+one+"\n"
        digest=_parse_one_shot_scratch_ack_lab(good,nonce)
        self.assertEqual(digest,sha256(bytes.fromhex(one)).hexdigest())
        for invalid in (
            "ACK "+nonce+"\n",
            "ACK "+nonce+" "+("c"*63)+"\n",
            "ACK "+nonce+" "+("C"*64)+"\n",
            "ACK "+nonce+" "+("g"*64)+"\n",
            "ACK "+("0"*32)+" "+one+"\n",
            "ACK "+nonce+" "+one,
            "ACK "+nonce+" "+one+"\nEXTRA",
            "INVALID\n",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _parse_one_shot_scratch_ack_lab(invalid,nonce)

    def test_replayed_response_rejected_even_if_envelope_nonce_is_same(self):
        from hashlib import sha256
        from types import SimpleNamespace
        from rag.runtime.knowledge_deletion_liveness_parent_lab import (
            validate_supervised_scratch_response_lab,
        )
        pin=SimpleNamespace(project_id="private-lab",generation_id="private_liveness",
                            nonce="a"*32)
        request=SimpleNamespace(pin=pin,request_digest=lambda:"b"*64)
        receipt=SimpleNamespace(tree_sha256="c"*64)
        first=sha256(bytes.fromhex("d"*64)).hexdigest()
        next_challenge=sha256(bytes.fromhex("e"*64)).hexdigest()
        stale={
            "state":"LAB_CHILD_COMPLETED_WHILE_PARENT_PIPE_OPEN",
            "project_id":pin.project_id,
            "generation_id":pin.generation_id,
            "nonce":pin.nonce,
            "request_sha256":request.request_digest(),
            "tree_sha256":receipt.tree_sha256,
            "challenge_sha256":first,
            "operational_use_allowed":False,
            "activation_authorized":False,
        }
        validate_supervised_scratch_response_lab(stale,request,receipt,first)
        with self.assertRaisesRegex(RuntimeError,"response mismatch"):
            validate_supervised_scratch_response_lab(
                stale,request,receipt,next_challenge,
            )


    def test_pinned_parent_birth_roundtrip_survives_venv_redirector(self):
        from rag.runtime.knowledge_deletion_parent_identity_lab import (
            current_process_creation_filetime_lab,
        )
        birth=current_process_creation_filetime_lab()
        self.assertGreater(birth,0)
        # Venv redirector may be immediate OS parent, yet the provided
        # intended parent PID and immutable birth time must be verified.
        code=(
            "import sys;"
            "from rag.runtime.knowledge_deletion_parent_identity_lab import "
            "open_pinned_parent_identity_lab,held_parent_still_alive_lab,"
            "close_parent_identity_lab;"
            "identity=open_pinned_parent_identity_lab(sys.argv[1],sys.argv[2]);"
            "assert held_parent_still_alive_lab(identity);"
            "close_parent_identity_lab(identity);"
            "print('IDENTITY_MATCH')"
        )
        result=subprocess.run(
            [sys.executable,"-c",code,str(os.getpid()),str(birth)],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=8,
        )
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("IDENTITY_MATCH",result.stdout)

    def test_wrong_parent_birth_is_refused_for_direct_child(self):
        from rag.runtime.knowledge_deletion_parent_identity_lab import (
            current_process_creation_filetime_lab,
        )
        birth=current_process_creation_filetime_lab()
        code=(
            "import sys;"
            "from rag.runtime.knowledge_deletion_parent_identity_lab import "
            "open_pinned_parent_identity_lab;"
            "open_pinned_parent_identity_lab(sys.argv[1],sys.argv[2])"
        )
        cases=(
            (str(os.getpid()),str(birth+1)),
            (str(os.getpid()),"wrong"),
            ("0",str(birth)),
            ("4294967295",str(birth)),
            (str(os.getppid()),str(birth)),
        )
        for pid,created in cases:
            with self.subTest(pid=pid,created=created):
                result=subprocess.run(
                    [sys.executable,"-c",code,pid,created],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True,text=True,timeout=8,
                )
                self.assertNotEqual(result.returncode,0)
                self.assertIn("ProcessIdentityLabError",result.stderr)

    def test_worker_supervised_rejects_correct_parent_pid_wrong_birth(self):
        from rag.runtime.knowledge_deletion_parent_identity_lab import (
            current_process_creation_filetime_lab,
        )
        birth=current_process_creation_filetime_lab()
        result=subprocess.run(
            [sys.executable,"-m","rag.runtime.isolated_project_worker",
             "--pinned-scratch-supervised",str(self.root),
             str(os.getpid()),str(birth+1)],
            cwd=str(Path(__file__).resolve().parents[1]),
            input="",capture_output=True,text=True,timeout=8,
        )
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn("CHILD_VERIFIED",result.stdout)
        self.assertIn("identity mismatch",result.stderr)


    def test_parent_times_out_if_child_never_finishes_preflight(self):
        # Parent owns generation + semantic locks while waiting for child.
        # After timeout it must kill/reap synthetic worker and release locks.
        result=subprocess.run(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(self.root),"--lab-hang-before-ready"],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=14,
        )
        self.assertNotEqual(result.returncode,0)
        self.assertIn("scratch child output timed out",result.stderr)
        self.assertNotIn("PARENT_CONFIRMED",result.stdout)
        writer=self.writer()
        self.assertEqual(writer.returncode,0,writer.stderr)
        self.assertIn("WRITER_ALLOWED",writer.stdout)
        self.assert_original_artifacts()

    def test_parent_times_out_if_child_hangs_after_ready(self):
        parent=subprocess.Popen(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(self.root),"--lab-hang-after-ready"],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.ready(parent)
            busy=self.writer()
            self.assertEqual(busy.returncode,0,busy.stderr)
            self.assertIn("WRITER_BUSY",busy.stdout)
            out,error=parent.communicate(input="ACK\n",timeout=14)
            self.assertNotEqual(parent.returncode,0)
            self.assertIn("scratch child output timed out",error)
            self.assertNotIn("PARENT_CONFIRMED",out)
            released=self.writer()
            self.assertEqual(released.returncode,0,released.stderr)
            self.assertIn("WRITER_ALLOWED",released.stdout)
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.communicate(timeout=4)
        self.assert_original_artifacts()

    def test_parent_rejects_unrecognized_synthetic_hang_flag(self):
        result=subprocess.run(
            [sys.executable,"-m",
             "rag.runtime.knowledge_deletion_liveness_parent_lab",
             str(self.root),"--lab-other-mode"],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=8,
        )
        self.assertNotEqual(result.returncode,0)
        self.assertIn("PermissionError",result.stderr)
        self.assertNotIn("PARENT_READY",result.stdout)
        self.assert_original_artifacts()
