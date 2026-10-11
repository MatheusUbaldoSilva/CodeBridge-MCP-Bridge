"""Independent Windows processes perform real SQLite/Qdrant retrieval across a generation switch."""
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_validate import fixture
from rag.index.fts5 import initialize_fts5
from rag.index.qdrant_local import open_qdrant_local, close_qdrant_local
from rag.models.embedding import TEXT_EMBEDDING_DIMENSION
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_protected_session import protected_generation_retirement
from rag.runtime.generation_process_lock import GenerationBusy
from qdrant_client import models

CHILD = """
import json,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[4])
from rag.runtime.generation_search_paths import isolated_generation_search_paths
from rag.index.qdrant_local import open_qdrant_local,close_qdrant_local
from rag.retrieval.hybrid_text import search_text_vector
from rag.contracts import SearchQuery
with isolated_generation_search_paths(Path(sys.argv[1])) as paths:
    db=sqlite3.connect(paths.sqlite.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        content=db.execute('SELECT content FROM rag_chunks LIMIT 1').fetchone()[0]
    finally:
        db.close()
    q=open_qdrant_local(paths.qdrant)
    try:
        result=search_text_vector(q,SearchQuery(query='hello',project_id='a',top_k=2),[1.0]+[0.0]*1023)
    finally:
        close_qdrant_local(q)
    Path(sys.argv[2]).write_text(json.dumps({'generation':paths.generation,'content':content,
          'hits':len(result)}))
    deadline=time.monotonic()+8
    while not Path(sys.argv[3]).exists() and time.monotonic()<deadline:
        time.sleep(.04)
"""

def wait_ready(marker,process):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        if marker.exists():
            return
        if process.poll() is not None:
            raise AssertionError('reader failed before writing result')
        time.sleep(.04)
    raise AssertionError('reader readiness timeout')

class MultiprocessRealSearchTests(unittest.TestCase):
    def test_two_real_retrievals_pin_original_generation(self):
        import json,shutil
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'codebridge-rag-generation-test'
            for name in ('one','two'):
                folder=root/'generations'/name
                folder.mkdir(parents=True)
                fixture(folder)
                db=sqlite3.connect(folder/'rag_index.sqlite3')
                try:
                    initialize_fts5(db)
                    db.commit()
                finally:
                    db.close()
                shutil.rmtree(folder/'qdrant')
                q=open_qdrant_local(folder/'qdrant')
                try:
                    q.create_collection('code',vectors_config=models.VectorParams(size=3,distance=models.Distance.COSINE))
                    q.create_collection('text',vectors_config=models.VectorParams(size=TEXT_EMBEDDING_DIMENSION,distance=models.Distance.COSINE))
                    q.upsert('text',points=[models.PointStruct(id=42,vector=[1.0]+[0.0]*1023,
                        payload={'project_namespace':'a','chunk_id':'c1','document_id':'d1',
                                 'content':'hello','source_type':'DOCUMENTATION','path':'a.md'})],wait=True)
                finally:
                    close_qdrant_local(q)
            activate_test_generation(root,'one')
            children=[]
            try:
                for i in range(2):
                    marker=root/('ready'+str(i))
                    release=root/('release'+str(i))
                    p=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-c',CHILD,
                                        str(root),str(marker),str(release),
                                        str(Path(__file__).resolve().parents[1])],
                                       stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                    children.append(p)
                    wait_ready(marker,p)
                    report=json.loads(marker.read_text())
                    self.assertEqual(report,{'generation':'one','content':'hello','hits':1})
                activate_test_generation(root,'two')
                with self.assertRaises(GenerationBusy):
                    with protected_generation_retirement(root,'one'):
                        pass
                for i,p in enumerate(children):
                    (root/('release'+str(i))).touch()
                    self.assertEqual(p.wait(timeout=5),0)
                with protected_generation_retirement(root,'one') as folder:
                    self.assertTrue(folder.is_dir())
            finally:
                for i in range(2):
                    (root/('release'+str(i))).touch()
                for p in children:
                    try:
                        p.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        self.fail('isolated reader did not stop')
if __name__=='__main__':
    unittest.main()
