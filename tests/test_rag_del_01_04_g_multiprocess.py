"""RAG-DEL cross-process catalog serialization, temporary files only."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

class CatalogMultiProcessTests(TestCase):
    def test_interrupted_swap_is_rolled_back_by_new_process(self):
        from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap
        with TemporaryDirectory() as temp:
            root=Path(temp)
            catalog=root/"project-indexes.json"
            pointer=root/"active-generation.json"
            catalog.write_text(json.dumps({"schema_version":1,"projects":{
                "demo":{"project_id":"demo","enabled":True,
                        "source_revision":"old","generation_directory":"before"}}}))
            pointer.write_text('{"schema_version":1,"generation":"public"}')
            original=catalog.read_bytes()
            public=pointer.read_bytes()
            with self.assertRaises(RuntimeError):
                laboratory_swap("demo","old",{
                    "project_id":"demo","enabled":True,
                    "source_revision":"next","generation_directory":"new"},
                    catalog_file=catalog,public_pointer=pointer,
                    operator_approved=True,laboratory_mode=True,_fail_at="after")
            journal=next(root.glob("rag-del-*.journal.json"))
            transaction=journal.name.split("-")[2].split(".")[0]
            code=("from pathlib import Path;import sys;"
                  "from rag.runtime.knowledge_deletion_swap_lab import laboratory_rollback;"
                  "r=laboratory_rollback(sys.argv[1],catalog_file=Path(sys.argv[2]),"
                  "public_pointer=Path(sys.argv[3]),"
                  "operator_approved=True,laboratory_mode=True);"
                  "print(r['state'])")
            env=dict(os.environ)
            env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1])
            result=subprocess.run([sys.executable,"-c",code,transaction,
                str(catalog),str(pointer)],env=env,
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("LAB_ROLLBACK_COMPLETE",result.stdout)
            self.assertEqual(catalog.read_bytes(),original)
            self.assertEqual(pointer.read_bytes(),public)
    def test_two_processes_cannot_both_swap(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            catalog=root/"project-indexes.json"
            pointer=root/"active-generation.json"
            catalog.write_text(json.dumps({"schema_version":1,"projects":{
                "demo":{"project_id":"demo","enabled":True,
                        "source_revision":"old","generation_directory":"before"}}}))
            pointer.write_text('{"schema_version":1,"generation":"public"}')
            original_pointer=pointer.read_bytes()
            script=r'''
import sys
from pathlib import Path
from rag.runtime.knowledge_deletion_swap_lab import laboratory_swap
try:
    laboratory_swap("demo","old",{
        "project_id":"demo","enabled":True,
        "source_revision":"next","generation_directory":"new"},
        catalog_file=Path(sys.argv[1]),public_pointer=Path(sys.argv[2]),
        operator_approved=True,laboratory_mode=True)
    print("SWAPPED")
except Exception as error:
    print("REJECTED",type(error).__name__)
'''
            env=dict(os.environ)
            cwd=str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"]=cwd
            processes=[subprocess.Popen(
                [sys.executable,"-c",script,str(catalog),str(pointer)],
                cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                for _ in range(2)]
            results=[]
            for process in processes:
                stdout,stderr=process.communicate(timeout=20)
                self.assertEqual(process.returncode,0,stderr)
                results.append(stdout.strip())
            self.assertEqual(sum("SWAPPED" in r for r in results),1,results)
            self.assertEqual(sum("REJECTED" in r for r in results),1,results)
            self.assertEqual(pointer.read_bytes(),original_pointer)
            self.assertEqual(len(list(root.glob("rag-del-*.journal.json"))),1)
