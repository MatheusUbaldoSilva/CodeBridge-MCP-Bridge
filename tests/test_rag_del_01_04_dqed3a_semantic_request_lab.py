"""DQ-E-D-3A: strict synthetic request protocol tested in real subprocess."""
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

from rag.contracts import SearchQuery, SourceType
from rag.runtime.query_classifier import QueryRoute
from rag.runtime.knowledge_deletion_semantic_dispatch_lab import (
    dispatch_semantic_already_locked_lab,
)
from rag.runtime.knowledge_deletion_semantic_request_lab import (
    PinnedSemanticRequestV1, PinnedSemanticRequestLabError,
    verify_pinned_semantic_request_lab,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import private_read_session_lab
from rag.runtime.production_generation_lock import production_generation_lock


class SemanticRequestIPCOnlyTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_semantic"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            db.execute("INSERT INTO rag_documents VALUES ('private-lab','source.py')")
            db.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"fake":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"private-lab":{
                "project_id":"private-lab","enabled":True,
                "source_revision":"source-revision-1",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.query=SearchQuery(
            query="where is the isolated runtime",project_id="private-lab",
            top_k=3,source_types=(SourceType.CODE,),
            path_filter="src",branch="main",
        )
        self.route=QueryRoute.CODE

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

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def child(self,payload):
        return subprocess.run(
            [sys.executable,"-m","rag.runtime.knowledge_deletion_pin_worker_lab",
             str(self.root),"--semantic-request"],
            cwd=str(Path(__file__).resolve().parents[1]),
            input=json.dumps(payload),capture_output=True,text=True,timeout=10,
        )

    def request(self, pin):
        def build(query,route,envelope):
            return PinnedSemanticRequestV1.parse({
                "schema_version":1,
                "pin":envelope.to_payload(),
                "query":query.query,"route":route.value,
                "top_k":query.top_k,
                "source_types":[t.value for t in query.source_types],
                "path_filter":query.path_filter,
                "branch":query.branch,
            })
        return dispatch_semantic_already_locked_lab(
            self.query,self.route,pin=pin,catalog_file=self.catalog,
            executor=build,laboratory_mode=True,operator_approved=True,
        )

    def test_real_child_receives_same_pin_and_exact_query_fingerprint(self):
        with self.patch_root():
            with self.session() as pin:
                request=self.request(pin)
                self.assertEqual(request.pin.generation_id,"private_semantic")
                reply=self.child(request.to_payload())
                self.assertEqual(reply.returncode,0,reply.stderr)
                result=json.loads(reply.stdout)
                self.assertEqual(result["state"],"LAB_SEMANTIC_REQUEST_VALIDATED")
                self.assertEqual(result["nonce"],request.pin.nonce)
                self.assertEqual(result["request_sha256"],request.request_digest())
                self.assertEqual(result["route"],"CODE")
                self.assertEqual(result["top_k"],3)
                self.assertEqual(result["result_count"],0)
                self.assertFalse(result["model_executed"])
                self.assertFalse(result["activation_authorized"])

    def test_invalid_routes_and_query_limits_fail_before_sqlite(self):
        with self.patch_root():
            with self.session() as pin:
                request=self.request(pin)
                baseline=request.to_payload()
                for changed in (
                    {"route":"LEXICAL_ONLY"},{"route":"INVALID"},
                    {"top_k":0},{"top_k":21},{"top_k":True},
                    {"query":""},{"query":"x"*4097},
                    {"query":"line\x00bad"},
                    {"source_types":["CODE","CODE"]},
                    {"source_types":["UNKNOWN"]},{"source_types":"CODE"},
                ):
                    with self.subTest(changed=changed):
                        response=self.child({**baseline,**changed})
                        self.assertNotEqual(response.returncode,0)

    def test_injected_file_paths_and_out_of_scope_filters_refused(self):
        with self.patch_root():
            with self.session() as pin:
                baseline=self.request(pin).to_payload()
                for changed in (
                    {"command":"python.exe"},
                    {"sqlite_path":"../../outside"},
                    {"path_filter":"../secret"},
                    {"path_filter":"C:/Users/system"},
                    {"path_filter":"src\\bad"},
                    {"path_filter":"x"*513},
                    {"branch":"x"*129},
                    {"branch":None,"path_filter":""},
                ):
                    with self.subTest(changed=changed):
                        response=self.child({**baseline,**changed})
                        self.assertNotEqual(response.returncode,0)

    def test_request_digest_differs_across_valid_query_payloads(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                new= PinnedSemanticRequestV1.parse({
                    **req.to_payload(),"query":"different legitimate query",
                })
                self.assertNotEqual(req.request_digest(),new.request_digest())
                self.assertEqual(req.pin.nonce,new.pin.nonce)
                self.assertEqual(self.child(new.to_payload()).returncode,0)

    def test_catalog_change_invalidates_parent_child_request(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
        # Outside the pinned session, later catalog changes must fail closed.
        row=json.loads(self.catalog.read_text())
        row["projects"]["private-lab"]["source_revision"]="newer-revision"
        self.catalog.write_text(json.dumps(row),encoding="utf-8")
        res=self.child(req.to_payload())
        self.assertNotEqual(res.returncode,0)
        self.assertIn("catalog pin fingerprint mismatch",res.stderr)

    def test_synthetic_attestation_is_never_operational_authorization(self):
        with self.patch_root():
            with self.session() as pin:
                req=self.request(pin)
                result=verify_pinned_semantic_request_lab(
                    req,catalog_file=self.catalog,laboratory_mode=True,
                )
                self.assertFalse(result["parent_locks_attested_by_worker"])
                self.assertFalse(result["operational_use_allowed"])
                with self.assertRaises(PermissionError):
                    verify_pinned_semantic_request_lab(
                        req,catalog_file=self.catalog,laboratory_mode=False,
                    )