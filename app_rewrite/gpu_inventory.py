import ctypes
import os
import uuid
from ctypes import wintypes


DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ADAPTER_FLAG_SOFTWARE = 0x2
IID_IDXGIFACTORY1 = "770aae78-f26f-4dba-a829-253c83d1b387"


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
        return _enumerate_dxgi_adapters()
    except Exception:
        return []
