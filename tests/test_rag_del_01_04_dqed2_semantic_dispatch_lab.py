"""DQ-E-D-2: legacy semantic lock exactly once; scratch dispatch already locked."""
from contextlib import closing, contextmanager
from hashlib import sha256
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
from rag.runtime.isolated_project_search import semantic_isolated_project
from rag.runtime.knowledge_deletion_semantic_dispatch_lab import (
    dispatch_semantic_already_locked_lab,
)
from rag.runtime.knowledge_deletion_pin_ipc_lab import (
    verify_private_pin_envelope_lab, PinEnvelopeLabError,
)
from rag.runtime.knowledge_deletion_private_read_session_lab import (
    private_read_session_lab, PrivateReadSessionLabError,
)
from rag.runtime.production_generation_lock import (
    production_generation_lock, ProductionGenerationBusy,
)


def _fake_result():
    return json.dumps([{
        "chunk_id":"s1", "document_id":"d1", "content":"synthetic result",
        "metadata":{"project_id":"project-lab","source_type":"CODE","path":"src/a.py"},
        "score":0.95,"rank":1,"retrieval_modes":["SYNTHETIC"],"stale":False,
    }])


class LegacySemanticLockRefactorTests(TestCase):
    def setUp(self):
        self.query=SearchQuery(query="where is runtime",project_id="project-lab",top_k=2)
        self.route=QueryRoute.CODE
        self.index=SimpleNamespace(python_executable=Path("synthetic-python"))

    def test_legacy_entry_acquires_exactly_one_semantic_lock(self):
        calls=[]
        held=[False]
        @contextmanager
        def counted(*,exclusive,channel):
            self.assertEqual((exclusive,channel),(True,"semantic"))
            self.assertFalse(held[0],"reentrant semantic lock forbidden")
            held[0]=True
            calls.append("enter")
            try:
                yield
            finally:
                held[0]=False
                calls.append("exit")
        def synthetic_subprocess(*args,**kwargs):
            self.assertTrue(held[0])
            calls.append("child")
            self.assertEqual(json.loads(kwargs["input"])["project_id"],"project-lab")
            self.assertEqual(kwargs["timeout"],180)
            return SimpleNamespace(returncode=0,stdout=_fake_result(),stderr="")
        with (
            patch("rag.runtime.isolated_project_search.resolve_isolated_project",
                  return_value=self.index),
            patch("rag.runtime.production_generation_lock.production_generation_lock",
                  counted),
            patch("rag.runtime.isolated_project_search.subprocess.run",
                  side_effect=synthetic_subprocess),
        ):
            result=semantic_isolated_project(self.query,self.route)
        self.assertEqual(calls,["enter","child","exit"])
        self.assertEqual(result[0].metadata.project_id,"project-lab")
        self.assertEqual(result[0].retrieval_modes,("SYNTHETIC",))

    def test_legacy_busy_retry_does_not_dispatch_before_lock(self):
        attempts=[]
        @contextmanager
        def busy_once(*,exclusive,channel):
            attempts.append("enter")
            if len(attempts)==1:
                raise ProductionGenerationBusy("busy")
            yield
        with (
            patch("rag.runtime.isolated_project_search.resolve_isolated_project",
                  return_value=self.index),
            patch("rag.runtime.production_generation_lock.production_generation_lock",
                  busy_once),
            patch("rag.runtime.isolated_project_search.time.sleep") as sleep,
            patch("rag.runtime.isolated_project_search.subprocess.run",
                  return_value=SimpleNamespace(
                      returncode=0,stdout=_fake_result(),stderr=""
                  )) as runner,
        ):
            result=semantic_isolated_project(self.query,self.route)
        self.assertEqual(len(attempts),2)
        self.assertEqual(runner.call_count,1)
        sleep.assert_called_once_with(0.2)
        self.assertEqual(result[0].chunk_id,"s1")

    def test_legacy_child_timeout_releases_semantic_lock(self):
        events=[]
        @contextmanager
        def guard(*,exclusive,channel):
            events.append("enter")
            try: yield
            finally: events.append("exit")
        with (
            patch("rag.runtime.isolated_project_search.resolve_isolated_project",
                  return_value=self.index),
            patch("rag.runtime.production_generation_lock.production_generation_lock",
                  guard),
            patch("rag.runtime.isolated_project_search.subprocess.run",
                  side_effect=subprocess.TimeoutExpired("synthetic",180)),
        ):
            with self.assertRaisesRegex(RuntimeError,"inference timed out"):
                semantic_isolated_project(self.query,self.route)
        self.assertEqual(events,["enter","exit"])

    def test_legacy_nonzero_child_remains_structured_error(self):
        with (
            patch("rag.runtime.isolated_project_search.resolve_isolated_project",
                  return_value=self.index),
            patch("rag.runtime.production_generation_lock.production_generation_lock",
                  return_value=_no_op()),
            patch("rag.runtime.isolated_project_search.subprocess.run",
                  return_value=SimpleNamespace(returncode=9,stdout="",stderr="worker failed")),
        ):
            with self.assertRaisesRegex(RuntimeError,"worker failed"):
                semantic_isolated_project(self.query,self.route)

    def test_missing_project_is_rejected_without_acquiring_lock(self):
        with (
            patch("rag.runtime.isolated_project_search.resolve_isolated_project",
                  return_value=None),
            patch("rag.runtime.production_generation_lock.production_generation_lock") as lock,
        ):
            with self.assertRaises(PermissionError):
                semantic_isolated_project(self.query,self.route)
            lock.assert_not_called()


@contextmanager
def _no_op():
    yield


class AlreadyHeldScratchDispatchTests(TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.rag=self.root/"CodeBridge"/"rag"
        self.rag.mkdir(parents=True)
        self.catalog=self.root/"project-indexes.json"
        self.db=self.root/"generations"/"private_locked"/"rag_index.sqlite3"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TABLE rag_documents(project_id TEXT,path TEXT)")
            db.execute("INSERT INTO rag_documents VALUES ('project-lab','a.py')")
            db.commit()
        self.manifest=self.db.with_name("rag-index-manifest.json")
        self.manifest.write_text('{"lab":true}',encoding="utf-8")
        self.catalog.write_text(json.dumps({
            "schema_version":1,"projects":{"project-lab":{
                "project_id":"project-lab","enabled":True,
                "source_revision":"revision-lab",
                "generation_directory":str(self.db.parent.resolve()),
                "sqlite_sha256":sha256(self.db.read_bytes()).hexdigest(),
                "manifest_sha256":sha256(self.manifest.read_bytes()).hexdigest(),
            }}
        }),encoding="utf-8")
        self.query=SearchQuery(query="test",project_id="project-lab",top_k=1)
        self.route=QueryRoute.CODE

    def patch_root(self):
        return patch(
            "rag.runtime.production_generation_lock.resolve_rag_sqlite_path",
            return_value=self.rag/"rag_index.sqlite3",
        )

    def session(self,*,semantic=True):
        return private_read_session_lab(
            "project-lab",catalog_file=self.catalog,
            sqlite_path=self.db,manifest_path=self.manifest,
            generation_guard_factory=lambda:production_generation_lock(
                exclusive=False,channel="generation",
            ),
            semantic_guard_factory=lambda:production_generation_lock(
                exclusive=True,channel="semantic",
            ),
            semantic=semantic,laboratory_mode=True,operator_approved=True,
        )

    def dispatch(self,pin,executor,query=None,**kwargs):
        return dispatch_semantic_already_locked_lab(
            query or self.query,self.route,pin=pin,catalog_file=self.catalog,
            executor=executor,laboratory_mode=True,operator_approved=True,
            **kwargs,
        )

    def test_synthetic_child_under_held_lock_without_reacquisition(self):
        observed=[]
        def child(query,route,envelope):
            observed.append(envelope.nonce)
            evidence=verify_private_pin_envelope_lab(
                envelope,catalog_file=self.catalog,laboratory_mode=True,
            )
            self.assertFalse(evidence["operational_use_allowed"])
            return ("synthetic-semantic-result",evidence["generation_id"])
        with self.patch_root():
            with self.session() as pinned:
                # Existing locks are held already: any NEW acquisition must fail.
                with patch("rag.runtime.production_generation_lock.production_generation_lock",
                           side_effect=AssertionError("semantic lock reacquired")):
                    result=self.dispatch(pinned,child)
                self.assertEqual(result,(
                    "synthetic-semantic-result","private_locked",
                ))
        self.assertEqual(len(observed),1)

    def test_real_fake_worker_dispatch_does_not_start_model(self):
        def fake_worker(query,route,envelope):
            completed=subprocess.run(
                [sys.executable,"-m","rag.runtime.knowledge_deletion_pin_worker_lab",
                 str(self.root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                input=json.dumps(envelope.to_payload()),
                capture_output=True,text=True,timeout=10,
            )
            if completed.returncode:
                raise AssertionError(completed.stderr)
            return json.loads(completed.stdout)["state"]
        with self.patch_root():
            with self.session() as pin:
                self.assertEqual(
                    self.dispatch(pin,fake_worker),
                    "LAB_PIN_ENVELOPE_VALIDATED",
                )

    def test_closed_or_lexical_session_never_dispatches(self):
        with self.patch_root():
            with self.session(semantic=False) as pin:
                with self.assertRaises(PinEnvelopeLabError):
                    self.dispatch(pin,lambda *args:None)
            with self.session() as pin:
                self.dispatch(pin,lambda *args:None)
            with self.assertRaises((PinEnvelopeLabError, PrivateReadSessionLabError)):
                self.dispatch(pin,lambda *args:None)

    def test_foreign_query_and_missing_approval_are_refused(self):
        foreign=SearchQuery(query="private",project_id="other-project")
        with self.patch_root():
            with self.session() as pin:
                with self.assertRaises(PermissionError):
                    self.dispatch(pin,lambda *args:None,query=foreign)
                with self.assertRaises(PermissionError):
                    dispatch_semantic_already_locked_lab(
                        self.query,self.route,pin=pin,catalog_file=self.catalog,
                        executor=lambda *args:None,laboratory_mode=True,
                        operator_approved=False,
                    )

    def test_executor_error_does_not_leave_semantic_lock_held(self):
        with self.patch_root():
            with self.assertRaisesRegex(RuntimeError,"synthetic failure"):
                with self.session() as pin:
                    self.dispatch(
                        pin,lambda *args:(_ for _ in ()).throw(
                            RuntimeError("synthetic failure")
                        ),
                    )
            with production_generation_lock(exclusive=True,channel="semantic"):
                pass