import unittest
from benchmarks.rag017_vm_host_preflight import evaluate


class VMHostPreflightTests(unittest.TestCase):
    def host(self, ram=6, disk=100, commands=True):
        return {
            "free_ram_gb": ram, "free_disk_gb": disk,
            "firmware_virtualization": True, "slat": True,
            "vm_monitor_extensions": True,
            "hyperv_commands": {key: commands for key in ("Get-VM", "New-VM", "Checkpoint-VM")},
        }

    def test_resources_never_authorize_rollback(self):
        report = evaluate(self.host())
        self.assertTrue(report["virtualization_hardware_ok"])
        self.assertTrue(report["hyperv_commands_available"])
        self.assertFalse(report["rollback_full_test_allowed"])
        self.assertFalse(report["snapshot_verified"])
        self.assertFalse(report["host_execution_allowed"])

    def test_low_memory_blocks_candidate(self):
        report = evaluate(self.host(ram=1.5))
        self.assertFalse(report["memory_candidate_4gb"])

    def test_missing_hyperv_blocks_capability(self):
        report = evaluate(self.host(commands=False))
        self.assertFalse(report["hyperv_commands_available"])

    def test_unknown_resources_fail_closed(self):
        report = evaluate({})
        self.assertFalse(report["virtualization_hardware_ok"])
        self.assertFalse(report["memory_candidate_4gb"])
        self.assertFalse(report["disk_candidate_60gb"])
        self.assertFalse(report["rollback_full_test_allowed"])


if __name__ == "__main__":
    unittest.main()
