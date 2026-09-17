import threading
import uuid

from ipc_named_pipe import (
    NamedPipeClient,
    NamedPipeServer,
)


class WindowsControlChannel:
    def __init__(
        self,
        on_message=None,
    ):
        if (
            on_message is not None
            and not callable(on_message)
        ):
            raise TypeError(
                "on_message deve ser callable ou None"
            )

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._ready = threading.Event()

        self._on_message = on_message

        self._pipe_name = None
        self._pipe_leaf = None

        self._server = None
        self._connection = None
        self._thread = None
        self._error = None

    @property
    def pipe_name(self):
        with self._lock:
            return self._pipe_name

    @property
    def pipe_leaf(self):
        with self._lock:
            return self._pipe_leaf

    @property
    def is_ready(self):
        return self._ready.is_set()

    @property
    def error(self):
        with self._lock:
            return self._error

    def start(self):
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                raise RuntimeError(
                    "Canal de controle Windows ja esta ativo"
                )

            token = uuid.uuid4().hex

            pipe_leaf = (
                "CodeBridge.WindowsControl."
                + token
            )

            pipe_name = (
                '\\\\.\\pipe\\'
                + pipe_leaf
            )

            server = NamedPipeServer(
                pipe_name
            )

            self._stop.clear()
            self._ready.clear()

            self._pipe_name = pipe_name
            self._pipe_leaf = pipe_leaf
            self._server = server
            self._connection = None
            self._error = None

            thread = threading.Thread(
                target=self._run,
                name=(
                    "CodeBridgeWindowsControl"
                ),
                daemon=True,
            )

            self._thread = thread

        thread.start()

        return pipe_name

    def wait_ready(
        self,
        timeout=5.0,
    ):
        if not self._ready.wait(
            timeout=float(timeout)
        ):
            raise TimeoutError(
                "Timeout aguardando canal "
                "de controle Windows"
            )

        with self._lock:
            error = self._error
            connection = self._connection

        if error is not None:
            raise RuntimeError(
                "Falha no canal de controle Windows: "
                + str(error)
            ) from error

        if connection is None:
            raise RuntimeError(
                "Canal de controle Windows "
                "nao possui conexao ativa"
            )

        return True

    def _run(self):
        connection = None

        try:
            with self._lock:
                server = self._server

            if server is None:
                raise RuntimeError(
                    "Servidor do canal de controle ausente"
                )

            connection = server.accept()

            with self._lock:
                self._connection = connection

            first = connection.receive()

            if first != b"READY":
                raise RuntimeError(
                    "Handshake inesperado no "
                    "canal de controle Windows"
                )

            connection.send(
                b"ACK:READY"
            )

            self._ready.set()

            while not self._stop.is_set():
                try:
                    payload = (
                        connection.receive()
                    )

                except EOFError:
                    break

                if payload == b"PING":
                    connection.send(
                        b"ACK:PING"
                    )
                    continue

                if payload == b"CLOSE":
                    connection.send(
                        b"ACK:CLOSE"
                    )
                    continue

                callback = self._on_message

                if callback is None:
                    connection.send(
                        b"ERROR:UNKNOWN"
                    )
                    continue

                response = callback(
                    payload
                )

                if response is not None:
                    if not isinstance(
                        response,
                        bytes,
                    ):
                        raise TypeError(
                            "Resposta do canal de controle "
                            "deve ser bytes ou None"
                        )

                    connection.send(
                        response
                    )

        except Exception as error:
            if not self._stop.is_set():
                with self._lock:
                    self._error = error

                self._ready.set()

        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

            with self._lock:
                if (
                    self._connection
                    is connection
                ):
                    self._connection = None

    def close(self):
        self._stop.set()

        with self._lock:
            connection = self._connection
            thread = self._thread
            pipe_name = self._pipe_name

        if connection is not None:
            try:
                connection.cancel_pending_io()
            except Exception:
                pass

        elif (
            pipe_name
            and thread is not None
            and thread.is_alive()
        ):
            try:
                probe = (
                    NamedPipeClient.connect(
                        pipe_name,
                        timeout=0.25,
                    )
                )

                probe.close()

            except Exception:
                pass

        if (
            thread is not None
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):
            thread.join(
                timeout=1.0
            )

        if (
            thread is not None
            and thread.is_alive()
        ):
            return False

        with self._lock:
            self._connection = None
            self._server = None
            self._thread = None
            self._pipe_name = None
            self._pipe_leaf = None

        self._ready.clear()

        return True
