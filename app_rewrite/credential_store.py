import ctypes
import os
from ctypes import wintypes


CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2

ERROR_NOT_FOUND = 1168

DEFAULT_SSH_TARGET = "CodeBridge-MCP-Bridge:SSH"


class CredentialStoreError(RuntimeError):
    pass


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class CREDENTIALW(ctypes.Structure):
    pass


PCREDENTIALW = ctypes.POINTER(CREDENTIALW)


CREDENTIALW._fields_ = [
    ("Flags", wintypes.DWORD),
    ("Type", wintypes.DWORD),
    ("TargetName", wintypes.LPWSTR),
    ("Comment", wintypes.LPWSTR),
    ("LastWritten", FILETIME),
    ("CredentialBlobSize", wintypes.DWORD),
    ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
    ("Persist", wintypes.DWORD),
    ("AttributeCount", wintypes.DWORD),
    ("Attributes", ctypes.c_void_p),
    ("TargetAlias", wintypes.LPWSTR),
    ("UserName", wintypes.LPWSTR),
]


class WindowsCredentialStore:
    def __init__(
        self,
        target=DEFAULT_SSH_TARGET,
    ):
        if os.name != "nt":
            raise CredentialStoreError(
                "Windows Credential Manager so esta disponivel no Windows"
            )

        if not target:
            raise ValueError(
                "Target da credencial nao pode ser vazio"
            )

        self.target = target

        self._advapi32 = ctypes.WinDLL(
            "Advapi32.dll",
            use_last_error=True,
        )

        self._cred_write = (
            self._advapi32.CredWriteW
        )

        self._cred_write.argtypes = [
            ctypes.POINTER(CREDENTIALW),
            wintypes.DWORD,
        ]

        self._cred_write.restype = (
            wintypes.BOOL
        )

        self._cred_read = (
            self._advapi32.CredReadW
        )

        self._cred_read.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(PCREDENTIALW),
        ]

        self._cred_read.restype = (
            wintypes.BOOL
        )

        self._cred_delete = (
            self._advapi32.CredDeleteW
        )

        self._cred_delete.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]

        self._cred_delete.restype = (
            wintypes.BOOL
        )

        self._cred_free = (
            self._advapi32.CredFree
        )

        self._cred_free.argtypes = [
            ctypes.c_void_p,
        ]

        self._cred_free.restype = None

    def save(
        self,
        username,
        password,
    ):
        if not username:
            raise ValueError(
                "Login SSH nao pode ser vazio"
            )

        if password is None:
            raise ValueError(
                "Senha SSH nao pode ser None"
            )

        secret_bytes = password.encode(
            "utf-16-le"
        )

        if len(secret_bytes) > 512:
            raise ValueError(
                "Senha excede o limite suportado pelo Credential Manager"
            )

        secret_buffer = (
            ctypes.create_string_buffer(
                secret_bytes
            )
        )

        try:
            credential = CREDENTIALW()

            credential.Flags = 0
            credential.Type = (
                CRED_TYPE_GENERIC
            )

            credential.TargetName = (
                self.target
            )

            credential.Comment = (
                "CodeBridge SSH credential"
            )

            credential.CredentialBlobSize = (
                len(secret_bytes)
            )

            credential.CredentialBlob = (
                ctypes.cast(
                    secret_buffer,
                    ctypes.POINTER(
                        ctypes.c_ubyte
                    ),
                )
            )

            credential.Persist = (
                CRED_PERSIST_LOCAL_MACHINE
            )

            credential.AttributeCount = 0
            credential.Attributes = None
            credential.TargetAlias = None
            credential.UserName = username

            if not self._cred_write(
                ctypes.byref(credential),
                0,
            ):
                error = ctypes.get_last_error()

                raise CredentialStoreError(
                    "Falha ao salvar credencial SSH no Windows: "
                    + str(
                        ctypes.WinError(
                            error
                        )
                    )
                )

        finally:
            ctypes.memset(
                secret_buffer,
                0,
                ctypes.sizeof(
                    secret_buffer
                ),
            )

    def load(self):
        pointer = PCREDENTIALW()

        if not self._cred_read(
            self.target,
            CRED_TYPE_GENERIC,
            0,
            ctypes.byref(pointer),
        ):
            error = ctypes.get_last_error()

            if error == ERROR_NOT_FOUND:
                return None

            raise CredentialStoreError(
                "Falha ao ler credencial SSH do Windows: "
                + str(
                    ctypes.WinError(
                        error
                    )
                )
            )

        try:
            credential = pointer.contents

            username = (
                credential.UserName
                or ""
            )

            if (
                credential.CredentialBlobSize
                == 0
            ):
                password = ""

            else:
                raw = ctypes.string_at(
                    credential.CredentialBlob,
                    credential.CredentialBlobSize,
                )

                password = raw.decode(
                    "utf-16-le"
                )

            return {
                "username": username,
                "password": password,
            }

        finally:
            self._cred_free(
                pointer
            )

    def exists(self):
        return self.load() is not None

    def delete(self):
        if self._cred_delete(
            self.target,
            CRED_TYPE_GENERIC,
            0,
        ):
            return True

        error = ctypes.get_last_error()

        if error == ERROR_NOT_FOUND:
            return False

        raise CredentialStoreError(
            "Falha ao apagar credencial SSH do Windows: "
            + str(
                ctypes.WinError(
                    error
                )
            )
        )
