"""Read-only Windows host diagnostics for the RAG-017 disposable VM gate.

This is not evidence of a VM snapshot or rollback. Never alters host features.
"""
import json
import subprocess
from pathlib import Path


def probe():
    ps = r"""
$os=Get-CimInstance Win32_OperatingSystem
$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1
$disk=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$commands=@('Get-VM','New-VM','Checkpoint-VM')
$available=@{}
foreach($name in $commands){ $available[$name]=[bool](Get-Command $name -ErrorAction SilentlyContinue) }
[pscustomobject]@{
  os_caption=$os.Caption
  total_ram_gb=[math]::Round($os.TotalVisibleMemorySize/1MB,2)
  free_ram_gb=[math]::Round($os.FreePhysicalMemory/1MB,2)
  free_disk_gb=[math]::Round($disk.FreeSpace/1GB,2)
  firmware_virtualization=[bool]$cpu.VirtualizationFirmwareEnabled
  slat=[bool]$cpu.SecondLevelAddressTranslationExtensions
  vm_monitor_extensions=[bool]$cpu.VMMonitorModeExtensions
  hyperv_commands=$available
} | ConvertTo-Json -Compress -Depth 4
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, text=True, check=True, timeout=25,
    )
    return json.loads(result.stdout)


def evaluate(host):
    ram = host.get("free_ram_gb")
    disk = host.get("free_disk_gb")
    commands = host.get("hyperv_commands") or {}
    return {
        "host": host,
        "virtualization_hardware_ok": all(
            host.get(key) is True
            for key in ("firmware_virtualization", "slat", "vm_monitor_extensions")
        ),
        "hyperv_commands_available": all(commands.get(k) is True for k in ("Get-VM", "New-VM", "Checkpoint-VM")),
        "memory_candidate_4gb": isinstance(ram, (int, float)) and ram >= 4,
        "disk_candidate_60gb": isinstance(disk, (int, float)) and disk >= 60,
        "disposable_vm_verified": False,
        "snapshot_verified": False,
        "rollback_full_test_allowed": False,
        "host_execution_allowed": False,
        "note": "Read-only diagnostic. Resources alone never authorize VM installation or host installer execution.",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(probe()), indent=2, ensure_ascii=False))
