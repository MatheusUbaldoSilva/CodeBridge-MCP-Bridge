import unittest
from installer.rag_p9b_combined_recovery_lab import recover_combined_lab
class CombinedTests(unittest.TestCase):
    def run_combined(self,files=True,shell=True,post=True,independent=True):
        calls=[]
        r=recover_combined_lab(
            lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"},independent=independent,
            file_worker=lambda:{"state":"FILE_RESTORE_LAB_VERIFIED" if files else "FAIL",
                                "verified":files,"old_files":236,"new_files_removed":22},
            shell_worker=lambda:{"state":"SHELL_LAB_VERIFIED" if shell else "FAIL",
                                 "verified":shell,"shortcuts":5,"registry_keys":2},
            verify_worker=lambda:{"verified":post},journal=lambda state,data:calls.append(state))
        return r,calls
    def test_complete(self):
        r,calls=self.run_combined()
        self.assertEqual(r["state"],"COMBINED_LAB_RECOVERY_VERIFIED")
        self.assertEqual((r["files"],r["new_targets"],r["shortcuts"],r["fake_registry_keys"]),(236,22,5,2))
        self.assertFalse(r["production_modified"])
        self.assertEqual(len(calls),4)
    def test_no_file_proof(self):
        r,calls=self.run_combined(files=False)
        self.assertEqual(r["reason"],"FILE_RESTORE_NOT_VERIFIED")
        self.assertEqual(len(calls),2)
    def test_no_shell_proof(self):
        r,calls=self.run_combined(shell=False)
        self.assertEqual(r["reason"],"SHELL_RESTORE_NOT_VERIFIED")
    def test_no_final_postverify(self):
        r,calls=self.run_combined(post=False)
        self.assertEqual(r["reason"],"INDEPENDENT_POSTVERIFY_FAILED")
    def test_missing_attestation_refuses_without_workers(self):
        calls=[]
        r=recover_combined_lab(lab_attestation=None,independent=True,
            file_worker=lambda:calls.append("files"),shell_worker=lambda:calls.append("shell"),
            verify_worker=lambda:calls.append("post"),journal=lambda *a:calls.append("journal"))
        self.assertEqual(r["reason"],"INDEPENDENT_LAB_GATES_REQUIRED")
        self.assertEqual(calls,[])
    def test_invalid_worker_responses_do_not_advance(self):
        for failure,reason in (("files","FILE_WORKER_INVALID"),("shell","SHELL_WORKER_INVALID"),
                               ("post","INDEPENDENT_POSTVERIFY_FAILED")):
            with self.subTest(failure=failure):
                calls=[]
                def step(name,good):
                    calls.append(name)
                    return None if name==failure else good
                r=recover_combined_lab(
                    lab_attestation={"purpose":"P9B_DISPOSABLE_UNIFIED_LAB"},independent=True,
                    file_worker=lambda:step("files",{"state":"FILE_RESTORE_LAB_VERIFIED","verified":True}),
                    shell_worker=lambda:step("shell",{"state":"SHELL_LAB_VERIFIED","verified":True}),
                    verify_worker=lambda:step("post",{"verified":True}),
                    journal=lambda state,data:calls.append(state))
                self.assertEqual(r["reason"],reason)
                self.assertFalse(r["verified"])
    def test_no_independent_channel(self):
        r,calls=self.run_combined(independent=False)
        self.assertEqual(r["reason"],"INDEPENDENT_LAB_GATES_REQUIRED")
if __name__=="__main__":unittest.main()
