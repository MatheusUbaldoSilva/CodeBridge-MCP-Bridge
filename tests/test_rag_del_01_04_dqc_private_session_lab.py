"""RAG-DEL-01.04-DQ-C: scratch-only composite private reader guard tests."""
from contextlib import closing, contextmanager
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys

from rag.runtime.knowledge_deletion_private_read_session_lab import (
    private_read_session_lab, PrivateReadSessionLabError,
)
from rag.runtime.production_generation_lock import (
    production_generation_lock, ProductionGenerationBusy,
)
from rag.runtime.knowledge_deletion_bounded_catalog_lab import LaboratoryCatalogUnsafe


_CHILD_GENERATION = r"""
import sys
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"rag_index.sqlite3"):
    with production_generation_lock(exclusive=True,channel="generation"):
        print("LOCKED",flush=True)
        sys.stdin.readline()
"""


class CompositePrivateReadSessionTests(TestCase):
    def setUp(self):
        temporary=TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_one"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("CREATE TABLE rag_documents (project_id TEXT,path TEXT,source_type TEXT)")
            con.executemany("INSERT INTO rag_documents VALUES (?,?,?)", [
                ("project-lab","docs/a.md","DOCUMENTATION"),
                ("project-lab","src/b.py","CODE"),
                ("foreign","private/other","CODE"),
            ])
            con.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"schema_version":1}',encoding="utf-8")
        self.row={
            "project_id":"project-lab","enabled":True,
            "generation_directory":str(self.db.parent.resolve()),
            "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
            "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
        }
        self.write_catalog()

    def write_catalog(self):
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"project-lab":self.row}
        }),encoding="utf-8")

    def read(self, *,semantic=False, gen_factory=None, sem_factory=None, **kwargs):
        return private_read_session_lab(
            "project-lab",catalog_file=self.catalog,sqlite_path=self.db,
            manifest_path=self.manifest,
            generation_guard_factory=gen_factory or (
                lambda: production_generation_lock(
                    exclusive=False,channel="generation",
                )),
            semantic_guard_factory=sem_factory or (
                lambda: production_generation_lock(
                    exclusive=True,channel="semantic",
                )),
            semantic=semantic,operator_approved=True,laboratory_mode=True,
            **kwargs,
        )

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def test_lexical_sqlite_session_holds_generation_and_catalog_without_semantic(self):
        with self.patch_root():
            with self.read() as pin:
                self.assertFalse(pin.semantic_lock_held)
                self.assertFalse(pin.activation_authorized)
                with closing(sqlite3.connect(
                    pin.sqlite.resolve().as_uri()+"?mode=ro",uri=True
                )) as db:
                    rows=db.execute(
                        "SELECT path FROM rag_documents WHERE project_id=? ORDER BY path",
                        (pin.project_id,)
                    ).fetchall()
                self.assertEqual(rows,[("docs/a.md",),("src/b.py",)])
                with self.assertRaises(PrivateReadSessionLabError):
                    pin.call_semantic_already_locked(lambda: "unsafe")
        self.assertTrue((self.rag/"production-generation.lock").is_file())

    def test_semantic_session_acquires_once_in_strict_order(self):
        calls=[]
        @contextmanager
        def generation():
            calls.append("generation-enter")
            with production_generation_lock(exclusive=False,channel="generation"):
                yield
            calls.append("generation-exit")
        @contextmanager
        def semantic():
            calls.append("semantic-enter")
            with production_generation_lock(exclusive=True,channel="semantic"):
                yield
            calls.append("semantic-exit")
        with self.patch_root():
            with self.read(semantic=True,gen_factory=generation,
                           sem_factory=semantic) as pin:
                self.assertTrue(pin.semantic_lock_held)
                self.assertEqual(
                    pin.call_semantic_already_locked(
                        lambda value: "synthetic-"+value, "vector"
                    ), "synthetic-vector",
                )
                self.assertEqual(calls,["generation-enter","semantic-enter"])
            self.assertEqual(calls,[
                "generation-enter","semantic-enter","semantic-exit","generation-exit",
            ])

    def test_real_foreign_exclusive_generation_lock_blocks_read(self):
        proc=subprocess.Popen(
            [sys.executable,"-c",_CHILD_GENERATION,str(self.rag)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(),"LOCKED")
            with self.patch_root():
                with self.assertRaises(ProductionGenerationBusy):
                    with self.read():
                        pass
        finally:
            if proc.poll() is None:
                try:
                    proc.communicate(input="\n",timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate(timeout=5)
        with self.patch_root():
            with self.read():
                pass
        self.assertEqual(proc.returncode,0)

    def test_missing_or_changed_manifest_fails_closed(self):
        self.manifest.write_text('{"changed":true}',encoding="utf-8")
        with self.patch_root():
            with self.assertRaisesRegex(PrivateReadSessionLabError, "fingerprint"):
                with self.read():
                    pass

    def test_mid_session_artifact_drift_detected_before_releasing_guards(self):
        with self.patch_root():
            with self.assertRaisesRegex(PrivateReadSessionLabError,"changed while pinned"):
                with self.read():
                    self.manifest.write_text('{"changed":true}',encoding="utf-8")
            # Verify Win32 generation lock was released even after drift.
            with production_generation_lock(exclusive=True,channel="generation"):
                pass

    def test_pending_deletion_journal_blocks_both_read_modes(self):
        (self.root/"rag-del-any.journal.json").write_text("{}",encoding="utf-8")
        with self.patch_root():
            for semantic in (False,True):
                with self.subTest(semantic=semantic):
                    with self.assertRaises(LaboratoryCatalogUnsafe):
                        with self.read(semantic=semantic):
                            pass

    def test_enabled_registration_and_public_namespace_are_required(self):
        self.row["enabled"]=False
        self.write_catalog()
        with self.patch_root():
            with self.assertRaisesRegex(PrivateReadSessionLabError,"registration"):
                with self.read():
                    pass
            with self.assertRaises(PrivateReadSessionLabError):
                with private_read_session_lab(
                    "codebridge",catalog_file=self.catalog,
                    sqlite_path=self.db,manifest_path=self.manifest,
                    generation_guard_factory=lambda: production_generation_lock(),
                    laboratory_mode=True,operator_approved=True,
                ):
                    pass

    def test_closed_session_cannot_call_semantic_executor(self):
        with self.patch_root():
            with self.read(semantic=True) as pin:
                self.assertEqual(pin.call_semantic_already_locked(lambda: 1),1)
            with self.assertRaisesRegex(PrivateReadSessionLabError, "already closed"):
                pin.call_semantic_already_locked(lambda: 2)

    def test_active_reader_prevents_generation_swap_in_another_process(self):
        child=r"""
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock,ProductionGenerationBusy
import sys
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"rag_index.sqlite3"):
    try:
        with production_generation_lock(exclusive=True,channel="generation"):
            print("SWAP_ALLOWED")
    except ProductionGenerationBusy:
        print("SWAP_BUSY")
"""
        with self.patch_root():
            with self.read():
                result=subprocess.run(
                    [sys.executable,"-c",child,str(self.rag)],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True,text=True,timeout=10,
                )
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn("SWAP_BUSY",result.stdout)
            result=subprocess.run(
                [sys.executable,"-c",child,str(self.rag)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=10,
            )
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("SWAP_ALLOWED",result.stdout)
