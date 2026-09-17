import ctypes
from ctypes import wintypes

MUTEX_NAME = r"Local\CodeBridge.MCP.Bridge.v2"
ERROR_ALREADY_EXISTS = 183
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


class SingleInstance:
    def __init__(self):
        self.handle = None

    def acquire(self):
        ctypes.set_last_error(0)
        handle = _kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateMutexW falhou")
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def release(self):
        if self.handle:
            _kernel32.CloseHandle(self.handle)
            self.handle = None
