import ctypes
import os
from ctypes import wintypes
from pathlib import Path


CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class DPAPISecretStore:
    def __init__(self, path):
        if os.name != "nt":
            raise RuntimeError("DPAPI so esta disponivel no Windows")
        self.path = Path(path)
        self._crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
        self._protect = self._crypt32.CryptProtectData
        self._unprotect = self._crypt32.CryptUnprotectData
        self._local_free = self._kernel32.LocalFree

        self._protect.argtypes = [
            ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
        ]
        self._protect.restype = wintypes.BOOL
        self._unprotect.argtypes = [
            ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
        ]
        self._unprotect.restype = wintypes.BOOL
        self._local_free.argtypes = [ctypes.c_void_p]
        self._local_free.restype = ctypes.c_void_p

    @staticmethod
    def _blob_from_bytes(data):
        buffer = ctypes.create_string_buffer(data)
        blob = DATA_BLOB(
            len(data),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        return blob, buffer

    def _free_blob(self, blob):
        if blob.pbData:
            self._local_free(ctypes.cast(blob.pbData, ctypes.c_void_p))
            blob.pbData = None
            blob.cbData = 0

    def save(self, secret):
        secret = str(secret or "").strip()
        if not secret:
            raise ValueError("Segredo DPAPI nao pode ser vazio")
        raw = secret.encode("utf-8")
        in_blob, in_buffer = self._blob_from_bytes(raw)
        out_blob = DATA_BLOB()
        try:
            ok = self._protect(
                ctypes.byref(in_blob),
                "CodeBridge Secure Tunnel Runtime API Key",
                None, None, None,
                CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out_blob),
            )
            if not ok:
                error = ctypes.get_last_error()
                raise RuntimeError(f"CryptProtectData falhou: {ctypes.WinError(error)}")
            encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_bytes(encrypted)
            temp.replace(self.path)
        finally:
            ctypes.memset(in_buffer, 0, ctypes.sizeof(in_buffer))
            self._free_blob(out_blob)
        return True

    def load(self):
        if not self.path.is_file():
            return None
        encrypted = self.path.read_bytes()
        in_blob, in_buffer = self._blob_from_bytes(encrypted)
        out_blob = DATA_BLOB()
        description = wintypes.LPWSTR()
        try:
            ok = self._unprotect(
                ctypes.byref(in_blob),
                ctypes.byref(description),
                None, None, None,
                CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out_blob),
            )
            if not ok:
                error = ctypes.get_last_error()
                raise RuntimeError(f"CryptUnprotectData falhou: {ctypes.WinError(error)}")
            raw = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return raw.decode("utf-8")
        finally:
            ctypes.memset(in_buffer, 0, ctypes.sizeof(in_buffer))
            if description:
                self._local_free(ctypes.cast(description, ctypes.c_void_p))
            self._free_blob(out_blob)

    def exists(self):
        return self.path.is_file()

    def delete(self):
        try:
            self.path.unlink()
            return True
        except FileNotFoundError:
            return False
