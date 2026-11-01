"""F-12 DEV metadata coherence is not installed GUI attestation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest import TestCase

from rag.runtime.knowledge_deletion_gui_evidence_package_dev import (
    review_gui_evidence_package_dev as review,
)

ROOT = Path("C:/Users/Matheus/CodeBridge-MCP-Bridge")


def tree():
    launcher = ROOT.parent / "CodeBridge-Launcher" / "launcher.py"
    gui = ROOT / "app_rewrite" / "main.py"
    mcp = ROOT / "author_mcp" / "mcp_server.py"
    return [
        dict(ProcessId=101, ParentProcessId=1, CreationEpochMs=1000,
             CommandLine='"C:/python/pythonw.exe" "' + str(launcher) + '"'),
        dict(ProcessId=102, ParentProcessId=101, CreationEpochMs=1100,
             CommandLine='"C:/python/python.exe" "' + str(gui) + '" --no-elevate'),
        dict(ProcessId=103, ParentProcessId=102, CreationEpochMs=1200,
             CommandLine='"C:/python/python.exe" "' + str(mcp)
                         + '" --host 127.0.0.1 --port 8765'),
    ]


def lab():
    return dict(
        state="DEV_GUI_INPROCESS_READER_OBSERVED",
        read_only=True, activation_authorized=False,
        lab_inprocess_observed=True,
        installed_gui_trusted_channel_attested=False,
        gui_runtime_attested_for_operational_deletion=False,
        code_receipt_sha256="a" * 64,
        checks=dict(
            gui_route_loaded_bytecode_matches_dev_file=True,
            reader_loaded_bytecode_matches_dev_file=True,
            on_gui_owner_thread=True,
        ),
    )


class F12GuiEvidencePackageDevTests(TestCase):
    def test_happy_dev_observations_never_operational(self):
        result = review(tree(), ROOT, lab())
        self.assertEqual(result["state"], "F12_DEV_SNAPSHOT_COHERENT_INSTALLED_UNVERIFIED")
        self.assertTrue(result["checks"]["process_argv_topology_observed"])
        self.assertTrue(result["checks"]["process_creation_order_observed"])
        self.assertTrue(result["checks"]["offscreen_gui_code_observed"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["operational_use_allowed"])
        self.assertFalse(result["installed_gui_attested"])
        self.assertFalse(result["ready_for_operational_pilot"])
        self.assertIn("INSTALLED_GUI_TRUSTED_CHANNEL_UNVERIFIED", result["blockers"])

    def test_receipt_stable_after_reordering(self):
        source=tree()
        receipt=review(source, ROOT, lab())["process_snapshot_sha256"]
        out=review(list(reversed(source)), ROOT, lab(), expected_snapshot_sha256=receipt)
        self.assertTrue(out["snapshot_receipt_matches"])
        self.assertEqual(out["process_snapshot_sha256"], receipt)

    def test_stale_birth_snapshot_changes_receipt(self):
        source=tree()
        previous=review(source, ROOT, lab())["process_snapshot_sha256"]
        source[-1]["CreationEpochMs"]+=1
        out=review(source, ROOT, lab(), expected_snapshot_sha256=previous)
        self.assertEqual(out["state"], "F12_DEV_SNAPSHOT_UNVERIFIED")
        self.assertIn("DEV_PROCESS_SNAPSHOT_CHANGED", out["blockers"])
        self.assertFalse(out["activation_authorized"])

    def test_stale_argv_snapshot_changes_receipt(self):
        source=tree()
        previous=review(source, ROOT, lab())["process_snapshot_sha256"]
        source[2]["CommandLine"]+=" --extra"
        out=review(source, ROOT, lab(), expected_snapshot_sha256=previous)
        self.assertIn("DEV_PROCESS_SNAPSHOT_CHANGED", out["blockers"])
        self.assertIn("DEV_PROCESS_TOPOLOGY_UNVERIFIED", out["blockers"])

    def test_topology_with_wrong_parent_fails_closed(self):
        source=tree()
        source[-1]["ParentProcessId"]=999
        out=review(source, ROOT, lab())
        self.assertFalse(out["checks"]["process_argv_topology_observed"])
        self.assertFalse(out["checks"]["process_creation_order_observed"])
        self.assertFalse(out["installed_gui_attested"])

    def test_birth_order_failure_cannot_pass_even_with_valid_argv(self):
        source=tree()
        source[-1]["CreationEpochMs"]=900
        out=review(source, ROOT, lab())
        self.assertTrue(out["checks"]["process_argv_topology_observed"])
        self.assertFalse(out["checks"]["process_creation_order_observed"])
        self.assertIn("DEV_PROCESS_BIRTH_ORDER_UNVERIFIED", out["blockers"])

    def test_offscreen_code_mismatch_fails(self):
        fake=lab()
        fake["checks"]["reader_loaded_bytecode_matches_dev_file"]=False
        out=review(tree(), ROOT, fake)
        self.assertFalse(out["checks"]["offscreen_gui_code_observed"])
        self.assertFalse(out["installed_gui_attested"])

    def test_forged_installed_claim_does_not_authorize(self):
        source=tree()
        source[0]["installed_gui_attested"]=True
        fake=lab()
        fake["installed_gui_trusted_channel_attested"]=True
        out=review(source, ROOT, fake)
        self.assertFalse(out["checks"]["offscreen_gui_code_observed"])
        self.assertFalse(out["installed_gui_attested"])
        self.assertFalse(out["activation_authorized"])

    def test_extra_caller_authority_fields_do_not_change_receipt(self):
        a=tree()
        b=deepcopy(a)
        b[0]["activation_authorized"]=True
        b[0]["loaded_module_trusted"]=True
        self.assertEqual(review(a, ROOT, lab())["process_snapshot_sha256"],
                         review(b, ROOT, lab())["process_snapshot_sha256"])

    def test_snapshot_does_not_mutate_caller_records(self):
        a=tree()
        original=deepcopy(a)
        review(a, ROOT, lab())
        self.assertEqual(a, original)

    def test_bad_pid_parent_birth_command_rejected(self):
        for idx, field, value in (
            (0,"ProcessId",True),(0,"ProcessId",0),
            (1,"ProcessId",101),(1,"ParentProcessId",True),
            (2,"ParentProcessId",-1),(2,"CreationEpochMs","1200"),
            (2,"CreationEpochMs",False),(1,"CommandLine",None),
            (1,"CommandLine",""),(1,"CommandLine","\x00"),
        ):
            with self.subTest(field=field,value=value):
                candidate=tree()
                candidate[idx][field]=value
                with self.assertRaises(ValueError):
                    review(candidate,ROOT,lab())

    def test_bad_snapshot_structure_rejected(self):
        for bad in ([],None,{},[None],tree()*30):
            with self.subTest(kind=str(type(bad))):
                with self.assertRaises(ValueError):
                    review(bad,ROOT,lab())

    def test_bad_previous_receipt_rejected(self):
        for bad in ("", "A"*64, "g"*64, 123, True, [], "0"*63):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    review(tree(),ROOT,lab(),expected_snapshot_sha256=bad)

    def test_bad_root_and_lab_rejected(self):
        for root in (None,"C:/temp",Path("relative")):
            with self.subTest(root=root),self.assertRaises(ValueError):
                review(tree(),root,lab())
        for observation in (None,[],True):
            with self.subTest(observation=observation),self.assertRaises(ValueError):
                review(tree(),ROOT,observation)

    def test_strict_f11_shadowed_cli_fails(self):
        for extra in (" --port 9999"," --host=0.0.0.0"," --port 8765"):
            candidate=tree()
            candidate[2]["CommandLine"]+=extra
            result=review(candidate,ROOT,lab())
            self.assertFalse(result["checks"]["process_argv_topology_observed"])
            self.assertFalse(result["activation_authorized"])

    def test_output_excludes_raw_command_lines(self):
        result=review(tree(),ROOT,lab())
        self.assertNotIn("CommandLine",str(result))
        self.assertNotIn("CodeBridge-Launcher",str(result))
        self.assertEqual(len(result["process_snapshot_sha256"]),64)
