import unittest
from installer.rag_p9b_nsis_transaction_plan import plan_transaction


class PlanTests(unittest.TestCase):
    def args(self):
        return dict(artifact={"state":"ARTIFACT_PAIR_VERIFIED_ONLY","paired":True,
                              "source_commit":"a"*40},
                    shutdown={"state":"SHUTDOWN_SIGNALS_COMPLETED","processes_stopped":True},
                    poststop={"state":"POSTSTOP_OBSERVED_ONLY","observed_stopped":True},
                    independent_online=True,
                    official_process_state="NO_RUNNING_CODEBRIDGE",
                    paired_commit="a"*40)

    def test_all_observed_still_not_authorized(self):
        r=plan_transaction(**self.args())
        self.assertEqual(r["state"],"P9B_TRANSACTION_STEPS_OBSERVED_ONLY")
        self.assertFalse(r["authorized"])

    def test_malformed_artifact_and_boolean_pair_are_blocked(self):
        for bad in (None, [], {"state":"ARTIFACT_PAIR_VERIFIED_ONLY","paired":1}):
            with self.subTest(bad=bad):
                args=self.args()
                args["artifact"]=bad
                self.assertEqual(plan_transaction(**args)["reason"],
                                 "ARTIFACT_PAIR_UNVERIFIED")

    def test_malformed_shutdown_and_poststop_are_blocked(self):
        for key in ("shutdown","poststop"):
            args=self.args()
            args[key]=None
            result=plan_transaction(**args)
            self.assertFalse(result["authorized"])
            self.assertEqual(result["state"],"P9B_TRANSACTION_REFUSED")

    def test_invalid_commit_digest_is_blocked(self):
        for bad in ("z"*40, "A"*40, "a"*39, True):
            args=self.args()
            args["paired_commit"]=bad
            result=plan_transaction(**args)
            self.assertEqual(result["reason"],"SOURCE_COMMIT_MISMATCH")

    def test_wrong_commit_denied(self):
        a=self.args()
        a["paired_commit"]="b"*40
        self.assertEqual(plan_transaction(**a)["reason"],"SOURCE_COMMIT_MISMATCH")

    def test_shutdown_failure_denied(self):
        a=self.args()
        a["shutdown"]["processes_stopped"]=False
        self.assertEqual(plan_transaction(**a)["reason"],"SHUTDOWN_UNVERIFIED")

    def test_poststop_failure_denied(self):
        a=self.args()
        a["poststop"]["observed_stopped"]=False
        self.assertEqual(plan_transaction(**a)["reason"],"POSTSTOP_UNVERIFIED")

    def test_remote_channel_lost_denied(self):
        a=self.args()
        a["independent_online"]=False
        self.assertEqual(plan_transaction(**a)["reason"],
                         "EXTERNAL_RECOVERY_CHANNEL_UNAVAILABLE")

    def test_guard_blocked_denied(self):
        a=self.args()
        a["official_process_state"]="UPDATE_PROCESS_BLOCKED"
        self.assertEqual(plan_transaction(**a)["reason"],
                         "OFFICIAL_PROCESS_GUARD_NOT_CLEAR")

    def test_artifact_changed_denied(self):
        a=self.args()
        a["artifact"]["paired"]=False
        self.assertEqual(plan_transaction(**a)["reason"],"ARTIFACT_PAIR_UNVERIFIED")

if __name__=="__main__":
    unittest.main()
