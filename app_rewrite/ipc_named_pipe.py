import ctypes
import struct
import time

from ctypes import wintypes

MAX_MESSAGE_BYTES = 4 * 1024 * 1024


DEFAULT_PIPE_NAME = (
    r"\\.\pipe\CodeBridge.MCP.IPC.v2"
)

DEFAULT_CONNECT_TIMEOUT = 5.0

FRAME_HEADER_SIZE = 4


PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000

PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000

PIPE_UNLIMITED_INSTANCES = 255

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

OPEN_EXISTING = 3

TOKEN_QUERY = 0x0008
TOKEN_USER_CLASS = 1

SDDL_REVISION_1 = 1

ERROR_FILE_NOT_FOUND = 2
ERROR_ACCESS_DENIED = 5
ERROR_BROKEN_PIPE = 109
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_SEM_TIMEOUT = 121
ERROR_NO_DATA = 232
ERROR_PIPE_BUSY = 231
ERROR_PIPE_CONNECTED = 535
ERROR_OPERATION_ABORTED = 995
ERROR_NOT_FOUND = 1168

INVALID_HANDLE_VALUE = (
    ctypes.c_void_p(-1).value
)


kernel32 = ctypes.WinDLL(
    "kernel32",
    use_last_error=True,
)

kernel32.CancelIoEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
]

kernel32.CancelIoEx.restype = wintypes.BOOL

advapi32 = ctypes.WinDLL(
    "advapi32",
    use_last_error=True,
)


class SID_AND_ATTRIBUTES(
    ctypes.Structure
):
    _fields_ = [
        (
            "Sid",
            wintypes.LPVOID,
        ),
        (
            "Attributes",
            wintypes.DWORD,
        ),
    ]


class TOKEN_USER(
    ctypes.Structure
):
    _fields_ = [
        (
            "User",
            SID_AND_ATTRIBUTES,
        ),
    ]


class SECURITY_ATTRIBUTES(
    ctypes.Structure
):
    _fields_ = [
        (
            "nLength",
            wintypes.DWORD,
        ),
        (
            "lpSecurityDescriptor",
            wintypes.LPVOID,
        ),
        (
            "bInheritHandle",
            wintypes.BOOL,
        ),
    ]


kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = (
    wintypes.HANDLE
)

kernel32.CloseHandle.argtypes = [
    wintypes.HANDLE,
]
kernel32.CloseHandle.restype = (
    wintypes.BOOL
)

kernel32.LocalFree.argtypes = [
    wintypes.HLOCAL,
]
kernel32.LocalFree.restype = (
    wintypes.HLOCAL
)

kernel32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(
        SECURITY_ATTRIBUTES
    ),
]
kernel32.CreateNamedPipeW.restype = (
    wintypes.HANDLE
)

kernel32.ConnectNamedPipe.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
]
kernel32.ConnectNamedPipe.restype = (
    wintypes.BOOL
)

kernel32.DisconnectNamedPipe.argtypes = [
    wintypes.HANDLE,
]
kernel32.DisconnectNamedPipe.restype = (
    wintypes.BOOL
)

kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = (
    wintypes.HANDLE
)

kernel32.WaitNamedPipeW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
]
kernel32.WaitNamedPipeW.restype = (
    wintypes.BOOL
)

kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(
        wintypes.DWORD
    ),
    wintypes.LPVOID,
]
kernel32.ReadFile.restype = (
    wintypes.BOOL
)

kernel32.WriteFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.DWORD,
    ctypes.POINTER(
        wintypes.DWORD
    ),
    wintypes.LPVOID,
]
kernel32.WriteFile.restype = (
    wintypes.BOOL
)


advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    ctypes.POINTER(
        wintypes.HANDLE
    ),
]
advapi32.OpenProcessToken.restype = (
    wintypes.BOOL
)

advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(
        wintypes.DWORD
    ),
]
advapi32.GetTokenInformation.restype = (
    wintypes.BOOL
)

advapi32.ConvertSidToStringSidW.argtypes = [
    wintypes.LPVOID,
    ctypes.POINTER(
        wintypes.LPWSTR
    ),
]
advapi32.ConvertSidToStringSidW.restype = (
    wintypes.BOOL
)

advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(
        wintypes.LPVOID
    ),
    ctypes.POINTER(
        wintypes.DWORD
    ),
]
advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
    wintypes.BOOL
)


class NamedPipeTransportError(
    OSError
):
    pass


class NamedPipeProtocolError(
    ValueError
):
    pass


def _last_error(
    operation,
):
    code = ctypes.get_last_error()

    return NamedPipeTransportError(
        f"{operation} falhou "
        f"(WinError {code})"
    )


def _handle_is_invalid(
    handle,
):
    return (
        handle is None
        or handle == 0
        or handle == INVALID_HANDLE_VALUE
    )


def _validate_pipe_name(
    pipe_name,
):
    if not isinstance(
        pipe_name,
        str,
    ):
        raise TypeError(
            "pipe_name deve ser string"
        )

    if not pipe_name.startswith(
        "\\\\.\\pipe\\"
    ):
        raise ValueError(
            "Nome de Named Pipe invalido"
        )

    if len(pipe_name) > 240:
        raise ValueError(
            "Nome de Named Pipe muito longo"
        )

    if "\x00" in pipe_name:
        raise ValueError(
            "Nome de Named Pipe contem NUL"
        )

    return pipe_name


def current_user_sid_string():
    token = wintypes.HANDLE()

    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_QUERY,
        ctypes.byref(
            token
        ),
    ):
        raise _last_error(
            "OpenProcessToken"
        )

    try:
        required = (
            wintypes.DWORD()
        )

        ctypes.set_last_error(
            0
        )

        advapi32.GetTokenInformation(
            token,
            TOKEN_USER_CLASS,
            None,
            0,
            ctypes.byref(
                required
            ),
        )

        error = (
            ctypes.get_last_error()
        )

        if (
            error
            != ERROR_INSUFFICIENT_BUFFER
            or required.value <= 0
        ):
            raise NamedPipeTransportError(
                "GetTokenInformation "
                "nao retornou tamanho valido"
            )

        buffer = (
            ctypes.create_string_buffer(
                required.value
            )
        )

        if not advapi32.GetTokenInformation(
            token,
            TOKEN_USER_CLASS,
            buffer,
            required.value,
            ctypes.byref(
                required
            ),
        ):
            raise _last_error(
                "GetTokenInformation"
            )

        token_user = ctypes.cast(
            buffer,
            ctypes.POINTER(
                TOKEN_USER
            ),
        ).contents

        sid_text = (
            wintypes.LPWSTR()
        )

        if not advapi32.ConvertSidToStringSidW(
            token_user.User.Sid,
            ctypes.byref(
                sid_text
            ),
        ):
            raise _last_error(
                "ConvertSidToStringSidW"
            )

        try:
            value = sid_text.value

            if (
                not value
                or not value.startswith(
                    "S-1-"
                )
            ):
                raise NamedPipeTransportError(
                    "SID do usuario atual invalido"
                )

            return value

        finally:
            if sid_text:
                kernel32.LocalFree(
                    ctypes.cast(
                        sid_text,
                        wintypes.HLOCAL,
                    )
                )

    finally:
        if token:
            kernel32.CloseHandle(
                token
            )


def build_current_user_pipe_sddl():
    sid = (
        current_user_sid_string()
    )

    # DACL protegida:
    # somente o SID do usuario atual
    # recebe Generic All.
    #
    # O rotulo de integridade Medium
    # permite a futura ponte Native
    # Messaging, normalmente nao elevada,
    # conversar com o CodeBridge elevado
    # mantendo a DACL presa ao mesmo
    # usuario do Windows.
    return (
        "D:P"
        f"(A;;GA;;;{sid})"
        "S:(ML;;NW;;;ME)"
    )


def _create_security_attributes():
    sddl = (
        build_current_user_pipe_sddl()
    )

    descriptor = (
        wintypes.LPVOID()
    )

    descriptor_size = (
        wintypes.DWORD()
    )

    if not (
        advapi32
        .ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl,
            SDDL_REVISION_1,
            ctypes.byref(
                descriptor
            ),
            ctypes.byref(
                descriptor_size
            ),
        )
    ):
        raise _last_error(
            "ConvertStringSecurityDescriptorToSecurityDescriptorW"
        )

    attributes = (
        SECURITY_ATTRIBUTES()
    )

    attributes.nLength = (
        ctypes.sizeof(
            SECURITY_ATTRIBUTES
        )
    )

    attributes.lpSecurityDescriptor = (
        descriptor
    )

    attributes.bInheritHandle = False

    return (
        attributes,
        descriptor,
    )


def _validate_frame_length(
    length,
):
    if (
        isinstance(
            length,
            bool,
        )
        or not isinstance(
            length,
            int,
        )
    ):
        raise NamedPipeProtocolError(
            "Tamanho do frame deve ser inteiro"
        )

    if length <= 0:
        raise NamedPipeProtocolError(
            "Frame vazio nao permitido"
        )

    if length > MAX_MESSAGE_BYTES:
        raise NamedPipeProtocolError(
            "Frame excede tamanho maximo"
        )

    return length


def _read_exact(
    handle,
    size,
):
    data = bytearray()

    while len(data) < size:
        remaining = (
            size
            - len(data)
        )

        chunk_size = min(
            remaining,
            65536,
        )

        buffer = (
            ctypes.create_string_buffer(
                chunk_size
            )
        )

        read = (
            wintypes.DWORD()
        )

        ok = kernel32.ReadFile(
            handle,
            buffer,
            chunk_size,
            ctypes.byref(
                read
            ),
            None,
        )

        if not ok:
            error = (
                ctypes.get_last_error()
            )

            if error in (
                ERROR_BROKEN_PIPE,
                ERROR_NO_DATA,
            ):
                raise EOFError(
                    "Named Pipe foi encerrado"
                )

            raise _last_error(
                "ReadFile"
            )

        if read.value == 0:
            raise EOFError(
                "Named Pipe retornou EOF"
            )

        data.extend(
            buffer.raw[
                :read.value
            ]
        )

    return bytes(
        data
    )


def _write_all(
    handle,
    data,
):
    offset = 0

    while offset < len(data):
        chunk = data[
            offset:
            offset + 65536
        ]

        buffer = (
            ctypes.create_string_buffer(
                chunk,
                len(chunk),
            )
        )

        written = (
            wintypes.DWORD()
        )

        ok = kernel32.WriteFile(
            handle,
            buffer,
            len(chunk),
            ctypes.byref(
                written
            ),
            None,
        )

        if not ok:
            error = (
                ctypes.get_last_error()
            )

            if error in (
                ERROR_BROKEN_PIPE,
                ERROR_NO_DATA,
            ):
                raise EOFError(
                    "Named Pipe foi encerrado"
                )

            raise _last_error(
                "WriteFile"
            )

        if written.value <= 0:
            raise NamedPipeTransportError(
                "WriteFile nao escreveu dados"
            )

        offset += written.value


def read_frame(
    handle,
):
    header = _read_exact(
        handle,
        FRAME_HEADER_SIZE,
    )

    length = struct.unpack(
        "<I",
        header,
    )[0]

    _validate_frame_length(
        length
    )

    return _read_exact(
        handle,
        length,
    )


def write_frame(
    handle,
    payload,
):
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "Payload do frame deve ser bytes"
        )

    length = _validate_frame_length(
        len(payload)
    )

    header = struct.pack(
        "<I",
        length,
    )

    _write_all(
        handle,
        header,
    )

    _write_all(
        handle,
        payload,
    )


class NamedPipeConnection:
    def __init__(
        self,
        handle,
        server_side=False,
    ):
        if _handle_is_invalid(
            handle
        ):
            raise ValueError(
                "Handle de Named Pipe invalido"
            )

        self._handle = handle
        self._server_side = bool(
            server_side
        )

    def receive(
        self,
    ):
        if self._handle is None:
            raise NamedPipeTransportError(
                "Conexao Named Pipe fechada"
            )

        return read_frame(
            self._handle
        )

    def send(
        self,
        payload,
    ):
        if self._handle is None:
            raise NamedPipeTransportError(
                "Conexao Named Pipe fechada"
            )

        write_frame(
            self._handle,
            payload,
        )

    def cancel_pending_io(
        self,
    ):
        handle = self._handle

        if handle is None:
            return False

        cancelled = (
            kernel32.CancelIoEx(
                handle,
                None,
            )
        )

        if cancelled:
            return True

        error = ctypes.get_last_error()

        if error in (
            ERROR_NOT_FOUND,
            ERROR_OPERATION_ABORTED,
        ):
            return False

        raise _last_error(
            "CancelIoEx"
        )

    def close(
        self,
    ):
        handle = self._handle

        if handle is None:
            return False

        self._handle = None

        if self._server_side:
            kernel32.DisconnectNamedPipe(
                handle
            )

        kernel32.CloseHandle(
            handle
        )

        return True

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        self.close()


class NamedPipeServer:
    def __init__(
        self,
        pipe_name=DEFAULT_PIPE_NAME,
    ):
        self._pipe_name = (
            _validate_pipe_name(
                pipe_name
            )
        )

    @property
    def pipe_name(
        self,
    ):
        return self._pipe_name

    def accept(
        self,
    ):
        (
            security_attributes,
            descriptor,
        ) = _create_security_attributes()

        handle = None

        try:
            handle = (
                kernel32.CreateNamedPipeW(
                    self._pipe_name,
                    (
                        PIPE_ACCESS_DUPLEX
                        | FILE_FLAG_FIRST_PIPE_INSTANCE
                    ),
                    (
                        PIPE_TYPE_BYTE
                        | PIPE_READMODE_BYTE
                        | PIPE_WAIT
                    ),
                    PIPE_UNLIMITED_INSTANCES,
                    65536,
                    65536,
                    0,
                    ctypes.byref(
                        security_attributes
                    ),
                )
            )

        finally:
            if descriptor:
                kernel32.LocalFree(
                    descriptor
                )

        if _handle_is_invalid(
            handle
        ):
            raise _last_error(
                "CreateNamedPipeW"
            )

        connected = (
            kernel32.ConnectNamedPipe(
                handle,
                None,
            )
        )

        if not connected:
            error = (
                ctypes.get_last_error()
            )

            if (
                error
                != ERROR_PIPE_CONNECTED
            ):
                kernel32.CloseHandle(
                    handle
                )

                raise NamedPipeTransportError(
                    "ConnectNamedPipe falhou "
                    f"(WinError {error})"
                )

        return NamedPipeConnection(
            handle,
            server_side=True,
        )


class NamedPipeClient:
    @staticmethod
    def connect(
        pipe_name=DEFAULT_PIPE_NAME,
        timeout=DEFAULT_CONNECT_TIMEOUT,
    ):
        pipe_name = (
            _validate_pipe_name(
                pipe_name
            )
        )

        if (
            isinstance(
                timeout,
                bool,
            )
            or not isinstance(
                timeout,
                (
                    int,
                    float,
                ),
            )
            or timeout <= 0
            or timeout > 60
        ):
            raise ValueError(
                "timeout deve estar entre 0 e 60 segundos"
            )

        deadline = (
            time.monotonic()
            + float(
                timeout
            )
        )

        last_error = None

        while True:
            remaining = (
                deadline
                - time.monotonic()
            )

            if remaining <= 0:
                raise NamedPipeTransportError(
                    "Timeout conectando ao Named Pipe"
                    + (
                        f" (ultimo WinError {last_error})"
                        if last_error
                        is not None
                        else ""
                    )
                )

            wait_ms = max(
                1,
                min(
                    int(
                        remaining
                        * 1000
                    ),
                    250,
                ),
            )

            available = (
                kernel32.WaitNamedPipeW(
                    pipe_name,
                    wait_ms,
                )
            )

            if not available:
                error = (
                    ctypes.get_last_error()
                )

                last_error = error

                if error in (
                    ERROR_FILE_NOT_FOUND,
                    ERROR_PIPE_BUSY,
                    ERROR_SEM_TIMEOUT,
                ):
                    time.sleep(
                        0.02
                    )

                    continue

                if (
                    error
                    == ERROR_ACCESS_DENIED
                ):
                    raise NamedPipeTransportError(
                        "Acesso negado ao Named Pipe"
                    )

                time.sleep(
                    0.02
                )

                continue

            handle = (
                kernel32.CreateFileW(
                    pipe_name,
                    (
                        GENERIC_READ
                        | GENERIC_WRITE
                    ),
                    0,
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )
            )

            if not _handle_is_invalid(
                handle
            ):
                return NamedPipeConnection(
                    handle,
                    server_side=False,
                )

            error = (
                ctypes.get_last_error()
            )

            last_error = error

            if error in (
                ERROR_FILE_NOT_FOUND,
                ERROR_PIPE_BUSY,
            ):
                time.sleep(
                    0.02
                )

                continue

            if error == ERROR_ACCESS_DENIED:
                raise NamedPipeTransportError(
                    "Acesso negado ao Named Pipe"
                )

            raise NamedPipeTransportError(
                "CreateFileW falhou "
                f"(WinError {error})"
            )

