import ctypes
import os
import uuid
from ctypes import wintypes
from dataclasses import dataclass, replace


DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ADAPTER_FLAG_SOFTWARE = 0x2
IID_IDXGIFACTORY1 = "770aae78-f26f-4dba-a829-253c83d1b387"

VENDOR_NAMES = {
    "10DE": "NVIDIA",
    "1002": "AMD",
    "8086": "Intel",
    "5143": "Qualcomm",
    "1414": "Microsoft",
    "15AD": "VMware",
    "1AF4": "VirtIO",
    "1B36": "Red Hat",
    "1234": "QEMU",
}

_DISCRETE_VRAM_THRESHOLD = 512 * 1024**2


@dataclass(frozen=True)
class GPUDevice:
    index: int
    name: str
    vendor_id: str
    vendor_name: str
    device_id: str
    subsystem_id: str
    revision: int
    dedicated_vram_bytes: int
    dedicated_system_bytes: int
    shared_system_bytes: int
    luid: str
    is_software: bool
    is_integrated: bool
    is_discrete: bool
    adapter_type: str
    is_primary: bool = False

    @classmethod
    def from_record(cls, record):
        vendor_id = str(
            record.get("vendor_id") or ""
        ).upper()
        dedicated = int(
            record.get("dedicated_vram_bytes")
            or 0
        )
        shared = int(
            record.get("shared_system_bytes")
            or 0
        )
        is_software = bool(
            record.get("is_software")
        )

        is_discrete = bool(
            not is_software
            and dedicated
            >= _DISCRETE_VRAM_THRESHOLD
        )
        is_integrated = bool(
            not is_software
            and not is_discrete
            and shared > 0
        )

        if is_software:
            adapter_type = "software"
        elif is_discrete:
            adapter_type = "discrete"
        elif is_integrated:
            adapter_type = "integrated"
        else:
            adapter_type = "hardware"

        return cls(
            index=int(record.get("index") or 0),
            name=str(
                record.get("name") or "GPU"
            ),
            vendor_id=vendor_id,
            vendor_name=VENDOR_NAMES.get(
                vendor_id,
                "Unknown",
            ),
            device_id=str(
                record.get("device_id") or ""
            ).upper(),
            subsystem_id=str(
                record.get("subsystem_id") or ""
            ).upper(),
            revision=int(
                record.get("revision") or 0
            ),
            dedicated_vram_bytes=dedicated,
            dedicated_system_bytes=int(
                record.get(
                    "dedicated_system_bytes"
                )
                or 0
            ),
            shared_system_bytes=shared,
            luid=str(record.get("luid") or ""),
            is_software=is_software,
            is_integrated=is_integrated,
            is_discrete=is_discrete,
            adapter_type=adapter_type,
            is_primary=bool(
                record.get("is_primary")
            ),
        )

    def to_dict(self):
        return {
            "index": self.index,
            "name": self.name,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "device_id": self.device_id,
            "subsystem_id": self.subsystem_id,
            "revision": self.revision,
            "dedicated_vram_bytes": (
                self.dedicated_vram_bytes
            ),
            "dedicated_system_bytes": (
                self.dedicated_system_bytes
            ),
            "shared_system_bytes": (
                self.shared_system_bytes
            ),
            "luid": self.luid,
            "is_software": self.is_software,
            "is_integrated": self.is_integrated,
            "is_discrete": self.is_discrete,
            "adapter_type": self.adapter_type,
            "is_primary": self.is_primary,
        }


def _primary_score(device):
    return (
        1 if not device.is_software else 0,
        1 if device.is_discrete else 0,
        int(device.dedicated_vram_bytes),
        int(device.shared_system_bytes),
        -int(device.index),
    )


def select_primary_gpu(devices):
    devices = list(devices or [])
    if not devices:
        return None
    return max(
        devices,
        key=_primary_score,
    )


def build_gpu_devices(records):
    devices = [
        GPUDevice.from_record(record)
        for record in (records or [])
    ]
    primary = select_primary_gpu(devices)
    if primary is None:
        return devices

    return [
        replace(
            device,
            is_primary=(
                device.index == primary.index
                and device.luid == primary.luid
            ),
        )
        for device in devices
    ]


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, value):
        return cls.from_buffer_copy(
            uuid.UUID(value).bytes_le
        )


class _LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.LONG),
    ]


class _DXGIAdapterDesc1(ctypes.Structure):
    _fields_ = [
        ("Description", wintypes.WCHAR * 128),
        ("VendorId", wintypes.UINT),
        ("DeviceId", wintypes.UINT),
        ("SubSysId", wintypes.UINT),
        ("Revision", wintypes.UINT),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", _LUID),
        ("Flags", wintypes.UINT),
    ]


def _format_hex(value, width=4):
    return f"{int(value) & ((1 << (width * 4)) - 1):0{width}X}"


def _format_luid(luid):
    high = int(luid.HighPart) & 0xFFFFFFFF
    low = int(luid.LowPart) & 0xFFFFFFFF
    return f"{high:08X}:{low:08X}"


def _adapter_record(index, desc):
    return {
        "index": int(index),
        "name": str(desc.Description).strip(),
        "vendor_id": _format_hex(desc.VendorId),
        "device_id": _format_hex(desc.DeviceId),
        "subsystem_id": _format_hex(
            desc.SubSysId,
            width=8,
        ),
        "revision": int(desc.Revision),
        "dedicated_vram_bytes": int(
            desc.DedicatedVideoMemory
        ),
        "dedicated_system_bytes": int(
            desc.DedicatedSystemMemory
        ),
        "shared_system_bytes": int(
            desc.SharedSystemMemory
        ),
        "luid": _format_luid(desc.AdapterLuid),
        "is_software": bool(
            int(desc.Flags)
            & DXGI_ADAPTER_FLAG_SOFTWARE
        ),
    }


def _vtable_function(
    obj,
    index,
    restype,
    *argtypes,
):
    winfunctype = getattr(
        ctypes,
        "WINFUNCTYPE",
        ctypes.CFUNCTYPE,
    )
    vtable = ctypes.cast(
        obj,
        ctypes.POINTER(
            ctypes.POINTER(ctypes.c_void_p)
        ),
    ).contents
    return winfunctype(
        restype,
        ctypes.c_void_p,
        *argtypes,
    )(vtable[index])


def _enumerate_dxgi_adapters():
    if os.name != "nt":
        return []

    dxgi = ctypes.WinDLL("dxgi")
    create_factory = dxgi.CreateDXGIFactory1
    create_factory.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    create_factory.restype = ctypes.c_long

    factory = ctypes.c_void_p()
    iid = _GUID.from_uuid(IID_IDXGIFACTORY1)
    hr = create_factory(
        ctypes.byref(iid),
        ctypes.byref(factory),
    )
    if hr < 0 or not factory.value:
        raise OSError(
            f"CreateDXGIFactory1 failed: "
            f"0x{hr & 0xFFFFFFFF:08X}"
        )

    enum_adapters = _vtable_function(
        factory,
        12,
        ctypes.c_long,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
    )
    release_factory = _vtable_function(
        factory,
        2,
        wintypes.ULONG,
    )

    adapters = []
    try:
        index = 0
        while True:
            adapter = ctypes.c_void_p()
            hr = enum_adapters(
                factory,
                index,
                ctypes.byref(adapter),
            )
            if (
                hr & 0xFFFFFFFF
            ) == DXGI_ERROR_NOT_FOUND:
                break
            if hr < 0:
                raise OSError(
                    f"EnumAdapters1({index}) failed: "
                    f"0x{hr & 0xFFFFFFFF:08X}"
                )

            get_desc = _vtable_function(
                adapter,
                10,
                ctypes.c_long,
                ctypes.POINTER(
                    _DXGIAdapterDesc1
                ),
            )
            release_adapter = _vtable_function(
                adapter,
                2,
                wintypes.ULONG,
            )
            try:
                desc = _DXGIAdapterDesc1()
                desc_hr = get_desc(
                    adapter,
                    ctypes.byref(desc),
                )
                if desc_hr < 0:
                    raise OSError(
                        f"GetDesc1({index}) failed: "
                        f"0x{desc_hr & 0xFFFFFFFF:08X}"
                    )
                adapters.append(
                    _adapter_record(index, desc)
                )
            finally:
                release_adapter(adapter)
            index += 1
    finally:
        release_factory(factory)

    return adapters


def discover_windows_gpus():
    try:
        records = _enumerate_dxgi_adapters()
    except Exception:
        return []

    return [
        device.to_dict()
        for device in build_gpu_devices(records)
    ]
