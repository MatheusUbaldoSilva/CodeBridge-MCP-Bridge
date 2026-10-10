"""Read-only targeted Windows evidence collector, restricted to a verified VM guest."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

GUEST_MARKERS = ("virtual machine", "vmware", "virtualbox", "kvm", "qemu",
                 "hyper-v", "parallels")


def guest_identity(manufacturer, model):
    identity = (manufacturer + " " + model).lower()
    return any(marker in identity for marker in GUEST_MARKERS)


def guest_probe():
    command = ("Get-CimInstance Win32_ComputerSystem | "
               "Select-Object Manufacturer,Model | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                             "-Command", command], capture_output=True,
                            text=True, check=True, timeout=20)
    return json.loads(result.stdout)


def capture(vm_id, evidence_root, out):
    if not isinstance(vm_id, str) or not vm_id.strip():
        raise ValueError("nonempty VM identity required")
    guest = guest_probe()
    if not guest_identity(str(guest.get("Manufacturer", "")),
                          str(guest.get("Model", ""))):
        raise PermissionError("refusing inventory outside recognizable VM guest")
    evidence_root = evidence_root.resolve(strict=True)
    if not evidence_root.is_dir() or not evidence_root.name.startswith("CodeBridge-RAG017-VMTest-"):
        raise ValueError("dedicated VM evidence root required")
    out = out.resolve()
    if out == evidence_root or evidence_root in out.parents:
        raise ValueError("evidence output must stay outside the scanned directory")
    if out.exists():
        raise FileExistsError(out)
    if not out.parent.is_dir():
        raise FileNotFoundError(out.parent)
    files = {}
    for file in evidence_root.rglob("*"):
        if file.is_file() and not file.is_symlink():
            files[file.relative_to(evidence_root).as_posix()] = hashlib.sha256(
                file.read_bytes()).hexdigest()
    script = r"""
$ErrorActionPreference='Stop'
$reg=@{}
@('HKCU:\Software\CodeBridge','HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall') | ForEach-Object {
  $root=$_
  if(Test-Path $root) {
    Get-ChildItem $root -ErrorAction Stop | Where-Object {
      $_.PSChildName -match 'CodeBridge'
    } | ForEach-Object {
      $item=Get-ItemProperty $_.PSPath
      $reg[$_.Name]=@{DisplayName=[string]$item.DisplayName;DisplayVersion=[string]$item.DisplayVersion;InstallLocation=[string]$item.InstallLocation;UninstallString=[string]$item.UninstallString}
    }
  }
}
$shortcuts=@{}
@([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('CommonDesktopDirectory'),
  [Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('CommonPrograms')) | Where-Object {$_ -and (Test-Path $_)} | ForEach-Object {
  $base=$_
  Get-ChildItem -LiteralPath $base -Recurse -Filter '*CodeBridge*.lnk' -File -ErrorAction Stop | ForEach-Object {
    $shortcuts[$_.FullName]=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
  }
}
$services=@{}
Get-CimInstance Win32_Service -Filter "Name LIKE '%CodeBridge%'" | ForEach-Object {
  $services[$_.Name]=@{PathName=[string]$_.PathName;StartMode=[string]$_.StartMode;State=[string]$_.State}
}
[pscustomobject]@{registry=$reg;shortcuts=$shortcuts;services=$services} | ConvertTo-Json -Depth 6 -Compress
"""
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                             "-Command", script], capture_output=True,
                            text=True, check=True, timeout=90)
    inventory = json.loads(result.stdout)
    report = {
        "vm_id": vm_id, "guest_identity": guest, "root": str(evidence_root),
        "files": files, "registry": inventory["registry"],
        "shortcuts": inventory["shortcuts"], "services": inventory["services"],
        "registry_inventory_collected": True,
        "registry_snapshot_verified": False,
        "shortcuts_inventory_collected": True,
        "shortcuts_snapshot_verified": False,
        "services_inventory_collected": True,
        "services_snapshot_verified": False,
        "vm_snapshot_verified": False,
        "rollback_full_verified": False,
    }
    with out.open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2, ensure_ascii=False, sort_keys=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vm-id", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.vm_id, args.root, args.out)
    print(json.dumps({"files": len(result["files"]), "vm_snapshot_verified": False}))


if __name__ == "__main__":
    main()
