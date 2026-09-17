import base64
import codecs
import socket
import threading
import time
import uuid
from pathlib import Path

import paramiko

from terminal_errors import (
    SSHCommandCancelled,
    SSHCommandError,
    SSHSessionInterrupted,
)


def _codebridge_linux_pty_diag(
    message,
):
    try:
        path = (
            Path.home()
            / "AppData"
            / "Local"
            / "CodeBridge-MCP-Bridge"
            / "linux_tab_diag.log"
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                f"{time.time():.6f} "
                + "PTY "
                + str(message)
                + "\n"
            )

    except Exception:
        pass


class LinuxTerminalSession:
    def __init__(
        self,
        host,
        username,
        password,
        port=22,
        connect_timeout=10,
    ):
        self.host = host
        self.username = username
        self.port = int(port)

        self._password = password
        self._connect_timeout = connect_timeout

        self._client = None
        self._transport = None
        self._channel = None

        self._reader_thread = None
        self._reader_stop = threading.Event()
        self._state_lock = threading.RLock()

        self._on_output = None
        self._output_decoder = None

        self._prompt_marker = None
        self._begin_marker = None
        self._status_prefix = None
        self._prompt_ready = False
        self._prompt_ready_event = threading.Event()
        self._startup_buffer = bytearray()
        self._idle_buffer = bytearray()

        self._execution_lock = threading.Lock()
        self._execution_state = None
        self._executing = False
        self._cancel_requested = False

        self._debug_last_resize_at = None
        self._debug_last_input_at = None
        self._debug_input_seq = 0

    @property
    def is_running(
        self,
    ):
        with self._state_lock:
            transport = self._transport
            channel = self._channel

        return bool(
            transport is not None
            and transport.is_active()
            and channel is not None
            and not channel.closed
        )

    @property
    def is_executing(
        self,
    ):
        with self._state_lock:
            return self._executing

    def set_output_callback(
        self,
        on_output,
    ):
        if (
            on_output is not None
            and not callable(
                on_output
            )
        ):
            raise TypeError(
                "on_output deve ser callable ou None"
            )

        with self._state_lock:
            self._on_output = on_output

    @staticmethod
    def _safe_prefix_length(
        buffer,
        prefixes,
    ):
        keep = 0

        for prefix in prefixes:
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

    def _emit_visible_bytes(
        self,
        data,
    ):
        if not data:
            return

        with self._state_lock:
            callback = self._on_output
            decoder = self._output_decoder

            debug_input_at = (
                self._debug_last_input_at
            )

            debug_input_seq = (
                self._debug_input_seq
            )

        if debug_input_at is not None:
            debug_age = (
                time.perf_counter()
                - debug_input_at
            )

            if (
                debug_age >= 0
                and debug_age <= 5.0
            ):
                _codebridge_linux_pty_diag(
                    "EMIT_AFTER_INPUT "
                    + "seq="
                    + str(debug_input_seq)
                    + " age_ms="
                    + f"{debug_age * 1000.0:.1f}"
                    + " bytes="
                    + str(len(data))
                    + " raw="
                    + repr(
                        bytes(data[:300])
                    )
                )

        if decoder is None:
            return

        text = decoder.decode(
            bytes(data),
            final=False,
        )

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
    def _emit_execution_text(
        state,
        data,
    ):
        if not data:
            return

        decoder = state[
            "decoder"
        ]

        text = decoder.decode(
            bytes(data),
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
        execution_chunks,
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

        execution_chunks.append(
            chunk
        )

    def _process_startup_bytes(
        self,
        data,
    ):
        visible = b""
        ready = False

        with self._state_lock:
            marker = self._prompt_marker

            self._startup_buffer.extend(
                data
            )

            buffer = self._startup_buffer

            position = buffer.find(
                marker
            )

            if position < 0:
                keep = self._safe_prefix_length(
                    buffer,
                    (
                        marker,
                    ),
                )

                safe_length = (
                    len(buffer)
                    - keep
                )

                if safe_length > 0:
                    del buffer[
                        :safe_length
                    ]

                return

            end = (
                position
                + len(marker)
            )

            visible = (
                b"\x1b[H\x1b[2J\x1b[3J"
                + bytes(
                    buffer[
                        end:
                    ]
                )
            )

            buffer.clear()

            self._prompt_ready = True
            ready = True

        if ready:
            self._prompt_ready_event.set()

        if visible:
            self._process_idle_bytes(
                visible
            )

    def _process_idle_bytes(
        self,
        data,
    ):
        chunks = []

        with self._state_lock:
            marker = self._prompt_marker

            self._idle_buffer.extend(
                data
            )

            buffer = self._idle_buffer

            while True:
                position = buffer.find(
                    marker
                )

                if position >= 0:
                    if position > 0:
                        chunks.append(
                            bytes(
                                buffer[
                                    :position
                                ]
                            )
                        )

                    del buffer[
                        :position
                        + len(marker)
                    ]

                    continue

                keep = self._safe_prefix_length(
                    buffer,
                    (
                        marker,
                    ),
                )

                safe_length = (
                    len(buffer)
                    - keep
                )

                if safe_length > 0:
                    chunks.append(
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

        for chunk in chunks:
            self._emit_visible_bytes(
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
        display_events = []

        class _ChunkSink:
            def __init__(
                self,
                kind,
            ):
                self.kind = kind

            def append(
                self,
                chunk,
            ):
                display_events.append(
                    (
                        self.kind,
                        chunk,
                    )
                )

        visible_chunks = _ChunkSink(
            "visible"
        )

        execution_chunks = _ChunkSink(
            "execution"
        )

        completion_event = None

        with self._state_lock:
            state = self._execution_state

            if state is None:
                pass

            else:
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

                    if phase == "BEGIN":
                        begin_marker = state[
                            "begin_marker"
                        ]

                        prompt_marker = (
                            self._prompt_marker
                        )

                        begin_position = (
                            buffer.find(
                                begin_marker
                            )
                        )

                        prompt_position = (
                            buffer.find(
                                prompt_marker
                            )
                        )

                        if (
                            prompt_position >= 0
                            and (
                                begin_position < 0
                                or prompt_position
                                < begin_position
                            )
                        ):
                            if prompt_position > 0:
                                visible_chunks.append(
                                    bytes(
                                        buffer[
                                            :prompt_position
                                        ]
                                    )
                                )

                            del buffer[
                                :prompt_position
                                + len(
                                    prompt_marker
                                )
                            ]

                            continue

                        if begin_position < 0:
                            keep = (
                                self._safe_prefix_length(
                                    buffer,
                                    (
                                        begin_marker,
                                        prompt_marker,
                                    ),
                                )
                            )

                            safe_length = (
                                len(buffer)
                                - keep
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

                        if begin_position > 0:
                            visible_chunks.append(
                                bytes(
                                    buffer[
                                        :begin_position
                                    ]
                                )
                            )

                        del buffer[
                            :begin_position
                            + len(
                                begin_marker
                            )
                        ]

                        state[
                            "phase"
                        ] = "CAPTURE"

                        continue

                    if phase == "CAPTURE":
                        begin_marker = state[
                            "begin_marker"
                        ]

                        status_prefix = state[
                            "status_prefix"
                        ]

                        prompt_marker = (
                            self._prompt_marker
                        )

                        begin_position = (
                            buffer.find(
                                begin_marker
                            )
                        )

                        status_position = (
                            buffer.find(
                                status_prefix
                            )
                        )

                        prompt_position = (
                            buffer.find(
                                prompt_marker
                            )
                        )

                        candidates = [
                            (
                                position,
                                kind,
                            )
                            for position, kind in (
                                (
                                    begin_position,
                                    "BEGIN",
                                ),
                                (
                                    status_position,
                                    "STATUS",
                                ),
                                (
                                    prompt_position,
                                    "PROMPT",
                                ),
                            )
                            if position >= 0
                        ]

                        if candidates:
                            position, kind = min(
                                candidates,
                                key=lambda item: item[
                                    0
                                ],
                            )

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

                                del buffer[
                                    :position
                                ]

                            if kind == "BEGIN":
                                del buffer[
                                    :len(
                                        begin_marker
                                    )
                                ]

                                continue

                            if kind == "STATUS":
                                terminator = (
                                    buffer.find(
                                        b"\x07",
                                        len(
                                            status_prefix
                                        ),
                                    )
                                )

                                if terminator < 0:
                                    break

                                value = bytes(
                                    buffer[
                                        len(
                                            status_prefix
                                        ):
                                        terminator
                                    ]
                                ).strip()

                                try:
                                    exit_code = int(
                                        value.decode(
                                            "ascii"
                                        )
                                    )

                                    if (
                                        self._cancel_requested
                                    ):
                                        state[
                                            "cancelled"
                                        ] = True

                                        state[
                                            "exit_code"
                                        ] = 130

                                    else:
                                        state[
                                            "exit_code"
                                        ] = exit_code

                                except ValueError:
                                    state[
                                        "error"
                                    ] = SSHSessionInterrupted(
                                        "Codigo de saida Linux invalido",
                                        output=bytes(
                                            state[
                                                "output"
                                            ]
                                        ).decode(
                                            "utf-8",
                                            errors="replace",
                                        ),
                                    )

                                del buffer[
                                    :terminator + 1
                                ]

                                state[
                                    "phase"
                                ] = "WAIT_PROMPT"

                                continue

                            residual = bytes(
                                buffer[
                                    len(
                                        prompt_marker
                                    ):
                                ]
                            )

                            buffer.clear()

                            if self._cancel_requested:
                                state[
                                    "cancelled"
                                ] = True

                                state[
                                    "exit_code"
                                ] = 130

                            else:
                                state[
                                    "error"
                                ] = SSHSessionInterrupted(
                                    "Prompt Linux retornou antes do marcador de status",
                                    output=bytes(
                                        state[
                                            "output"
                                        ]
                                    ).decode(
                                        "utf-8",
                                        errors="replace",
                                    ),
                                )

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

                        keep = (
                            self._safe_prefix_length(
                                buffer,
                                (
                                    begin_marker,
                                    status_prefix,
                                    prompt_marker,
                                ),
                            )
                        )

                        safe_length = (
                            len(buffer)
                            - keep
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

                    if phase == "WAIT_PROMPT":
                        prompt_marker = (
                            self._prompt_marker
                        )

                        position = buffer.find(
                            prompt_marker
                        )

                        if position < 0:
                            keep = (
                                self._safe_prefix_length(
                                    buffer,
                                    (
                                        prompt_marker,
                                    ),
                                )
                            )

                            safe_length = (
                                len(buffer)
                                - keep
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

                        residual = bytes(
                            buffer[
                                position
                                + len(
                                    prompt_marker
                                ):
                            ]
                        )

                        buffer.clear()

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
                    ] = SSHSessionInterrupted(
                        "Estado interno da PTY Linux invalido",
                        output=bytes(
                            state[
                                "output"
                            ]
                        ).decode(
                            "utf-8",
                            errors="replace",
                        ),
                    )

                    completion_event = (
                        self._complete_execution_locked(
                            state
                        )
                    )

                    break

        if state is None:
            self._process_idle_bytes(
                data
            )

            return

        for kind, chunk in display_events:
            if kind == "execution":
                self._emit_execution_text(
                    state,
                    chunk,
                )

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
            ready = self._prompt_ready
            executing = (
                self._execution_state
                is not None
            )

        if not ready:
            self._process_startup_bytes(
                data
            )

            return

        if executing:
            self._process_execution_bytes(
                data
            )

            return

        self._process_idle_bytes(
            data
        )

    def _fail_active_execution(
        self,
        error,
    ):
        event = None

        with self._state_lock:
            state = self._execution_state

            if state is None:
                return

            if state[
                "done"
            ]:
                return

            state[
                "error"
            ] = error

            event = (
                self._complete_execution_locked(
                    state
                )
            )

        if event is not None:
            event.set()

    def _reader_loop(
        self,
    ):
        try:
            while not self._reader_stop.is_set():
                with self._state_lock:
                    channel = self._channel

                if channel is None:
                    break

                if channel.recv_ready():
                    data = channel.recv(
                        65536
                    )

                    if not data:
                        self._fail_active_execution(
                            SSHSessionInterrupted(
                                "Canal SSH foi encerrado",
                                output="",
                            )
                        )

                        break

                    with self._state_lock:
                        debug_resize_at = (
                            self._debug_last_resize_at
                        )

                        debug_prompt_marker = (
                            self._prompt_marker
                        )

                        debug_input_at = (
                            self._debug_last_input_at
                        )

                        debug_input_seq = (
                            self._debug_input_seq
                        )

                    if debug_input_at is not None:
                        debug_input_age = (
                            time.perf_counter()
                            - debug_input_at
                        )

                        if (
                            debug_input_age >= 0
                            and debug_input_age <= 5.0
                        ):
                            input_prompt_count = (
                                0
                                if debug_prompt_marker
                                is None
                                else bytes(data).count(
                                    debug_prompt_marker
                                )
                            )

                            _codebridge_linux_pty_diag(
                                "RECV_AFTER_INPUT "
                                + "seq="
                                + str(debug_input_seq)
                                + " age_ms="
                                + f"{debug_input_age * 1000.0:.1f}"
                                + " bytes="
                                + str(len(data))
                                + " prompt_markers="
                                + str(input_prompt_count)
                                + " raw="
                                + repr(
                                    bytes(data[:300])
                                )
                            )

                    if debug_resize_at is not None:
                        debug_age = (
                            time.perf_counter()
                            - debug_resize_at
                        )

                        if (
                            debug_age >= 0
                            and debug_age <= 5.0
                        ):
                            prompt_count = (
                                0
                                if debug_prompt_marker
                                is None
                                else bytes(data).count(
                                    debug_prompt_marker
                                )
                            )

                            _codebridge_linux_pty_diag(
                                "RECV_AFTER_RESIZE "
                                + "age_ms="
                                + f"{debug_age * 1000.0:.1f}"
                                + " bytes="
                                + str(len(data))
                                + " prompt_markers="
                                + str(prompt_count)
                                + " raw="
                                + repr(
                                    bytes(data[:300])
                                )
                            )

                    self._process_received(
                        bytes(data)
                    )

                    continue

                if channel.exit_status_ready():
                    self._fail_active_execution(
                        SSHSessionInterrupted(
                            "Canal SSH foi encerrado",
                            output="",
                        )
                    )

                    break

                self._reader_stop.wait(
                    0.02
                )

        finally:
            self._reader_stop.set()

            self._fail_active_execution(
                SSHSessionInterrupted(
                    "Leitor da PTY Linux foi encerrado",
                    output="",
                )
            )

    @staticmethod
    def _encoded_shell_line(
        shell_text,
    ):
        payload = base64.b64encode(
            shell_text.encode(
                "utf-8"
            )
        ).decode(
            "ascii"
        )

        return (
            "eval \"$(printf '%s' '"
            + payload
            + "' | base64 -d)\""
            + "\n"
        )

    def start(
        self,
        on_output=None,
        width=120,
        height=40,
    ):
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

        with self._state_lock:
            stale_runtime = bool(
                self._client is not None
                or self._transport is not None
                or self._channel is not None
                or self._reader_thread is not None
            )

        if stale_runtime:
            self.close()

        client = paramiko.SSHClient()

        client.load_system_host_keys()

        client.set_missing_host_key_policy(
            paramiko.RejectPolicy()
        )

        channel = None

        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self._password,
                look_for_keys=False,
                allow_agent=False,
                timeout=self._connect_timeout,
                banner_timeout=self._connect_timeout,
                auth_timeout=self._connect_timeout,
            )

            transport = client.get_transport()

            if (
                transport is None
                or not transport.is_active()
            ):
                raise RuntimeError(
                    "Transporte SSH do terminal nao ficou ativo"
                )

            transport.set_keepalive(
                15
            )

            transport_socket = getattr(
                transport,
                "sock",
                None,
            )

            if transport_socket is not None:
                transport_socket.setsockopt(
                    socket.IPPROTO_TCP,
                    socket.TCP_NODELAY,
                    1,
                )

            channel = transport.open_session()

            channel.get_pty(
                term="xterm-256color",
                width=max(
                    20,
                    int(width),
                ),
                height=max(
                    5,
                    int(height),
                ),
            )

            channel.set_combine_stderr(
                True
            )

            channel.exec_command(
                "exec env force_color_prompt=yes bash -il"
            )

            marker_token = (
                uuid.uuid4().hex
            )

            marker_name = (
                "CODEBRIDGE_PROMPT_"
                + marker_token
            )

            begin_name = (
                "CODEBRIDGE_BEGIN_"
                + marker_token
            )

            status_name = (
                "CODEBRIDGE_STATUS_"
                + marker_token
            )

            prompt_marker = (
                b"\x1b]777;"
                + marker_name.encode(
                    "ascii"
                )
                + b"\x07"
            )

            begin_marker = (
                b"\x1b]777;"
                + begin_name.encode(
                    "ascii"
                )
                + b"\x07"
            )

            status_prefix = (
                b"\x1b]777;"
                + status_name.encode(
                    "ascii"
                )
                + b":"
            )

            ready_event = (
                threading.Event()
            )

            with self._state_lock:
                self._client = client
                self._transport = transport
                self._channel = channel

                self._on_output = on_output
                self._output_decoder = (
                    codecs.getincrementaldecoder(
                        "utf-8"
                    )(
                        errors="replace"
                    )
                )

                self._prompt_marker = prompt_marker
                self._begin_marker = begin_marker
                self._status_prefix = status_prefix
                self._prompt_ready = False
                self._prompt_ready_event = ready_event

                self._startup_buffer.clear()
                self._idle_buffer.clear()

                self._execution_state = None
                self._executing = False
                self._cancel_requested = False

                self._reader_stop.clear()

                reader = threading.Thread(
                    target=self._reader_loop,
                    name="CodeBridgeLinuxTerminalReader",
                    daemon=True,
                )

                self._reader_thread = reader

            reader.start()

            setup_prompt = (
                "__cb_active=0\n"
                "__cb_failed=0\n"
                "__cb_started=0\n"
                "__cb_saved_prompt_command=''\n"
                "__cb_saved_err_trap=''\n"
                "__cb_saved_debug_trap=''\n"
                "__cb_extdebug_was_on=0\n"
                "__cb_err() {\n"
                "    local code=$?\n"
                "    if [[ \"$__cb_active\" == \"1\" "
                "&& \"$__cb_failed\" == \"0\" ]]; then\n"
                "        __cb_failed=\"$code\"\n"
                "    fi\n"
                "    return 0\n"
                "}\n"
                "__cb_dbg() {\n"
                "    if [[ \"$__cb_active\" != \"1\" ]]; then\n"
                "        return 0\n"
                "    fi\n"
                "    if [[ \"$__cb_started\" == \"0\" ]]; then\n"
                "        __cb_started=1\n"
                "        printf '\\033]777;"
                + begin_name
                + "\\007'\n"
                "        return 0\n"
                "    fi\n"
                "    if [[ \"${FUNCNAME[1]-}\" == \"__cb_err\" ]]; then\n"
                "        return 0\n"
                "    fi\n"
                "    if [[ \"$BASH_COMMAND\" == \"__cb_err\" ]]; then\n"
                "        return 0\n"
                "    fi\n"
                "    if [[ \"$BASH_COMMAND\" == \"trap - DEBUG\" ]]; then\n"
                "        return 0\n"
                "    fi\n"
                "    if [[ \"$__cb_failed\" != \"0\" ]]; then\n"
                "        return 1\n"
                "    fi\n"
                "    return 0\n"
                "}\n"
                "__cb_finish() {\n"
                "    local code=0\n"
                "    if [[ \"$__cb_active\" != \"1\" ]]; then\n"
                "        return 0\n"
                "    fi\n"
                "    if [[ \"$__cb_failed\" != \"0\" ]]; then\n"
                "        code=\"$__cb_failed\"\n"
                "    fi\n"
                "    trap - ERR\n"
                "    PROMPT_COMMAND=$__cb_saved_prompt_command\n"
                "    if [[ \"$__cb_extdebug_was_on\" != \"0\" ]]; then\n"
                "        shopt -u extdebug\n"
                "    fi\n"
                "    __cb_active=0\n"
                "    __cb_failed=0\n"
                "    __cb_started=0\n"
                "    printf '\\033]777;"
                + status_name
                + ":%s\\007' \"$code\"\n"
                "    if [[ -n \"$__cb_saved_err_trap\" ]]; then\n"
                "        eval \"$__cb_saved_err_trap\"\n"
                "    fi\n"
                "    if [[ -n \"$__cb_saved_debug_trap\" ]]; then\n"
                "        eval \"$__cb_saved_debug_trap\"\n"
                "    fi\n"
                "    if [[ -n \"$__cb_saved_prompt_command\" ]]; then\n"
                "        eval \"$__cb_saved_prompt_command\"\n"
                "    fi\n"
                "}\n"
                "__cb_arm() {\n"
                "    __cb_saved_prompt_command=${PROMPT_COMMAND-}\n"
                "    __cb_saved_err_trap=$(trap -p ERR)\n"
                "    __cb_saved_debug_trap=$(trap -p DEBUG)\n"
                "    shopt -q extdebug\n"
                "    __cb_extdebug_was_on=$?\n"
                "    __cb_active=1\n"
                "    __cb_failed=0\n"
                "    __cb_started=0\n"
                "    PROMPT_COMMAND='trap - DEBUG; __cb_finish'\n"
                "    shopt -s extdebug\n"
                "    trap '__cb_err' ERR\n"
                "    trap '__cb_dbg' DEBUG\n"
                "}\n"
                "PS1="
                "'\\[\\e]777;"
                + marker_name
                + "\\a\\]'"
                "\"$PS1\"\n"
                "bind -x '\"\\e[24~\":__cb_arm'"
            )

            channel.sendall(
                self._encoded_shell_line(
                    setup_prompt
                ).encode(
                    "utf-8"
                )
            )

            if not ready_event.wait(
                timeout=self._connect_timeout
            ):
                raise RuntimeError(
                    "Prompt oculto da PTY Linux nao foi inicializado"
                )

            return True

        except Exception:
            self._reader_stop.set()

            if channel is not None:
                try:
                    channel.close()
                except Exception:
                    pass

            try:
                client.close()
            except Exception:
                pass

            with self._state_lock:
                self._client = None
                self._transport = None
                self._channel = None
                self._reader_thread = None

                self._on_output = None
                self._output_decoder = None

                self._prompt_marker = None
                self._begin_marker = None
                self._status_prefix = None
                self._prompt_ready = False

            raise

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
                "Terminal Linux nao esta conectado"
            )

        if self.is_executing:
            raise RuntimeError(
                "SSH ocupado com automacao"
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

        delay = float(
            character_delay
        )

        multiline = (
            "\n" in normalized
        )

        def cancelled():
            return (
                cancel_event is not None
                and cancel_event.is_set()
            )

        if cancelled():
            return False

        if multiline:
            self.send(
                b"\x1b[200~"
            )

        try:
            if delay <= 0:
                if cancelled():
                    return False

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

        finally:
            if multiline:
                self.send(
                    b"\x1b[201~"
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
                "Terminal Linux nao esta conectado"
            )

        acquired = (
            self._execution_lock.acquire(
                blocking=False
            )
        )

        if not acquired:
            raise RuntimeError(
                "Ja existe um comando Linux em execucao"
            )

        state = None

        try:
            with self._state_lock:
                begin_marker = (
                    self._begin_marker
                )

                status_prefix = (
                    self._status_prefix
                )

            if (
                begin_marker is None
                or status_prefix is None
            ):
                raise SSHSessionInterrupted(
                    "Protocolo do terminal Linux nao esta inicializado",
                    output="",
                )

            event = threading.Event()

            state = {
                "begin_marker": begin_marker,
                "status_prefix": status_prefix,
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
                "phase": "BEGIN",
                "exit_code": None,
                "error": None,
                "cancelled": False,
                "done": False,
                "event": event,
            }

            with self._state_lock:
                if self._executing:
                    raise RuntimeError(
                        "Ja existe um comando Linux em execucao"
                    )

                channel = self._channel

                if (
                    channel is None
                    or channel.closed
                ):
                    raise SSHSessionInterrupted(
                        "Canal SSH indisponivel",
                        output="",
                    )

                self._executing = True
                self._cancel_requested = False
                self._execution_state = state

            normalized_command = (
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

            command_bytes = (
                normalized_command.encode(
                    "utf-8"
                )
            )

            if prepared:
                payload = (
                    b"\x1b[24~"
                    + b"\r"
                )

            elif "\n" in normalized_command:
                payload = (
                    b"\x1b[200~"
                    + command_bytes
                    + b"\x1b[201~"
                    + b"\x1b[24~"
                    + b"\r"
                )

            else:
                payload = (
                    command_bytes
                    + b"\x1b[24~"
                    + b"\r"
                )

            try:
                channel.sendall(
                    payload
                )

            except (
                EOFError,
                OSError,
                paramiko.SSHException,
            ) as error:
                raise SSHSessionInterrupted(
                    "Falha ao enviar comando para PTY Linux",
                    output="",
                ) from error

            event.wait()

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

            error = state[
                "error"
            ]

            if error is not None:
                if isinstance(
                    error,
                    SSHSessionInterrupted,
                ):
                    raise SSHSessionInterrupted(
                        str(error),
                        output=output,
                    ) from error

                raise error

            if state[
                "cancelled"
            ]:
                raise SSHCommandCancelled(
                    "Comando Linux cancelado",
                    output=output,
                )

            exit_code = state[
                "exit_code"
            ]

            if exit_code is None:
                raise SSHSessionInterrupted(
                    "Codigo de saida Linux ausente",
                    output=output,
                )

            if exit_code != 0:
                raise SSHCommandError(
                    "Comando Linux falhou",
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

    def send(
        self,
        data,
    ):
        if isinstance(
            data,
            str,
        ):
            payload = data.encode(
                "utf-8"
            )

        elif isinstance(
            data,
            bytes,
        ):
            payload = data

        else:
            raise TypeError(
                "data deve ser str ou bytes"
            )

        with self._state_lock:
            channel = self._channel

        if (
            channel is None
            or channel.closed
        ):
            raise RuntimeError(
                "Terminal Linux nao esta conectado"
            )

        started = time.perf_counter()

        with self._state_lock:
            self._debug_input_seq += 1

            debug_input_seq = (
                self._debug_input_seq
            )

            self._debug_last_input_at = (
                started
            )

        _codebridge_linux_pty_diag(
            "SEND_CALL "
            + "seq="
            + str(debug_input_seq)
            + " bytes="
            + str(len(payload))
            + " payload="
            + repr(
                bytes(payload[:200])
            )
        )

        try:
            channel.sendall(
                payload
            )

        except Exception as error:
            _codebridge_linux_pty_diag(
                "SEND_ERROR "
                + "seq="
                + str(debug_input_seq)
                + " "
                + type(error).__name__
                + ": "
                + str(error)
            )

            raise

        _codebridge_linux_pty_diag(
            "SEND_DONE "
            + "seq="
            + str(debug_input_seq)
            + " elapsed_ms="
            + (
                f"{(
                    time.perf_counter()
                    - started
                ) * 1000.0:.1f}"
            )
        )

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

        self.send(
            line + "\n"
        )

    def send_ctrl_c(
        self,
    ):
        self.send(
            b"\x03"
        )

    def cancel_current(
        self,
    ):
        with self._state_lock:
            if not self._executing:
                return False

            if self._cancel_requested:
                return True

            self._cancel_requested = True

        try:
            self.send_ctrl_c()

        except Exception:
            with self._state_lock:
                self._cancel_requested = False

            raise

        return True

    def resize(
        self,
        width,
        height,
    ):
        width = max(
            20,
            int(width),
        )

        height = max(
            5,
            int(height),
        )

        with self._state_lock:
            channel = self._channel

        if (
            channel is None
            or channel.closed
        ):
            return False

        started = time.perf_counter()

        with self._state_lock:
            self._debug_last_resize_at = (
                started
            )

        _codebridge_linux_pty_diag(
            "RESIZE_CALL "
            + str(width)
            + "x"
            + str(height)
        )

        try:
            channel.resize_pty(
                width=width,
                height=height,
            )

        except Exception as error:
            _codebridge_linux_pty_diag(
                "RESIZE_ERROR "
                + type(error).__name__
                + ": "
                + str(error)
                + " elapsed_ms="
                + (
                    f"{(
                        time.perf_counter()
                        - started
                    ) * 1000.0:.1f}"
                )
            )

            raise

        _codebridge_linux_pty_diag(
            "RESIZE_DONE "
            + "elapsed_ms="
            + (
                f"{(
                    time.perf_counter()
                    - started
                ) * 1000.0:.1f}"
            )
        )

        return True

    def close(
        self,
    ):
        self._reader_stop.set()

        self._fail_active_execution(
            SSHSessionInterrupted(
                "Terminal Linux foi fechado",
                output="",
            )
        )

        with self._state_lock:
            channel = self._channel
            client = self._client
            reader = self._reader_thread

            self._channel = None
            self._transport = None
            self._client = None
            self._reader_thread = None

            self._on_output = None
            self._output_decoder = None

            self._prompt_marker = None
            self._begin_marker = None
            self._status_prefix = None
            self._prompt_ready = False

            self._startup_buffer.clear()
            self._idle_buffer.clear()

        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass

        if client is not None:
            try:
                client.close()
            except Exception:
                pass

        if (
            reader is not None
            and reader.is_alive()
            and reader is not threading.current_thread()
        ):
            reader.join(
                timeout=2
            )

