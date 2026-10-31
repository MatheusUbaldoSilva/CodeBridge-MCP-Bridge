"""RAG-DEL-01.04-DQ-D-A: forced child crash releases scratch lock hierarchy."""
from contextlib import closing
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
    private_read_session_lab,
)
from rag.runtime.knowledge_deletion_bounded_catalog_lab import (
    bounded_catalog_mutex_lab, LaboratoryCatalogBusy, LaboratoryCatalogUnsafe,
)
from rag.runtime.production_generation_lock import (
    production_generation_lock, ProductionGenerationBusy,
)


_CHILD = r"""
import sys
from pathlib import Path
from unittest.mock import patch
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.production_generation_lock import production_generation_lock

root=Path(sys.argv[1])
catalog=root/"project-indexes.json"
db=root/"generations"/"private_crash"/"rag_index.sqlite3"
manifest=db.with_name("rag-index-manifest.json")
rag=root/"CodeBridge"/"rag"
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=rag/"rag_index.sqlite3"):
    with private_read_session_lab(
        "project-lab",catalog_file=catalog,sqlite_path=db,
        manifest_path=manifest,
        generation_guard_factory=lambda:production_generation_lock(
            exclusive=False,channel="generation",
        ),
        semantic_guard_factory=lambda:production_generation_lock(
            exclusive=True,channel="semantic",
        ),
        semantic=True,laboratory_mode=True,operator_approved=True,
    ):
        print("ALL_LOCKS_HELD",flush=True)
        sys.stdin.readline()
"""


class CrashRecoveryReadGuardsLabTests(TestCase):
    def setUp(self):
        temporary=TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_crash"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute(
                "CREATE TABLE rag_documents(project_id TEXT,path TEXT,source_type TEXT)"
            )
            cn.execute("INSERT INTO rag_documents VALUES ('project-lab','a.py','CODE')")
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"test":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{
                "project-lab":{
                    "project_id":"project-lab","enabled":True,
                    "generation_directory":str(self.db.parent.resolve()),
                    "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                    "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
                }
            }
        }),encoding="utf-8")

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def read(self):
        return private_read_session_lab(
            "project-lab",catalog_file=self.catalog,sqlite_path=self.db,
            manifest_path=self.manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=True,laboratory_mode=True,operator_approved=True,
        )

    def test_abrupt_reader_death_releases_all_locks_without_touching_artifacts(self):
        before=(self.catalog.read_bytes(),self.db.read_bytes(),self.manifest.read_bytes())
        proc=subprocess.Popen(
            [sys.executable,"-c",_CHILD,str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(),"ALL_LOCKS_HELD")
            with self.patch_root():
                with self.assertRaises(ProductionGenerationBusy):
                    with production_generation_lock(exclusive=True,channel="generation"):
                        pass
                with self.assertRaises(ProductionGenerationBusy):
                    with production_generation_lock(exclusive=True,channel="semantic"):
                        pass
            with self.assertRaises(LaboratoryCatalogBusy):
                with bounded_catalog_mutex_lab(
                    self.catalog,timeout_seconds=0.05,
                    laboratory_mode=True,operator_approved=True,
                ):
                    pass
        finally:
            proc.kill()
            proc.communicate(timeout=5)
        self.assertNotEqual(proc.returncode,0)
        with self.patch_root():
            with production_generation_lock(exclusive=True,channel="generation"):
                pass
            with production_generation_lock(exclusive=True,channel="semantic"):
                pass
            with self.read():
                pass
        with bounded_catalog_mutex_lab(
            self.catalog,timeout_seconds=0.2,
            laboratory_mode=True,operator_approved=True,
        ):
            pass
        self.assertEqual(
            (self.catalog.read_bytes(),self.db.read_bytes(),self.manifest.read_bytes()),
            before,
        )

    def test_unresolved_journal_after_crash_blocks_new_read_not_auto_recovery(self):
        (self.root/"rag-del-1234.journal.json").write_text(
            '{"state":"PREPARED"}',encoding="utf-8",
        )
        before=self.catalog.read_bytes()
        with self.patch_root():
            with self.assertRaisesRegex(LaboratoryCatalogUnsafe,"journal"):
                with self.read():
                    pass
        self.assertEqual(self.catalog.read_bytes(),before)
        self.assertTrue((self.root/"rag-del-1234.journal.json").exists())