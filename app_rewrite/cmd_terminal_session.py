import ctypes
import os
import re
import threading
import time
import uuid
from ctypes import wintypes

from windows_terminal_session import (
    COORD,
    CREATE_UNICODE_ENVIRONMENT,
    ERROR_BROKEN_PIPE,
    ERROR_INVALID_HANDLE,
    EXTENDED_STARTUPINFO_PRESENT,
    PROCESS_INFORMATION,
    PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
    STARTF_USESTDHANDLES,
    STARTUPINFOEXW,
    STILL_ACTIVE,
    _close_handle,
    _kernel32,
    _raise_win32,
)


class CmdCommandError(RuntimeError):
    def __init__(
        self,
        message,
        output="",
        exit_code=None,
    ):
        super().__init__(
            message
        )

        self.output = str(
            output
        )

        self.exit_code = exit_code


class CmdCommandCancelled(RuntimeError):
    def __init__(
        self,
        message,
        output="",
    ):
        super().__init__(
            message
        )

        self.output = str(
            output
        )


class CmdSessionInterrupted(RuntimeError):
    def __init__(
        self,
        message,
        output="",
    ):
        super().__init__(
            message
        )

        self.output = str(
            output
        )


class CmdTerminalSession:
    def __init__(
        self,
        executable=None,
    ):
        if executable is None:
            executable = os.environ.get(
                "ComSpec"
            )

        if not executable:
            executable = os.path.join(
                os.environ.get(
                    "WINDIR",
                    r"C:\Windows",
                ),
                "System32",
                "cmd.exe",
            )

        self._executable = os.path.abspath(
            executable
        )

        self._state_lock = threading.RLock()
        self._write_lock = threading.Lock()

        self._output_callback = None

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

        self._last_error = None

        self._execution_lock = threading.Lock()
        self._execution_state = None
        self._executing = False

    @property
    def is_running(
        self,
    ):
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
    def pid(
        self,
    ):
        if not self.is_running:
            return None

        with self._state_lock:
            return self._pid

    @property
    def last_error(
        self,
    ):
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

    def _emit(
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
            return

        try:
            callback(
                bytes(
                    data
                )
            )

        except Exception:
            pass

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
                len(
                    buffer
                ),
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
                            "ReadFile do CMD ConPTY falhou",
                        )

                break

            if read.value == 0:
                continue

            self._process_received(
                buffer.raw[
                    :read.value
                ]
            )

        with self._state_lock:
            state = self._execution_state

            if state is not None:
                state["interrupted"] = True
                state["done"].set()

    @staticmethod
    def _decode_output(
        data,
    ):
        return bytes(
            data
        ).decode(
            "utf-8",
            errors="replace",
        )

    @staticmethod
    def _clean_execution_capture(
        data,
    ):
        payload = bytes(
            data
        )

        payload = re.sub(
            rb"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)",
            b"",
            payload,
        )

        payload = re.sub(
            rb"\x1b\[[0-?]*[ -/]*[@-~]",
            b"",
            payload,
        )

        return payload

    def _capture_execution_output(
        self,
        state,
        data,
    ):
        if not data:
            return

        captured = (
            self._clean_execution_capture(
                data
            )
        )

        if not captured:
            return

        state["captured"].extend(
            captured
        )

        callback = state.get(
            "on_output"
        )

        if callback is None:
            return

        try:
            callback(
                self._decode_output(
                    captured
                )
            )

        except Exception:
            pass

    def _emit_execution_output(
        self,
        state,
        data,
    ):
        if not data:
            return

        self._emit(
            data
        )

        self._capture_execution_output(
            state,
            data,
        )


    def _clean_marker_visible_capture(
        self,
        data,
    ):
        payload = bytes(
            data
        )

        # O ConPTY pode mover o cursor para a primeira coluna
        # da proxima linha sem entregar um LF real.
        payload = re.sub(
            rb"\x1b\[\d+;1[Hf]",
            b"\n",
            payload,
        )

        payload = (
            self._clean_execution_capture(
                payload
            )
        )

        # Aqui estamos especificamente no trecho imediatamente
        # anterior ao comando marcador interno. Portanto um
        # prompt Windows no final pertence ao terminal, nao ao
        # resultado do comando executado.
        prompt = re.search(
            rb"(?is)(?:^|\n)[A-Za-z]:\\[^\r\n>]*>\s*$",
            payload,
        )

        if prompt is not None:
            payload = payload[
                :prompt.start()
            ]

        else:
            prompt = re.search(
                rb"(?is)[A-Za-z]:\\[^\r\n>]*>\s*$",
                payload,
            )

            if prompt is not None:
                payload = payload[
                    :prompt.start()
                ]

        return payload

    def _complete_execution(
        self,
        state,
        exit_code,
    ):
        with self._state_lock:
            if (
                self._execution_state
                is not state
            ):
                return

            state["exit_code"] = (
                exit_code
            )

            self._execution_state = None
            self._executing = False

            state["done"].set()

    def _find_execution_marker(
        self,
        state,
        data,
    ):
        marker_prefix = state[
            "marker_prefix"
        ]

        pattern = (
            re.escape(
                marker_prefix
            )
            + rb"(-?\d+)"
        )

        return re.search(
            pattern,
            bytes(
                data
            ),
        )

    @staticmethod
    def _strip_marker_command_echo(
        state,
        data,
    ):
        payload = bytes(
            data
        )

        marker_token = state[
            "marker_token"
        ]

        position = payload.find(
            marker_token
        )

        if position < 0:
            return payload

        tail = payload[
            position:
        ].lower()

        if b"%errorlevel%" not in tail:
            return payload

        line_start = payload.rfind(
            b"\n",
            0,
            position,
        )

        if line_start < 0:
            return b""

        return payload[
            :line_start + 1
        ]

    def _process_execution_line(
        self,
        state,
        line,
    ):
        marker_token = state[
            "marker_token"
        ]

        if (
            marker_token in line
            and b"%errorlevel%" in line.lower()
        ):
            marker_position = line.find(
                marker_token
            )

            control_start = line.rfind(
                b"@echo ",
                0,
                marker_position,
            )

            if control_start < 0:
                control_start = line.rfind(
                    b"echo ",
                    0,
                    marker_position,
                )

            if control_start < 0:
                control_start = (
                    marker_position
                )

            visible = line[
                :control_start
            ]

            if visible:
                self._emit(
                    visible
                )

                captured_visible = (
                    self._clean_marker_visible_capture(
                        visible
                    )
                )

                if captured_visible:
                    self._capture_execution_output(
                        state,
                        captured_visible,
                    )

            return

        marker_match = (
            self._find_execution_marker(
                state,
                line,
            )
        )

        if marker_match is not None:
            before = line[
                :marker_match.start()
            ]

            after = line[
                marker_match.end():
            ]

            before = (
                self._strip_marker_command_echo(
                    state,
                    before,
                )
            )

            if before:
                self._emit_execution_output(
                    state,
                    before,
                )

            exit_code = int(
                marker_match.group(
                    1
                ).decode(
                    "ascii"
                )
            )

            self._complete_execution(
                state,
                exit_code,
            )

            if after:
                self._emit(
                    after
                )

            return

        expected = state[
            "expected_echoes"
        ]

        stripped = line.rstrip(
            b"\r\n"
        )

        if expected:
            candidate = expected[
                0
            ]

            if (
                stripped.endswith(
                    candidate
                )
            ):
                expected.pop(
                    0
                )

                self._emit(
                    line
                )

                return

        self._emit_execution_output(
            state,
            line,
        )

    def _process_received(
        self,
        data,
    ):
        if not data:
            return

        with self._state_lock:
            state = self._execution_state

        if state is None:
            self._emit(
                data
            )

            return

        pending = state[
            "pending"
        ]

        pending.extend(
            data
        )

        while True:
            newline_index = pending.find(
                b"\n"
            )

            if newline_index < 0:
                break

            line = bytes(
                pending[
                    :newline_index + 1
                ]
            )

            del pending[
                :newline_index + 1
            ]

            self._process_execution_line(
                state,
                line,
            )

            if state["done"].is_set():
                if pending:
                    self._emit(
                        bytes(
                            pending
                        )
                    )

                    pending.clear()

                return

        marker_match = (
            self._find_execution_marker(
                state,
                pending,
            )
        )

        if marker_match is None:
            return

        before = bytes(
            pending[
                :marker_match.start()
            ]
        )

        after = bytes(
            pending[
                marker_match.end():
            ]
        )

        pending.clear()

        before = (
            self._strip_marker_command_echo(
                state,
                before,
            )
        )

        if before:
            self._emit_execution_output(
                state,
                before,
            )

        exit_code = int(
            marker_match.group(
                1
            ).decode(
                "ascii"
            )
        )

        self._complete_execution(
            state,
            exit_code,
        )

        if after:
            self._emit(
                after
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
                int(
                    width
                ),
            ),
        )

        height = max(
            5,
            min(
                32767,
                int(
                    height
                ),
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
                "cmd.exe nao encontrado"
            )

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
                    "CreatePipe de entrada CMD falhou"
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
                    "CreatePipe de saida CMD falhou"
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
                    "CreatePseudoConsole CMD HRESULT="
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
                    "InitializeProcThreadAttributeList CMD falhou"
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
                    "UpdateProcThreadAttribute CMD falhou"
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

            command_line = (
                ctypes.create_unicode_buffer(
                    '"'
                    + self._executable
                    + '"'
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
                    "CreateProcessW do CMD falhou"
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
                        "CodeBridgeCmdTerminalReader"
                    ),
                    daemon=True,
                )

                self._reader_thread = (
                    reader_thread
                )

            installed = True

            reader_thread.start()

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
                "command CMD vazio"
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
                "Terminal CMD ConPTY nao esta aberto"
            )

        if self.is_executing:
            raise RuntimeError(
                "CMD ocupado com automacao"
            )

        normalized = (
            command.replace(
                "\r\n",
                "\n",
            ).replace(
                "\r",
                "\n",
            ).rstrip(
                "\n"
            )
        )

        if "\n" in normalized:
            return False

        delay = float(
            character_delay
        )

        def cancelled():
            return (
                cancel_event is not None
                and cancel_event.is_set()
            )

        if cancelled():
            return False

        if delay <= 0:
            self.send(
                normalized
            )

        else:
            for char in normalized:
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
                "command CMD vazio"
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
                "Terminal CMD ConPTY nao esta aberto"
            )

        acquired = (
            self._execution_lock.acquire(
                blocking=False
            )
        )

        if not acquired:
            raise RuntimeError(
                "Ja existe um comando CMD em execucao"
            )

        marker_id = uuid.uuid4().hex

        marker_text = (
            "__CODEBRIDGE_CMD_END_"
            + marker_id
            + "__:"
        )

        marker_prefix = marker_text.encode(
            "ascii"
        )

        marker_token = (
            "__CODEBRIDGE_CMD_END_"
            + marker_id
        ).encode(
            "ascii"
        )

        normalized = command.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        command_lines = normalized.split(
            "\n"
        )

        expected_echoes = [
            line.encode(
                "utf-8"
            )
            for line in command_lines
            if line != ""
        ]

        state = {
            "done": threading.Event(),
            "captured": bytearray(),
            "pending": bytearray(),
            "on_output": on_output,
            "marker_prefix": marker_prefix,
            "marker_token": marker_token,
            "expected_echoes": expected_echoes,
            "exit_code": None,
            "cancelled": False,
            "interrupted": False,
        }

        with self._state_lock:
            if self._execution_state is not None:
                self._execution_lock.release()

                raise RuntimeError(
                    "Estado CMD de execucao ocupado"
                )

            self._execution_state = state
            self._executing = True

        try:
            if prepared:
                self.send(
                    b"\r"
                )

            else:
                for line in command_lines:
                    self.send(
                        line.encode(
                            "utf-8"
                        )
                        + b"\r"
                    )

            marker_command = (
                "@echo "
                + marker_text
                + "%errorlevel%"
            )

            self.send(
                marker_command.encode(
                    "ascii"
                )
                + b"\r"
            )

            state["done"].wait()

            captured_bytes = bytes(
                state[
                    "captured"
                ]
            )

            if state["cancelled"]:
                captured_bytes = (
                    self._clean_marker_visible_capture(
                        captured_bytes
                    )
                )

            output = self._decode_output(
                captured_bytes
            )

            output = output.rstrip(
                "\r\n"
            )

            if state["cancelled"]:
                raise CmdCommandCancelled(
                    "Comando CMD cancelado",
                    output=output,
                )

            if state["interrupted"]:
                raise CmdSessionInterrupted(
                    "Sessao CMD interrompida",
                    output=output,
                )

            exit_code = state[
                "exit_code"
            ]

            if exit_code is None:
                raise CmdSessionInterrupted(
                    "Codigo de saida CMD ausente",
                    output=output,
                )

            if exit_code != 0:
                raise CmdCommandError(
                    "Comando CMD falhou",
                    output=output,
                    exit_code=exit_code,
                )

            return output

        finally:
            with self._state_lock:
                if (
                    self._execution_state
                    is state
                ):
                    self._execution_state = None
                    self._executing = False

            self._execution_lock.release()

    def _cancel_completion_worker(
        self,
        state,
    ):
        # Primeiro damos uma pequena janela para o Ctrl+C
        # inicial produzir o marcador normal ja enfileirado.
        if state["done"].wait(
            0.45
        ):
            return

        # Um segundo Ctrl+C ajuda a sair de estados interativos
        # do CMD, inclusive prompts de interrupcao.
        try:
            self.send_ctrl_c()
        except Exception:
            pass

        if state["done"].wait(
            0.20
        ):
            return

        # Se o Ctrl+C descartou o marcador original, reenviamos
        # somente o marcador interno da mesma execucao. Assim o
        # parser consegue concluir pelo caminho normal sempre que
        # o CMD ja voltou ao prompt.
        try:
            recovery_marker = (
                b"@echo "
                + state["marker_prefix"]
                + b"%errorlevel%\r"
            )

            self.send(
                recovery_marker
            )

        except Exception:
            pass

        if state["done"].wait(
            0.45
        ):
            return

        # Ultimo recurso: nunca deixar execute() bloqueado
        # indefinidamente depois de um cancelamento solicitado.
        with self._state_lock:
            if (
                self._execution_state
                is not state
            ):
                return

            if not state.get(
                "cancelled",
                False,
            ):
                return

            if state["done"].is_set():
                return

            state[
                "forced_cancel_completion"
            ] = True

            state["done"].set()

    def cancel_current(
        self,
    ):
        with self._state_lock:
            state = self._execution_state

            if state is None:
                return False

            state["cancelled"] = True

            start_worker = not state.get(
                "cancel_completion_worker_started",
                False,
            )

            if start_worker:
                state[
                    "cancel_completion_worker_started"
                ] = True

        try:
            self.send_ctrl_c()

        except Exception:
            return False

        if start_worker:
            worker = threading.Thread(
                target=self._cancel_completion_worker,
                args=(
                    state,
                ),
                name=(
                    "CodeBridge-CMD-"
                    "CancelCompletion"
                ),
                daemon=True,
            )

            worker.start()

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
                "Terminal CMD ConPTY nao esta aberto"
            )

        with self._state_lock:
            input_write = (
                self._input_write
            )

        if not input_write:
            raise RuntimeError(
                "Pipe de entrada CMD indisponivel"
            )

        total = 0

        with self._write_lock:
            while total < len(
                data
            ):
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
                    len(
                        chunk
                    ),
                    ctypes.byref(
                        written
                    ),
                    None,
                ):
                    _raise_win32(
                        "WriteFile do CMD ConPTY falhou"
                    )

                if written.value <= 0:
                    raise RuntimeError(
                        "CMD ConPTY nao aceitou dados"
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
                int(
                    width
                ),
            ),
        )

        height = max(
            5,
            min(
                32767,
                int(
                    height
                ),
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
                "ResizePseudoConsole CMD HRESULT="
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
            state = self._execution_state

            if state is not None:
                state["interrupted"] = True
                state["done"].set()

            self._execution_state = None
            self._executing = False

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
