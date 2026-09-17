import base64
import codecs
import ctypes
import os
import re
import threading
import time
import uuid
from ctypes import wintypes
from terminal_errors import (
    PowerShellCommandCancelled,
    PowerShellCommandError,
    PowerShellSessionInterrupted,
)
from windows_control_channel import (
    WindowsControlChannel,
)


PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
STARTF_USESTDHANDLES = 0x00000100
STILL_ACTIVE = 259

ERROR_BROKEN_PIPE = 109
ERROR_INVALID_HANDLE = 6


class COORD(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_short),
        ("Y", ctypes.c_short),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFOW),
        ("lpAttributeList", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


_kernel32 = ctypes.WinDLL(
    "kernel32",
    use_last_error=True,
)


_kernel32.CreatePipe.argtypes = [
    ctypes.POINTER(wintypes.HANDLE),
    ctypes.POINTER(wintypes.HANDLE),
    ctypes.c_void_p,
    wintypes.DWORD,
]
_kernel32.CreatePipe.restype = wintypes.BOOL

_kernel32.CreatePseudoConsole.argtypes = [
    COORD,
    wintypes.HANDLE,
    wintypes.HANDLE,
    wintypes.DWORD,
    ctypes.POINTER(ctypes.c_void_p),
]
_kernel32.CreatePseudoConsole.restype = ctypes.c_long

_kernel32.ResizePseudoConsole.argtypes = [
    ctypes.c_void_p,
    COORD,
]
_kernel32.ResizePseudoConsole.restype = ctypes.c_long

_kernel32.ClosePseudoConsole.argtypes = [
    ctypes.c_void_p,
]
_kernel32.ClosePseudoConsole.restype = None

_kernel32.InitializeProcThreadAttributeList.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(ctypes.c_size_t),
]
_kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL

_kernel32.UpdateProcThreadAttribute.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
_kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL

_kernel32.DeleteProcThreadAttributeList.argtypes = [
    ctypes.c_void_p,
]
_kernel32.DeleteProcThreadAttributeList.restype = None

_kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.BOOL,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW),
    ctypes.POINTER(PROCESS_INFORMATION),
]
_kernel32.CreateProcessW.restype = wintypes.BOOL

_kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
_kernel32.ReadFile.restype = wintypes.BOOL

_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
_kernel32.WriteFile.restype = wintypes.BOOL

_kernel32.GetExitCodeProcess.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.GetExitCodeProcess.restype = wintypes.BOOL

_kernel32.TerminateProcess.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
]
_kernel32.TerminateProcess.restype = wintypes.BOOL

_kernel32.CloseHandle.argtypes = [
    wintypes.HANDLE,
]
_kernel32.CloseHandle.restype = wintypes.BOOL


def _raise_win32(message):
    raise OSError(
        ctypes.get_last_error(),
        message,
    )


def _close_handle(handle):
    if not handle:
        return

    try:
        _kernel32.CloseHandle(
            handle
        )
    except Exception:
        pass


class WindowsTerminalSession:
    def __init__(
        self,
        executable=None,
    ):
        if executable is None:
            executable = os.path.join(
                os.environ.get(
                    "WINDIR",
                    r"C:\Windows",
                ),
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe",
            )

        self._executable = os.path.abspath(
            executable
        )

        self._state_lock = threading.RLock()
        self._write_lock = threading.Lock()

        self._output_callback = None
        self._visible_protocol_filter_buffer = bytearray()

        self._width = 120
        self._height = 40

        self._hpcon = None
        self._input_write = None
        self._output_read = None

        self._process_handle = None
        self._thread_handle = None
        self._pid = None

        self._reader_thread = None
        self._reader_stop = threading.Event()

        self._control_channel = (
            WindowsControlChannel(
                on_message=(
                    self._handle_control_message
                ),
            )
        )

        self._last_error = None

        self._execution_lock = (
            threading.Lock()
        )

        self._execution_state = None
        self._executing = False
        self._cancel_requested = False

        self._cancel_recovery_delay = 0.10

        protocol_token = uuid.uuid4().hex[:8]

        self._native_begin_marker_text = (
            "~B"
            + protocol_token
            + "~"
        )

        self._native_prompt_prefix_text = (
            "~S"
            + protocol_token
            + ":"
        )

        self._native_status_end_text = ":E~"

        self._native_prompt_end_text = (
            "~P"
            + protocol_token
            + "~"
        )

        self._native_begin_marker = (
            self._native_begin_marker_text.encode(
                "ascii"
            )
        )

        self._native_prompt_prefix = (
            self._native_prompt_prefix_text.encode(
                "ascii"
            )
        )

        self._native_status_end = (
            self._native_status_end_text.encode(
                "ascii"
            )
        )

        self._native_prompt_end = (
            self._native_prompt_end_text.encode(
                "ascii"
            )
        )

        self._native_redraw_prompt_sequence = (
            b"\x1b[20~"
        )

        self._native_clear_line_sequence = (
            b"\x1b[21~"
        )

        self._native_add_line_sequence = (
            b"\x1b[23~"
        )

        self._native_accept_sequence = (
            b"\x1b[24~"
        )

        self._native_input_settle_delay = 0.05

    @property
    def is_running(self):
        with self._state_lock:
            process_handle = (
                self._process_handle
            )

        if not process_handle:
            return False

        exit_code = wintypes.DWORD()

        if not _kernel32.GetExitCodeProcess(
            process_handle,
            ctypes.byref(
                exit_code
            ),
        ):
            return False

        return (
            exit_code.value
            == STILL_ACTIVE
        )

    @property
    def pid(self):
        if not self.is_running:
            return None

        with self._state_lock:
            return self._pid

    @property
    def last_error(self):
        with self._state_lock:
            return self._last_error

    @property
    def is_executing(
        self,
    ):
        with self._state_lock:
            return self._executing

    def set_output_callback(
        self,
        callback,
    ):
        if (
            callback is not None
            and not callable(
                callback
            )
        ):
            raise TypeError(
                "callback deve ser callable ou None"
            )

        with self._state_lock:
            self._output_callback = (
                callback
            )

    def _handle_control_message(
        self,
        payload,
    ):
        if not isinstance(
            payload,
            (bytes, bytearray),
        ):
            return b"ERROR:TYPE"

        try:
            message = bytes(
                payload
            ).decode(
                "ascii"
            )

        except UnicodeDecodeError:
            return b"ERROR:ENCODING"

        if message.startswith(
            "BEGIN:"
        ):
            execution_id = message[
                len("BEGIN:"):
            ]

            try:
                parsed_id = (
                    uuid.UUID(
                        hex=execution_id
                    ).hex
                )

            except Exception:
                return b"ERROR:BEGIN_ID"

            if parsed_id != execution_id:
                return b"ERROR:BEGIN_ID"

            with self._state_lock:
                state = (
                    self._execution_state
                )

                if (
                    state is None
                    or state.get(
                        "done",
                        False,
                    )
                ):
                    return b"ERROR:NO_EXECUTION"

                previous_id = state.get(
                    "control_execution_id"
                )

                if (
                    previous_id is not None
                    and previous_id
                    != execution_id
                ):
                    return b"ERROR:BEGIN_CONFLICT"

                state[
                    "control_execution_id"
                ] = execution_id

                state[
                    "control_begin_seen"
                ] = True

            fence_token = (
                uuid.uuid4().hex
            )

            with self._state_lock:
                state = (
                    self._execution_state
                )

                if (
                    state is None
                    or state.get(
                        "done",
                        False,
                    )
                ):
                    return b"ERROR:NO_EXECUTION"

                if (
                    state.get(
                        "control_execution_id"
                    )
                    != execution_id
                ):
                    return b"ERROR:BEGIN_CONFLICT"

                state[
                    "control_start_fence_token"
                ] = fence_token

                state[
                    "control_start_fence"
                ] = (
                    "~CBFS"
                    + fence_token
                    + "~"
                ).encode(
                    "ascii"
                )

            return (
                "ACK:BEGIN:"
                + execution_id
                + ":"
                + fence_token
            ).encode(
                "ascii"
            )

        if message.startswith(
            "END:"
        ):
            parts = message.split(
                ":",
                3,
            )

            if len(parts) != 4:
                return b"ERROR:END_FORMAT"

            execution_id = parts[1]

            try:
                parsed_id = (
                    uuid.UUID(
                        hex=execution_id
                    ).hex
                )

            except Exception:
                return b"ERROR:END_ID"

            if parsed_id != execution_id:
                return b"ERROR:END_ID"

            success_text = (
                parts[2]
                .strip()
                .lower()
            )

            if success_text not in (
                "true",
                "false",
            ):
                return b"ERROR:END_STATUS"

            exit_text = (
                parts[3]
                .strip()
            )

            try:
                exit_code = (
                    int(exit_text)
                    if exit_text
                    else 0
                )

            except ValueError:
                return b"ERROR:END_EXIT"

            failed = (
                success_text != "true"
                or exit_code != 0
            )

            if (
                success_text != "true"
                and exit_code == 0
            ):
                exit_code = 1
                failed = True

            with self._state_lock:
                state = (
                    self._execution_state
                )

                if (
                    state is None
                    or state.get(
                        "done",
                        False,
                    )
                ):
                    return b"ERROR:NO_EXECUTION"

                begin_id = state.get(
                    "control_execution_id"
                )

                if begin_id != execution_id:
                    return b"ERROR:END_CONFLICT"

                if state.get(
                    "control_end_seen",
                    False,
                ):
                    return b"ERROR:END_DUPLICATE"

                state[
                    "control_end_seen"
                ] = True

                state[
                    "control_failed"
                ] = failed

                state[
                    "control_exit_code"
                ] = exit_code

            fence_token = (
                uuid.uuid4().hex
            )

            with self._state_lock:
                state = (
                    self._execution_state
                )

                if (
                    state is None
                    or state.get(
                        "done",
                        False,
                    )
                ):
                    return b"ERROR:NO_EXECUTION"

                if (
                    state.get(
                        "control_execution_id"
                    )
                    != execution_id
                ):
                    return b"ERROR:END_CONFLICT"

                state[
                    "control_end_fence_token"
                ] = fence_token

                state[
                    "control_end_fence"
                ] = (
                    "~CBFE"
                    + fence_token
                    + "~"
                ).encode(
                    "ascii"
                )

            return (
                "ACK:END:"
                + execution_id
                + ":"
                + fence_token
            ).encode(
                "ascii"
            )

        return b"ERROR:UNKNOWN"


    def _native_control_bootstrap_script(
        self,
    ):
        pipe_leaf = (
            self._control_channel.pipe_leaf
        )

        if not pipe_leaf:
            raise RuntimeError(
                "Named Pipe de controle Windows ausente"
            )

        safe_leaf = pipe_leaf.replace(
            "'",
            "''",
        )

        return (
            "$__cb_control_pipe="
            "[System.IO.Pipes.NamedPipeClientStream]::new("
            "'.','"
            + safe_leaf
            + "',"
            "[System.IO.Pipes.PipeDirection]::InOut,"
            "[System.IO.Pipes.PipeOptions]::None"
            ");"
            "$__cb_control_pipe.Connect(5000);"
            "$__cb_ready=[Text.Encoding]::UTF8.GetBytes('READY');"
            "$__cb_header=[BitConverter]::GetBytes("
            "[UInt32]$__cb_ready.Length"
            ");"
            "$__cb_control_pipe.Write("
            "$__cb_header,0,$__cb_header.Length"
            ");"
            "$__cb_control_pipe.Write("
            "$__cb_ready,0,$__cb_ready.Length"
            ");"
            "$__cb_control_pipe.Flush();"
            "$__cb_header_in=New-Object byte[] 4;"
            "$__cb_offset=0;"
            "while ($__cb_offset -lt 4) {"
            "$__cb_read=$__cb_control_pipe.Read("
            "$__cb_header_in,$__cb_offset,4-$__cb_offset"
            ");"
            "if ($__cb_read -le 0) {"
            "throw 'EOF no handshake do canal de controle'"
            "};"
            "$__cb_offset+=$__cb_read"
            "};"
            "$__cb_length=[BitConverter]::ToUInt32("
            "$__cb_header_in,0"
            ");"
            "$__cb_payload=New-Object byte[] $__cb_length;"
            "$__cb_offset=0;"
            "while ($__cb_offset -lt $__cb_length) {"
            "$__cb_read=$__cb_control_pipe.Read("
            "$__cb_payload,$__cb_offset,"
            "$__cb_length-$__cb_offset"
            ");"
            "if ($__cb_read -le 0) {"
            "throw 'EOF lendo ACK do canal de controle'"
            "};"
            "$__cb_offset+=$__cb_read"
            "};"
            "$__cb_ack=[Text.Encoding]::UTF8.GetString("
            "$__cb_payload"
            ");"
            "if ($__cb_ack -ne 'ACK:READY') {"
            "throw 'Handshake do canal de controle invalido'"
            "};"
            "$__cb_control_state=[PSCustomObject]@{"
            "Pipe=$__cb_control_pipe;"
            "ExecutionId=$null"
            "};"
            "Remove-Variable "
            "__cb_control_pipe,__cb_ready,__cb_header,"
            "__cb_header_in,__cb_offset,__cb_read,"
            "__cb_length,__cb_payload,__cb_ack "
            "-ErrorAction SilentlyContinue;"
        )

    def _native_bootstrap_script(
        self,
    ):
        return (
            self._native_control_bootstrap_script()
            + "Import-Module PSReadLine -ErrorAction Stop;"
            "$global:__CodeBridgeOriginalPrompt="
            "(Get-Command prompt).ScriptBlock;"
            "$global:__CodeBridgeAutomationActive=$false;"
            "$global:__CodeBridgeAutomationPagerState=$null;"
            "$__cb_f9={"
            "param($key,$arg);"
            "[Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt("
            "$key,$arg"
            ")"
            "};"
            "Set-PSReadLineKeyHandler "
            "-Chord F9 "
            "-ScriptBlock $__cb_f9;"
            "Set-PSReadLineKeyHandler "
            "-Chord F10 "
            "-Function RevertLine;"
            "Set-PSReadLineKeyHandler "
            "-Chord F11 "
            "-Function AddLine;"
            "$__cb_f12={"
            "$__cb_ping=[Text.Encoding]::UTF8.GetBytes('PING');"
            "$__cb_ping_header=[BitConverter]::GetBytes("
            "[UInt32]$__cb_ping.Length"
            ");"
            "$__cb_control_state.Pipe.Write("
            "$__cb_ping_header,0,$__cb_ping_header.Length"
            ");"
            "$__cb_control_state.Pipe.Write("
            "$__cb_ping,0,$__cb_ping.Length"
            ");"
            "$__cb_control_state.Pipe.Flush();"
            "$__cb_ping_header_in=New-Object byte[] 4;"
            "$__cb_ping_offset=0;"
            "while ($__cb_ping_offset -lt 4) {"
            "$__cb_ping_read=$__cb_control_state.Pipe.Read("
            "$__cb_ping_header_in,$__cb_ping_offset,"
            "4-$__cb_ping_offset"
            ");"
            "if ($__cb_ping_read -le 0) {"
            "throw 'EOF no PING do canal de controle'"
            "};"
            "$__cb_ping_offset+=$__cb_ping_read"
            "};"
            "$__cb_ping_length=[BitConverter]::ToUInt32("
            "$__cb_ping_header_in,0"
            ");"
            "$__cb_ping_payload=New-Object byte[] $__cb_ping_length;"
            "$__cb_ping_offset=0;"
            "while ($__cb_ping_offset -lt $__cb_ping_length) {"
            "$__cb_ping_read=$__cb_control_state.Pipe.Read("
            "$__cb_ping_payload,$__cb_ping_offset,"
            "$__cb_ping_length-$__cb_ping_offset"
            ");"
            "if ($__cb_ping_read -le 0) {"
            "throw 'EOF lendo ACK:PING'"
            "};"
            "$__cb_ping_offset+=$__cb_ping_read"
            "};"
            "$__cb_ping_ack=[Text.Encoding]::UTF8.GetString("
            "$__cb_ping_payload"
            ");"
            "if ($__cb_ping_ack -ne 'ACK:PING') {"
            "throw 'ACK:PING invalido'"
            "};"
            "Remove-Variable "
            "__cb_ping,__cb_ping_header,__cb_ping_header_in,"
            "__cb_ping_offset,__cb_ping_read,__cb_ping_length,"
            "__cb_ping_payload,__cb_ping_ack "
            "-ErrorAction SilentlyContinue;"
            "$__cb_exec_id=[Guid]::NewGuid().ToString('N');"
            "$__cb_begin_text='BEGIN:'+$__cb_exec_id;"
            "$__cb_begin=[Text.Encoding]::ASCII.GetBytes("
            "$__cb_begin_text"
            ");"
            "$__cb_begin_header=[BitConverter]::GetBytes("
            "[UInt32]$__cb_begin.Length"
            ");"
            "$__cb_control_state.Pipe.Write("
            "$__cb_begin_header,0,$__cb_begin_header.Length"
            ");"
            "$__cb_control_state.Pipe.Write("
            "$__cb_begin,0,$__cb_begin.Length"
            ");"
            "$__cb_control_state.Pipe.Flush();"
            "$__cb_begin_header_in=New-Object byte[] 4;"
            "$__cb_begin_offset=0;"
            "while ($__cb_begin_offset -lt 4) {"
            "$__cb_begin_read=$__cb_control_state.Pipe.Read("
            "$__cb_begin_header_in,$__cb_begin_offset,"
            "4-$__cb_begin_offset"
            ");"
            "if ($__cb_begin_read -le 0) {"
            "throw 'EOF no ACK:BEGIN'"
            "};"
            "$__cb_begin_offset+=$__cb_begin_read"
            "};"
            "$__cb_begin_length=[BitConverter]::ToUInt32("
            "$__cb_begin_header_in,0"
            ");"
            "$__cb_begin_payload="
            "New-Object byte[] $__cb_begin_length;"
            "$__cb_begin_offset=0;"
            "while ("
            "$__cb_begin_offset -lt $__cb_begin_length"
            ") {"
            "$__cb_begin_read=$__cb_control_state.Pipe.Read("
            "$__cb_begin_payload,$__cb_begin_offset,"
            "$__cb_begin_length-$__cb_begin_offset"
            ");"
            "if ($__cb_begin_read -le 0) {"
            "throw 'EOF lendo ACK:BEGIN'"
            "};"
            "$__cb_begin_offset+=$__cb_begin_read"
            "};"
            "$__cb_begin_ack="
            "[Text.Encoding]::ASCII.GetString("
            "$__cb_begin_payload"
            ");"
            "$__cb_begin_ack_prefix="
            "'ACK:BEGIN:'+$__cb_exec_id+':';"
            "if (-not $__cb_begin_ack.StartsWith("
            "$__cb_begin_ack_prefix"
            ")) {"
            "throw 'ACK:BEGIN invalido'"
            "};"
            "$__cb_begin_fence_token="
            "$__cb_begin_ack.Substring("
            "$__cb_begin_ack_prefix.Length"
            ");"
            "[void][Guid]::ParseExact("
            "$__cb_begin_fence_token,'N'"
            ");"
            "$__cb_control_state.ExecutionId="
            "$__cb_exec_id;"
            "Remove-Variable "
            "__cb_begin_text,__cb_begin,__cb_begin_header,"
            "__cb_begin_header_in,__cb_begin_offset,"
            "__cb_begin_read,__cb_begin_length,"
            "__cb_begin_payload,__cb_begin_ack,"
            "__cb_begin_ack_prefix "
            "-ErrorAction SilentlyContinue;"
            "$global:__CodeBridgeAutomationActive=$true;"
            "$global:__CodeBridgeAutomationPagerState="
            "[PSCustomObject]@{"
            "HadGitPager=(Test-Path Env:GIT_PAGER);"
            "GitPager=$env:GIT_PAGER;"
            "HadPager=(Test-Path Env:PAGER);"
            "Pager=$env:PAGER"
            "};"
            "$env:GIT_PAGER='cat';"
            "$env:PAGER='cat';"
            "$global:__CodeBridgePreviousEap="
            "$global:ErrorActionPreference;"
            "$global:__CodeBridgeErrorKey='*:ErrorAction';"
            "$global:__CodeBridgeHadDefault="
            "$global:PSDefaultParameterValues.ContainsKey("
            "$global:__CodeBridgeErrorKey);"
            "if ($global:__CodeBridgeHadDefault) {"
            "$global:__CodeBridgePreviousDefault="
            "$global:PSDefaultParameterValues["
            "$global:__CodeBridgeErrorKey]"
            "} else {"
            "$global:__CodeBridgePreviousDefault=$null"
            "};"
            "$global:ErrorActionPreference='Continue';"
            "$global:PSDefaultParameterValues["
            "$global:__CodeBridgeErrorKey]='Stop';"
            "$global:LASTEXITCODE=0;"
            "[Console]::Write("
            "'~CBFS'+$__cb_begin_fence_token+'~'"
            ");"
            "Remove-Variable "
            "__cb_begin_fence_token "
            "-ErrorAction SilentlyContinue;"
            "[Microsoft.PowerShell.PSConsoleReadLine]"
            "::AcceptLine()"
            "}.GetNewClosure();"
            "Set-PSReadLineKeyHandler "
            "-Chord F12 "
            "-ScriptBlock $__cb_f12;"
            "Remove-Variable "
            "__cb_f12 "
            "-ErrorAction SilentlyContinue;"
            "$__cb_prompt={"
            "$__cb_ok=$?;"
            "$__cb_lec=$global:LASTEXITCODE;"
            "if ($global:__CodeBridgeAutomationActive) {"
            "if ($null -ne "
            "$global:__CodeBridgeAutomationPagerState) {"
            "if ("
            "$global:__CodeBridgeAutomationPagerState.HadGitPager"
            ") {"
            "$env:GIT_PAGER="
            "$global:__CodeBridgeAutomationPagerState.GitPager"
            "} else {"
            "Remove-Item Env:GIT_PAGER "
            "-ErrorAction SilentlyContinue"
            "};"
            "if ("
            "$global:__CodeBridgeAutomationPagerState.HadPager"
            ") {"
            "$env:PAGER="
            "$global:__CodeBridgeAutomationPagerState.Pager"
            "} else {"
            "Remove-Item Env:PAGER "
            "-ErrorAction SilentlyContinue"
            "};"
            "$global:__CodeBridgeAutomationPagerState=$null"
            "};"
            "$global:ErrorActionPreference="
            "$global:__CodeBridgePreviousEap;"
            "if ($global:__CodeBridgeHadDefault) {"
            "$global:PSDefaultParameterValues["
            "$global:__CodeBridgeErrorKey]="
            "$global:__CodeBridgePreviousDefault"
            "} else {"
            "[void]"
            "$global:PSDefaultParameterValues.Remove("
            "$global:__CodeBridgeErrorKey)"
            "};"
            "$global:__CodeBridgeAutomationActive=$false;"
            "$__cb_control_exit="
            "if ($null -eq $__cb_lec) {"
            "'0'"
            "} else {"
            "[string]$__cb_lec"
            "};"
            "$__cb_end_text="
            "'END:'+$__cb_control_state.ExecutionId+':'"
            "+[string]$__cb_ok+':'"
            "+$__cb_control_exit;"
            "$__cb_end=[Text.Encoding]::ASCII.GetBytes("
            "$__cb_end_text"
            ");"
            "$__cb_end_header=[BitConverter]::GetBytes("
            "[UInt32]$__cb_end.Length"
            ");"
            "$__cb_control_state.Pipe.Write("
            "$__cb_end_header,0,$__cb_end_header.Length"
            ");"
            "$__cb_control_state.Pipe.Write("
            "$__cb_end,0,$__cb_end.Length"
            ");"
            "$__cb_control_state.Pipe.Flush();"
            "$__cb_end_header_in=New-Object byte[] 4;"
            "$__cb_end_offset=0;"
            "while ($__cb_end_offset -lt 4) {"
            "$__cb_end_read=$__cb_control_state.Pipe.Read("
            "$__cb_end_header_in,$__cb_end_offset,"
            "4-$__cb_end_offset"
            ");"
            "if ($__cb_end_read -le 0) {"
            "throw 'EOF no ACK:END'"
            "};"
            "$__cb_end_offset+=$__cb_end_read"
            "};"
            "$__cb_end_length=[BitConverter]::ToUInt32("
            "$__cb_end_header_in,0"
            ");"
            "$__cb_end_payload="
            "New-Object byte[] $__cb_end_length;"
            "$__cb_end_offset=0;"
            "while ("
            "$__cb_end_offset -lt $__cb_end_length"
            ") {"
            "$__cb_end_read=$__cb_control_state.Pipe.Read("
            "$__cb_end_payload,$__cb_end_offset,"
            "$__cb_end_length-$__cb_end_offset"
            ");"
            "if ($__cb_end_read -le 0) {"
            "throw 'EOF lendo ACK:END'"
            "};"
            "$__cb_end_offset+=$__cb_end_read"
            "};"
            "$__cb_end_ack="
            "[Text.Encoding]::ASCII.GetString("
            "$__cb_end_payload"
            ");"
            "$__cb_end_ack_prefix="
            "'ACK:END:'+$__cb_control_state.ExecutionId+':';"
            "if (-not $__cb_end_ack.StartsWith("
            "$__cb_end_ack_prefix"
            ")) {"
            "throw 'ACK:END invalido'"
            "};"
            "$__cb_end_fence_token="
            "$__cb_end_ack.Substring("
            "$__cb_end_ack_prefix.Length"
            ");"
            "[void][Guid]::ParseExact("
            "$__cb_end_fence_token,'N'"
            ");"
            "Remove-Variable "
            "__cb_control_exit,__cb_end_text,__cb_end,"
            "__cb_end_header,__cb_end_header_in,"
            "__cb_end_offset,__cb_end_read,__cb_end_length,"
            "__cb_end_payload,__cb_end_ack,"
            "__cb_end_ack_prefix "
            "-ErrorAction SilentlyContinue;"
            "[Console]::Write("
            "'~CBFE'+$__cb_end_fence_token+'~'"
            ");"
            "Remove-Variable "
            "__cb_end_fence_token "
            "-ErrorAction SilentlyContinue;"
            "return (& $global:__CodeBridgeOriginalPrompt)"
            "};"
            "return (& $global:__CodeBridgeOriginalPrompt)"
            "}.GetNewClosure();"
            "Set-Item "
            "-Path Function:\\global:prompt "
            "-Value $__cb_prompt;"
            "Remove-Variable "
            "__cb_control_state,__cb_prompt "
            "-ErrorAction SilentlyContinue;"
        )

    def start(
        self,
        on_output=None,
        width=120,
        height=40,
    ):
        width = max(
            20,
            min(
                32767,
                int(width),
            ),
        )

        height = max(
            5,
            min(
                32767,
                int(height),
            ),
        )

        if (
            on_output is not None
            and not callable(
                on_output
            )
        ):
            raise TypeError(
                "on_output deve ser callable ou None"
            )

        if self.is_running:
            self.set_output_callback(
                on_output
            )

            self.resize(
                width,
                height,
            )

            return True

        self.close()

        if not os.path.isfile(
            self._executable
        ):
            raise RuntimeError(
                "powershell.exe 5.1 nao encontrado"
            )

        self._control_channel.start()

        input_read = wintypes.HANDLE()
        input_write = wintypes.HANDLE()
        output_read = wintypes.HANDLE()
        output_write = wintypes.HANDLE()

        hpcon = ctypes.c_void_p()
        attribute_buffer = None
        attribute_list = None
        process = PROCESS_INFORMATION()

        installed = False

        try:
            if not _kernel32.CreatePipe(
                ctypes.byref(
                    input_read
                ),
                ctypes.byref(
                    input_write
                ),
                None,
                0,
            ):
                _raise_win32(
                    "CreatePipe de entrada falhou"
                )

            if not _kernel32.CreatePipe(
                ctypes.byref(
                    output_read
                ),
                ctypes.byref(
                    output_write
                ),
                None,
                0,
            ):
                _raise_win32(
                    "CreatePipe de saida falhou"
                )

            hr = _kernel32.CreatePseudoConsole(
                COORD(
                    width,
                    height,
                ),
                input_read,
                output_write,
                0,
                ctypes.byref(
                    hpcon
                ),
            )

            if hr != 0:
                raise RuntimeError(
                    "CreatePseudoConsole HRESULT="
                    + hex(
                        hr
                        & 0xFFFFFFFF
                    )
                )

            size = ctypes.c_size_t()

            _kernel32.InitializeProcThreadAttributeList(
                None,
                1,
                0,
                ctypes.byref(
                    size
                ),
            )

            attribute_buffer = (
                ctypes.create_string_buffer(
                    size.value
                )
            )

            attribute_list = ctypes.cast(
                attribute_buffer,
                ctypes.c_void_p,
            )

            if not _kernel32.InitializeProcThreadAttributeList(
                attribute_list,
                1,
                0,
                ctypes.byref(
                    size
                ),
            ):
                _raise_win32(
                    "InitializeProcThreadAttributeList falhou"
                )

            if not _kernel32.UpdateProcThreadAttribute(
                attribute_list,
                0,
                PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                hpcon,
                ctypes.sizeof(
                    ctypes.c_void_p
                ),
                None,
                None,
            ):
                _raise_win32(
                    "UpdateProcThreadAttribute falhou"
                )

            startup = STARTUPINFOEXW()

            startup.StartupInfo.cb = (
                ctypes.sizeof(
                    STARTUPINFOEXW
                )
            )

            startup.StartupInfo.dwFlags = (
                STARTF_USESTDHANDLES
            )

            startup.StartupInfo.hStdInput = None
            startup.StartupInfo.hStdOutput = None
            startup.StartupInfo.hStdError = None

            startup.lpAttributeList = (
                attribute_list
            )

            bootstrap = (
                self._native_bootstrap_script()
            )

            encoded_bootstrap = (
                base64.b64encode(
                    bootstrap.encode(
                        "utf-16le"
                    )
                ).decode(
                    "ascii"
                )
            )

            command_line = (
                ctypes.create_unicode_buffer(
                    '"'
                    + self._executable
                    + '" -NoLogo -NoExit '
                    + "-EncodedCommand "
                    + encoded_bootstrap
                )
            )

            flags = (
                EXTENDED_STARTUPINFO_PRESENT
                | CREATE_UNICODE_ENVIRONMENT
            )

            if not _kernel32.CreateProcessW(
                None,
                command_line,
                None,
                None,
                False,
                flags,
                None,
                os.getcwd(),
                ctypes.byref(
                    startup.StartupInfo
                ),
                ctypes.byref(
                    process
                ),
            ):
                _raise_win32(
                    "CreateProcessW do PowerShell falhou"
                )

            _close_handle(
                input_read
            )
            input_read = None

            _close_handle(
                output_write
            )
            output_write = None

            with self._state_lock:
                self._output_callback = (
                    on_output
                )

                self._width = width
                self._height = height

                self._hpcon = hpcon
                self._input_write = input_write
                self._output_read = output_read

                self._process_handle = (
                    process.hProcess
                )

                self._thread_handle = (
                    process.hThread
                )

                self._pid = int(
                    process.dwProcessId
                )

                self._last_error = None

                self._reader_stop.clear()

                reader_thread = threading.Thread(
                    target=self._reader_loop,
                    name=(
                        "CodeBridgeWindowsTerminalReader"
                    ),
                    daemon=True,
                )

                self._reader_thread = (
                    reader_thread
                )

            installed = True
            reader_thread.start()

            try:
                self._control_channel.wait_ready(
                    timeout=5.0
                )

            except Exception:
                self.close()
                raise

            return True

        finally:
            if attribute_list:
                try:
                    _kernel32.DeleteProcThreadAttributeList(
                        attribute_list
                    )
                except Exception:
                    pass

            if not installed:
                self._control_channel.close()

                if process.hProcess:
                    try:
                        _kernel32.TerminateProcess(
                            process.hProcess,
                            0,
                        )
                    except Exception:
                        pass

                if hpcon:
                    try:
                        _kernel32.ClosePseudoConsole(
                            hpcon
                        )
                    except Exception:
                        pass

                _close_handle(
                    input_read
                )

                _close_handle(
                    input_write
                )

                _close_handle(
                    output_read
                )

                _close_handle(
                    output_write
                )

                _close_handle(
                    process.hThread
                )

                _close_handle(
                    process.hProcess
                )

    @staticmethod
    def _find_console_decorated_marker(
        buffer,
        marker,
    ):
        if not marker:
            return None, None

        size = len(buffer)

        def match_from(
            raw_index,
            marker_index,
            replay_allowed,
            memo,
        ):
            key = (
                raw_index,
                marker_index,
                replay_allowed,
            )

            if key in memo:
                return memo[key]

            if marker_index == len(marker):
                result = (
                    "match",
                    raw_index,
                )
                memo[key] = result
                return result

            if raw_index >= size:
                result = (
                    "partial",
                    None,
                )
                memo[key] = result
                return result

            value = buffer[raw_index]

            if value in (
                0x0A,
                0x0D,
            ):
                result = match_from(
                    raw_index + 1,
                    marker_index,
                    True,
                    memo,
                )
                memo[key] = result
                return result

            if value == 0x1B:
                if (
                    raw_index + 1
                    >= size
                ):
                    result = (
                        "partial",
                        None,
                    )
                    memo[key] = result
                    return result

                if (
                    buffer[raw_index + 1]
                    != 0x5B
                ):
                    result = (
                        "fail",
                        None,
                    )
                    memo[key] = result
                    return result

                sequence_index = (
                    raw_index + 2
                )

                while (
                    sequence_index
                    < size
                ):
                    final = buffer[
                        sequence_index
                    ]

                    if (
                        0x40
                        <= final
                        <= 0x7E
                    ):
                        result = match_from(
                            sequence_index + 1,
                            marker_index,
                            True,
                            memo,
                        )
                        memo[key] = result
                        return result

                    sequence_index += 1

                result = (
                    "partial",
                    None,
                )
                memo[key] = result
                return result

            saw_partial = False

            if (
                value
                == marker[marker_index]
            ):
                result = match_from(
                    raw_index + 1,
                    marker_index + 1,
                    False,
                    memo,
                )

                if result[0] == "match":
                    memo[key] = result
                    return result

                if result[0] == "partial":
                    saw_partial = True

            if (
                replay_allowed
                and marker_index > 0
            ):
                maximum = min(
                    marker_index,
                    size - raw_index,
                )

                for replay_length in range(
                    maximum,
                    0,
                    -1,
                ):
                    suffix = marker[
                        marker_index
                        - replay_length:
                        marker_index
                    ]

                    if (
                        buffer[
                            raw_index:
                            raw_index
                            + replay_length
                        ]
                        != suffix
                    ):
                        continue

                    result = match_from(
                        raw_index
                        + replay_length,
                        marker_index,
                        False,
                        memo,
                    )

                    if result[0] == "match":
                        memo[key] = result
                        return result

                    if result[0] == "partial":
                        saw_partial = True

                remaining = (
                    size - raw_index
                )

                for replay_length in range(
                    marker_index,
                    remaining,
                    -1,
                ):
                    suffix = marker[
                        marker_index
                        - replay_length:
                        marker_index
                    ]

                    if (
                        buffer[
                            raw_index:
                        ]
                        == suffix[
                            :remaining
                        ]
                    ):
                        saw_partial = True
                        break

            if saw_partial:
                result = (
                    "partial",
                    None,
                )
            else:
                result = (
                    "fail",
                    None,
                )

            memo[key] = result
            return result

        partial_start = None

        for start in range(size):
            if buffer[start] != marker[0]:
                continue

            result = match_from(
                start,
                0,
                False,
                {},
            )

            if result[0] == "match":
                return (
                    (
                        start,
                        result[1],
                    ),
                    partial_start,
                )

            if result[0] == "partial":
                if (
                    partial_start is None
                    or start < partial_start
                ):
                    partial_start = start

        return None, partial_start

    @staticmethod
    def _safe_prefix_length(
        buffer,
        prefixes,
    ):
        keep = 0

        for prefix in prefixes:
            if not prefix:
                continue

            maximum = min(
                len(buffer),
                len(prefix) - 1,
            )

            for length in range(
                maximum,
                0,
                -1,
            ):
                if (
                    buffer[-length:]
                    == prefix[:length]
                ):
                    keep = max(
                        keep,
                        length,
                    )

                    break

        return keep

    @staticmethod
    def _line_end(
        buffer,
        start,
    ):
        carriage = buffer.find(
            b"\r",
            start,
        )

        newline = buffer.find(
            b"\n",
            start,
        )

        positions = [
            value
            for value in (
                carriage,
                newline,
            )
            if value >= 0
        ]

        if not positions:
            return None

        end = min(
            positions
        )

        if (
            end
            == len(
                buffer
            ) - 1
        ):
            return None

        consume = (
            end + 1
        )

        if buffer[
            end:end + 2
        ] in (
            b"\r\n",
            b"\n\r",
        ):
            consume += 1

        return (
            end,
            consume,
        )

    @staticmethod
    def _visible_protocol_partial_start(
        data,
    ):
        prefixes = (
            b"~CBFS",
            b"~CBFE",
        )

        start = max(
            0,
            len(data) - 37,
        )

        for index in range(
            start,
            len(data),
        ):
            if data[index:index + 1] != b"~":
                continue

            suffix = data[index:]

            if any(
                prefix.startswith(
                    suffix
                )
                for prefix in prefixes
            ):
                return index

            if (
                len(suffix) >= 5
                and suffix[:5]
                in prefixes
            ):
                token = suffix[5:]

                if (
                    len(token) <= 32
                    and all(
                        byte
                        in b"0123456789abcdefABCDEF"
                        for byte in token
                    )
                ):
                    return index

        return None

    def _filter_visible_protocol_bytes(
        self,
        data,
    ):
        self._visible_protocol_filter_buffer.extend(
            bytes(
                data
            )
        )

        pending = bytes(
            self._visible_protocol_filter_buffer
        )

        filtered = re.sub(
            rb"~CBF[SE][0-9A-Fa-f]{32}~",
            b"",
            pending,
        )

        partial_start = (
            self._visible_protocol_partial_start(
                filtered
            )
        )

        if partial_start is None:
            self._visible_protocol_filter_buffer.clear()

            return filtered

        visible = filtered[
            :partial_start
        ]

        self._visible_protocol_filter_buffer[:] = (
            filtered[
                partial_start:
            ]
        )

        return visible

    def _emit_visible_bytes(
        self,
        data,
    ):
        if not data:
            return

        with self._state_lock:
            callback = (
                self._output_callback
            )

            if callback is None:
                self._visible_protocol_filter_buffer.clear()
                return

            visible = (
                self._filter_visible_protocol_bytes(
                    data
                )
            )

        if not visible:
            return

        try:
            callback(
                visible
            )

        except Exception:
            pass

    @staticmethod
    def _emit_execution_text(
        state,
        data,
    ):
        if not data:
            return

        text = state[
            "decoder"
        ].decode(
            bytes(
                data
            ),
            final=False,
        )

        callback = state[
            "on_output"
        ]

        if (
            text
            and callback is not None
        ):
            try:
                callback(
                    text
                )

            except Exception:
                pass

    @staticmethod
    def _append_execution_bytes(
        state,
        data,
        chunks,
    ):
        if not data:
            return

        chunk = bytes(
            data
        )

        state[
            "output"
        ].extend(
            chunk
        )

        chunks.append(
            chunk
        )

    def _complete_execution_locked(
        self,
        state,
    ):
        state[
            "done"
        ] = True

        if (
            self._execution_state
            is state
        ):
            self._execution_state = None

        return state[
            "event"
        ]

    def _process_execution_bytes(
        self,
        data,
    ):
        execution_chunks = []
        visible_chunks = []
        completion_event = None
        state = None

        with self._state_lock:
            state = (
                self._execution_state
            )

            if state is not None:
                buffer = state[
                    "buffer"
                ]

                buffer.extend(
                    data
                )

                while True:
                    phase = state[
                        "phase"
                    ]

                    if phase == "WAIT_START_FENCE":
                        marker = state.get(
                            "control_start_fence"
                        )

                        if not marker:
                            break

                        position = buffer.find(
                            marker
                        )

                        marker_end = None
                        partial_start = None

                        if position >= 0:
                            marker_end = (
                                position
                                + len(marker)
                            )

                        else:
                            (
                                decorated_match,
                                partial_start,
                            ) = (
                                self._find_console_decorated_marker(
                                    buffer,
                                    marker,
                                )
                            )

                            if decorated_match is not None:
                                (
                                    position,
                                    marker_end,
                                ) = decorated_match

                        if position < 0:
                            keep = (
                                self._safe_prefix_length(
                                    buffer,
                                    (
                                        marker,
                                    ),
                                )
                            )

                            safe_length = (
                                len(buffer)
                                - keep
                            )

                            if partial_start is not None:
                                safe_length = min(
                                    safe_length,
                                    partial_start,
                                )

                            if safe_length > 0:
                                visible_chunks.append(
                                    bytes(
                                        buffer[
                                            :safe_length
                                        ]
                                    )
                                )

                                del buffer[
                                    :safe_length
                                ]

                            break

                        if position > 0:
                            visible_chunks.append(
                                bytes(
                                    buffer[
                                        :position
                                    ]
                                )
                            )

                        del buffer[
                            :marker_end
                        ]

                        state[
                            "phase"
                        ] = "CAPTURE"

                        continue

                    if phase == "CAPTURE":
                        marker = state.get(
                            "control_end_fence"
                        )

                        if not marker:
                            if buffer:
                                chunk = bytes(
                                    buffer
                                )

                                self._append_execution_bytes(
                                    state,
                                    chunk,
                                    execution_chunks,
                                )

                                buffer.clear()

                            break

                        position = buffer.find(
                            marker
                        )

                        marker_end = None
                        partial_start = None

                        if position >= 0:
                            marker_end = (
                                position
                                + len(marker)
                            )

                        else:
                            (
                                decorated_match,
                                partial_start,
                            ) = (
                                self._find_console_decorated_marker(
                                    buffer,
                                    marker,
                                )
                            )

                            if decorated_match is not None:
                                (
                                    position,
                                    marker_end,
                                ) = decorated_match

                        if position < 0:
                            keep = (
                                self._safe_prefix_length(
                                    buffer,
                                    (
                                        marker,
                                    ),
                                )
                            )

                            safe_length = (
                                len(buffer)
                                - keep
                            )

                            if partial_start is not None:
                                safe_length = min(
                                    safe_length,
                                    partial_start,
                                )

                            if safe_length > 0:
                                chunk = bytes(
                                    buffer[
                                        :safe_length
                                    ]
                                )

                                self._append_execution_bytes(
                                    state,
                                    chunk,
                                    execution_chunks,
                                )

                                del buffer[
                                    :safe_length
                                ]

                            break

                        if position > 0:
                            chunk = bytes(
                                buffer[
                                    :position
                                ]
                            )

                            self._append_execution_bytes(
                                state,
                                chunk,
                                execution_chunks,
                            )

                        residual = bytes(
                            buffer[
                                marker_end:
                            ]
                        )

                        buffer.clear()

                        if not state.get(
                            "control_begin_seen",
                            False,
                        ):
                            state[
                                "error"
                            ] = RuntimeError(
                                "BEGIN ausente no canal "
                                "de controle Windows"
                            )

                        elif not state.get(
                            "control_end_seen",
                            False,
                        ):
                            state[
                                "error"
                            ] = RuntimeError(
                                "END ausente no canal "
                                "de controle Windows"
                            )

                        elif state.get(
                            "control_failed"
                        ) is None:
                            state[
                                "error"
                            ] = RuntimeError(
                                "Status ausente no canal "
                                "de controle Windows"
                            )

                        elif state.get(
                            "control_exit_code"
                        ) is None:
                            state[
                                "error"
                            ] = RuntimeError(
                                "Exit code ausente no canal "
                                "de controle Windows"
                            )

                        else:
                            state[
                                "failed"
                            ] = bool(
                                state[
                                    "control_failed"
                                ]
                            )

                            state[
                                "exit_code"
                            ] = int(
                                state[
                                    "control_exit_code"
                                ]
                            )

                        if self._cancel_requested:
                            state[
                                "cancelled"
                            ] = True

                            state[
                                "exit_code"
                            ] = 130

                        completion_event = (
                            self._complete_execution_locked(
                                state
                            )
                        )

                        if residual:
                            visible_chunks.append(
                                residual
                            )

                        break

                    state[
                        "error"
                    ] = RuntimeError(
                        "Estado interno do parser "
                        "PowerShell invalido"
                    )

                    completion_event = (
                        self._complete_execution_locked(
                            state
                        )
                    )

                    break

        if state is None:
            self._emit_visible_bytes(
                data
            )

            return

        for chunk in execution_chunks:
            self._emit_execution_text(
                state,
                chunk,
            )

            self._emit_visible_bytes(
                chunk
            )

        for chunk in visible_chunks:
            self._emit_visible_bytes(
                chunk
            )

        if completion_event is not None:
            completion_event.set()

    def _process_received(
        self,
        data,
    ):
        with self._state_lock:
            executing = (
                self._execution_state
                is not None
            )

        if executing:
            self._process_execution_bytes(
                data
            )

            return

        self._emit_visible_bytes(
            data
        )

    @staticmethod
    def _transport_for_script(
        script,
    ):
        encoded = base64.b64encode(
            script.encode(
                "utf-8"
            )
        ).decode(
            "ascii"
        )

        return (
            "$__cb_transport="
            "[Text.Encoding]::UTF8.GetString("
            "[Convert]::FromBase64String('"
            + encoded
            + "'));"
            ".([ScriptBlock]::Create("
            "$__cb_transport));"
            "Remove-Variable __cb_transport "
            "-ErrorAction SilentlyContinue"
        )

    def _reader_loop(
        self,
    ):
        while not self._reader_stop.is_set():
            with self._state_lock:
                output_read = (
                    self._output_read
                )

            if not output_read:
                break

            buffer = ctypes.create_string_buffer(
                8192
            )

            read = wintypes.DWORD()

            ok = _kernel32.ReadFile(
                output_read,
                buffer,
                len(buffer),
                ctypes.byref(
                    read
                ),
                None,
            )

            if not ok:
                error_code = (
                    ctypes.get_last_error()
                )

                if error_code not in (
                    ERROR_BROKEN_PIPE,
                    ERROR_INVALID_HANDLE,
                ):
                    with self._state_lock:
                        self._last_error = OSError(
                            error_code,
                            "ReadFile do ConPTY falhou",
                        )

                break

            if read.value == 0:
                continue

            payload = bytes(
                buffer.raw[
                    :read.value
                ]
            )

            self._process_received(
                payload
            )

    def prepare_command(
        self,
        command,
        character_delay=0.0,
        cancel_event=None,
    ):
        if not isinstance(
            command,
            str,
        ):
            raise TypeError(
                "command deve ser str"
            )

        if not command.strip():
            raise ValueError(
                "command nao pode ser vazio"
            )

        if (
            isinstance(
                character_delay,
                bool,
            )
            or not isinstance(
                character_delay,
                (int, float),
            )
            or character_delay < 0
        ):
            raise ValueError(
                "character_delay deve ser numero nao negativo"
            )

        if (
            cancel_event is not None
            and (
                not callable(
                    getattr(
                        cancel_event,
                        "is_set",
                        None,
                    )
                )
                or not callable(
                    getattr(
                        cancel_event,
                        "wait",
                        None,
                    )
                )
            )
        ):
            raise TypeError(
                "cancel_event deve oferecer is_set() e wait()"
            )

        if not self.is_running:
            raise RuntimeError(
                "Terminal PowerShell ConPTY nao esta aberto"
            )

        if self.is_executing:
            raise RuntimeError(
                "PowerShell ocupado com automacao"
            )

        def cancelled():
            return (
                cancel_event is not None
                and cancel_event.is_set()
            )

        normalized = (
            command.replace(
                "\r\n",
                "\n",
            ).replace(
                "\r",
                "\n",
            )
        )

        lines = normalized.split(
            "\n"
        )

        delay = float(
            character_delay
        )

        if cancelled():
            return False

        self.send(
            self._native_clear_line_sequence
        )

        for index, line in enumerate(
            lines
        ):
            if cancelled():
                return False

            if delay <= 0:
                if line:
                    self.send(
                        line
                    )

            else:
                for char in line:
                    if cancelled():
                        return False

                    self.send(
                        char
                    )

                    if cancel_event is not None:
                        if cancel_event.wait(
                            delay
                        ):
                            return False

                    else:
                        time.sleep(
                            delay
                        )

            if index < len(lines) - 1:
                if cancelled():
                    return False

                self.send(
                    self._native_add_line_sequence
                )

        return not cancelled()

    def execute(
        self,
        command,
        on_output=None,
        prepared=False,
    ):
        if not isinstance(
            command,
            str,
        ):
            raise TypeError(
                "command deve ser str"
            )

        if not command.strip():
            raise ValueError(
                "command nao pode ser vazio"
            )

        if (
            on_output is not None
            and not callable(
                on_output
            )
        ):
            raise TypeError(
                "on_output deve ser callable ou None"
            )

        if not isinstance(
            prepared,
            bool,
        ):
            raise TypeError(
                "prepared deve ser bool"
            )

        if not self.is_running:
            raise RuntimeError(
                "Terminal PowerShell ConPTY nao esta aberto"
            )

        acquired = (
            self._execution_lock.acquire(
                blocking=False
            )
        )

        if not acquired:
            raise RuntimeError(
                "Ja existe um comando PowerShell em execucao"
            )

        state = None

        try:
            state = {
                "buffer": bytearray(),
                "output": bytearray(),
                "decoder": (
                    codecs.getincrementaldecoder(
                        "utf-8"
                    )(
                        errors="replace"
                    )
                ),
                "on_output": on_output,
                "phase": "WAIT_START_FENCE",
                "accepted": False,
                "control_begin_seen": False,
                "control_execution_id": None,
                "control_end_seen": False,
                "control_failed": None,
                "control_exit_code": None,
                "control_start_fence_token": None,
                "control_start_fence": None,
                "control_end_fence_token": None,
                "control_end_fence": None,
                "failed": False,
                "exit_code": None,
                "error_message": "",
                "error": None,
                "cancelled": False,
                "done": False,
                "event": threading.Event(),
            }

            with self._state_lock:
                if self._executing:
                    raise RuntimeError(
                        "Ja existe um comando PowerShell em execucao"
                    )

                self._executing = True
                self._cancel_requested = False
                self._execution_state = state

            try:
                if not prepared:
                    normalized_command = (
                        command.replace(
                            "\r\n",
                            "\n",
                        ).replace(
                            "\r",
                            "\n",
                        )
                    )

                    command_lines = (
                        normalized_command.split(
                            "\n"
                        )
                    )

                    for index, line in enumerate(
                        command_lines
                    ):
                        self.send(
                            line
                        )

                        if index < len(
                            command_lines
                        ) - 1:
                            self.send(
                                self._native_add_line_sequence
                            )

                    time.sleep(
                        self._native_input_settle_delay
                    )

                with self._state_lock:
                    cancelled = (
                        self._cancel_requested
                    )

                    if not cancelled:
                        state[
                            "accepted"
                        ] = True

                if not cancelled:
                    self.send(
                        self._native_accept_sequence
                    )

            except Exception as error:
                raise PowerShellSessionInterrupted(
                    "Falha ao enviar comando "
                    "ao ConPTY PowerShell",
                    output="",
                ) from error

            state[
                "event"
            ].wait()

            remaining = state[
                "decoder"
            ].decode(
                b"",
                final=True,
            )

            if (
                remaining
                and on_output is not None
            ):
                try:
                    on_output(
                        remaining
                    )

                except Exception:
                    pass

            output = bytes(
                state[
                    "output"
                ]
            ).decode(
                "utf-8",
                errors="replace",
            )

            output = output.replace(
                "\r\n",
                "\n",
            )

            parser_error = state[
                "error"
            ]

            if parser_error is not None:
                raise PowerShellSessionInterrupted(
                    str(
                        parser_error
                    ),
                    output=output,
                ) from parser_error

            if state[
                "cancelled"
            ]:
                raise PowerShellCommandCancelled(
                    "Comando PowerShell cancelado",
                    output=output,
                )

            exit_code = state[
                "exit_code"
            ]

            if exit_code is None:
                raise PowerShellSessionInterrupted(
                    "Codigo de saida "
                    "PowerShell ausente",
                    output=output,
                )

            if state[
                "failed"
            ]:
                raise PowerShellCommandError(
                    "Comando PowerShell falhou",
                    exit_code=exit_code,
                    output=output,
                )

            return output

        finally:
            with self._state_lock:
                if (
                    state is not None
                    and self._execution_state
                    is state
                ):
                    self._execution_state = None

                self._executing = False
                self._cancel_requested = False

            self._execution_lock.release()

    def cancel_current(
        self,
    ):
        with self._state_lock:
            state = (
                self._execution_state
            )

            if (
                not self._executing
                or state is None
            ):
                return False

            if self._cancel_requested:
                return True

            self._cancel_requested = True

        try:
            self.send_ctrl_c()

        except Exception:
            with self._state_lock:
                if (
                    self._execution_state
                    is state
                ):
                    self._cancel_requested = False

            raise

        time.sleep(
            self._cancel_recovery_delay
        )

        event = None
        visible = b""

        with self._state_lock:
            if (
                self._execution_state
                is state
                and not state[
                    "done"
                ]
            ):
                if state[
                    "buffer"
                ]:
                    visible = bytes(
                        state[
                            "buffer"
                        ]
                    )

                    state[
                        "buffer"
                    ].clear()

                state[
                    "cancelled"
                ] = True

                state[
                    "exit_code"
                ] = 130

                event = (
                    self._complete_execution_locked(
                        state
                    )
                )

        if visible:
            self._emit_visible_bytes(
                visible
            )

        if event is not None:
            event.set()

        return True

    def send(
        self,
        data,
    ):
        if isinstance(
            data,
            str,
        ):
            data = data.encode(
                "utf-8"
            )

        elif isinstance(
            data,
            bytearray,
        ):
            data = bytes(
                data
            )

        elif not isinstance(
            data,
            bytes,
        ):
            raise TypeError(
                "data deve ser bytes ou str"
            )

        if not data:
            return 0

        if not self.is_running:
            raise RuntimeError(
                "Terminal PowerShell ConPTY nao esta aberto"
            )

        with self._state_lock:
            input_write = (
                self._input_write
            )

        if not input_write:
            raise RuntimeError(
                "Pipe de entrada do ConPTY indisponivel"
            )

        total = 0

        with self._write_lock:
            while total < len(data):
                chunk = data[
                    total:
                ]

                buffer = (
                    ctypes.create_string_buffer(
                        chunk
                    )
                )

                written = wintypes.DWORD()

                if not _kernel32.WriteFile(
                    input_write,
                    buffer,
                    len(chunk),
                    ctypes.byref(
                        written
                    ),
                    None,
                ):
                    _raise_win32(
                        "WriteFile do ConPTY falhou"
                    )

                if written.value <= 0:
                    raise RuntimeError(
                        "ConPTY nao aceitou dados de entrada"
                    )

                total += int(
                    written.value
                )

        return total

    def send_line(
        self,
        line,
    ):
        if not isinstance(
            line,
            str,
        ):
            raise TypeError(
                "line deve ser str"
            )

        return self.send(
            line
            + "\r"
        )

    def send_ctrl_c(
        self,
    ):
        return self.send(
            b"\x03"
        )

    def resize(
        self,
        width,
        height,
    ):
        width = max(
            20,
            min(
                32767,
                int(width),
            ),
        )

        height = max(
            5,
            min(
                32767,
                int(height),
            ),
        )

        with self._state_lock:
            self._width = width
            self._height = height
            hpcon = self._hpcon

        if (
            not hpcon
            or not self.is_running
        ):
            return False

        hr = _kernel32.ResizePseudoConsole(
            hpcon,
            COORD(
                width,
                height,
            ),
        )

        if hr != 0:
            raise RuntimeError(
                "ResizePseudoConsole HRESULT="
                + hex(
                    hr
                    & 0xFFFFFFFF
                )
            )

        return True

    def close(
        self,
    ):
        with self._state_lock:
            reader_thread = (
                self._reader_thread
            )

            hpcon = self._hpcon
            input_write = self._input_write
            output_read = self._output_read

            process_handle = (
                self._process_handle
            )

            thread_handle = (
                self._thread_handle
            )

            self._reader_stop.set()

            self._reader_thread = None

            self._hpcon = None
            self._input_write = None
            self._output_read = None

            self._process_handle = None
            self._thread_handle = None
            self._pid = None

            self._output_callback = None

        self._control_channel.close()

        _close_handle(
            input_write
        )

        if process_handle:
            exit_code = wintypes.DWORD()

            running = (
                _kernel32.GetExitCodeProcess(
                    process_handle,
                    ctypes.byref(
                        exit_code
                    ),
                )
                and exit_code.value
                == STILL_ACTIVE
            )

            if running:
                try:
                    _kernel32.TerminateProcess(
                        process_handle,
                        0,
                    )
                except Exception:
                    pass

        if hpcon:
            try:
                _kernel32.ClosePseudoConsole(
                    hpcon
                )
            except Exception:
                pass

        _close_handle(
            output_read
        )

        if (
            reader_thread is not None
            and reader_thread.is_alive()
            and reader_thread
            is not threading.current_thread()
        ):
            reader_thread.join(
                timeout=1.0
            )

        _close_handle(
            thread_handle
        )

        _close_handle(
            process_handle
        )

        return True

