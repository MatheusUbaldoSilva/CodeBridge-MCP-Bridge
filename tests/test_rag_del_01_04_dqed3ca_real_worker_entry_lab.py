"""DQ-E-D-3C-A: REAL worker entrypoint, pinned scratch mode; zero models."""
from contextlib import closing
from hashlib import sha256
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys

from rag.contracts import SearchQuery
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.knowledge_deletion_semantic_roundtrip_lab import (
    execute_semantic_roundtrip_lab, SemanticRoundtripLabError,
)
from rag.runtime.production_generation_lock import production_generation_lock
from rag.runtime import isolated_project_worker


_WRITER=r"""
import sys
from pathlib import Path
from unittest.mock import patch
from rag.runtime.production_generation_lock import production_generation_lock,ProductionGenerationBusy
root=Path(sys.argv[1])
with patch("rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
           return_value=root/"CodeBridge"/"rag"/"rag_index.sqlite3"):
    try:
        with production_generation_lock(exclusive=True,channel="generation"):
            print("WRITER_ALLOWED")
    except ProductionGenerationBusy:
        print("WRITER_BUSY")
"""


class RealWorkerScratchEntrypointTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_entry"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as cn:
            cn.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            cn.execute("INSERT INTO rag_documents VALUES ('private-lab','proof.py')")
            cn.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"synthetic":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"revision-1",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.query=SearchQuery(query="where is the lock",project_id="private-lab",top_k=2)
        self.route=QueryRoute.CODE

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def session(self):
        return private_read_session_lab(
            "private-lab",catalog_file=self.catalog,
            sqlite_path=self.db,manifest_path=self.manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=True,laboratory_mode=True,operator_approved=True,
        )

    def runner(self,*args,**kwargs):
        assert args[0][2]=="rag.runtime.knowledge_deletion_pin_worker_lab"
        argv=[sys.executable,"-m","rag.runtime.isolated_project_worker",
              "--pinned-scratch-only",str(self.root)]
        return subprocess.run(argv,**kwargs)

    def roundtrip(self,pin,**kwargs):
        return execute_semantic_roundtrip_lab(
            self.query,self.route,pin=pin,catalog_file=self.catalog,
            laboratory_mode=True,operator_approved=True,
            runner=self.runner,**kwargs,
        )

    def test_real_worker_entry_accepts_pin_and_preserves_response_correlation(self):
        with self.patch_root():
            with self.session() as pin:
                result=self.roundtrip(pin)
                self.assertEqual(result["state"],"LAB_PINNED_SEMANTIC_ROUNDTRIP_ONLY")
                self.assertEqual(result["generation_id"],"private_entry")
                self.assertFalse(result["model_executed"])
                self.assertFalse(result["activation_authorized"])

    def test_pinned_branch_never_resolves_registered_index_or_loads_semantic_model(self):
        # Real worker code path tested in-process with fail-on-use dependencies.
        from rag.runtime.knowledge_deletion_semantic_dispatch_lab import (
            dispatch_semantic_already_locked_lab,
        )
        with self.patch_root():
            with self.session() as pin:
                def executor(query,route,envelope):
                    payload={
                        "schema_version":1,"pin":envelope.to_payload(),
                        "query":query.query,"route":route.value,"top_k":query.top_k,
                        "source_types":[],"path_filter":None,"branch":None,
                    }
                    output=StringIO()
                    with (
                        patch.object(sys,"argv",["worker","--pinned-scratch-only",str(self.root)]),
                        patch.object(sys,"stdin",StringIO(json.dumps(payload)+"\n")),
                        patch.object(sys,"stdout",output),
                        patch.object(isolated_project_worker,"resolve_isolated_project",
                                     side_effect=AssertionError("catalog re-resolution")),
                        patch.object(isolated_project_worker,"search_persistent_semantic",
                                     side_effect=AssertionError("unexpected model")),
                    ):
                        isolated_project_worker.main()
                    return json.loads(output.getvalue())
                response=dispatch_semantic_already_locked_lab(
                    self.query,self.route,pin=pin,catalog_file=self.catalog,
                    executor=executor,laboratory_mode=True,operator_approved=True,
                )
                self.assertEqual(response["state"],"LAB_SEMANTIC_REQUEST_VALIDATED")
                self.assertFalse(response["model_executed"])

    def test_legacy_worker_without_args_keeps_original_route(self):
        payload={
            "project_id":"private-lab","query":"read context",
            "top_k":1,"source_types":[],"route":"CODE",
        }
        index=SimpleNamespace(
            project_id="private-lab",generation="gen1",
            sqlite=self.db,qdrant=self.db.parent/"qdrant",
            manifest=self.manifest,
        )
        output=StringIO()
        with (
            patch.object(sys,"argv",["worker"]),
            patch.object(sys,"stdin",StringIO(json.dumps(payload))),
            patch.object(sys,"stdout",output),
            patch.object(isolated_project_worker,"resolve_isolated_project",return_value=index) as resolver,
            patch.object(isolated_project_worker,"search_persistent_semantic",return_value=()) as search,
        ):
            isolated_project_worker.main()
        resolver.assert_called_once_with("private-lab")
        search.assert_called_once()
        self.assertEqual(json.loads(output.getvalue()),[])

    def test_unknown_flags_are_refused_before_request_is_read(self):
        for argv in (
            ["worker","--pinned-operational",str(self.root)],
            ["worker","--pinned-scratch-only"],
            ["worker","--pinned-scratch-only",str(self.root),"--model"],
            ["worker","--unknown"],
        ):
            with self.subTest(argv=argv):
                with (
                    patch.object(sys,"argv",argv),
                    patch.object(sys,"stdin",StringIO("")),
                    patch.object(isolated_project_worker,"resolve_isolated_project",
                                 side_effect=AssertionError("unexpected resolver")),
                ):
                    with self.assertRaises(PermissionError):
                        isolated_project_worker.main()

    def test_real_worker_rejects_non_scratch_root_and_malformed_request(self):
        for root,payload in (
            (Path.home(),{"anything":True}),
            (self.root,{"project_id":"private-lab"}),
        ):
            proc=subprocess.run(
                [sys.executable,"-m","rag.runtime.isolated_project_worker",
                 "--pinned-scratch-only",str(root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                input=json.dumps(payload)+"\n",capture_output=True,text=True,timeout=10,
            )
            self.assertNotEqual(proc.returncode,0)
            self.assertFalse(proc.stdout.strip())

    def test_real_worker_fails_when_catalog_changes_between_pin_and_child(self):
        def tampered_runner(*args,**kwargs):
            original=self.catalog.read_bytes()
            try:
                changed=json.loads(original)
                changed["projects"]["private-lab"]["source_revision"]="revision-2"
                self.catalog.write_text(json.dumps(changed),encoding="utf-8")
                return self.runner(*args,**kwargs)
            finally:
                self.catalog.write_bytes(original)
        with self.patch_root():
            with self.session() as pin:
                with self.assertRaises(SemanticRoundtripLabError):
                    execute_semantic_roundtrip_lab(
                        self.query,self.route,pin=pin,catalog_file=self.catalog,
                        laboratory_mode=True,operator_approved=True,
                        runner=tampered_runner,
                    )

    def test_real_worker_and_writer_compete_while_pin_held(self):
        with self.patch_root():
            with self.session() as pin:
                self.roundtrip(pin)
                other=subprocess.run(
                    [sys.executable,"-c",_WRITER,str(self.root)],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True,text=True,timeout=10,
                )
                self.assertEqual(other.returncode,0,other.stderr)
                self.assertIn("WRITER_BUSY",other.stdout)
            other=subprocess.run(
                [sys.executable,"-c",_WRITER,str(self.root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=10,
            )
            self.assertIn("WRITER_ALLOWED",other.stdout)