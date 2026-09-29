import ctypes
import threading
from pathlib import Path


DEFAULT_AUDIO_PATH = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "completion_execucao_concluida.mp3"
)


class CompletionSound:
    _audio_lock = threading.Lock()

    def __init__(
        self,
        config,
        play_fn=None,
        audio_path=None,
    ):
        self._config = config
        self._lock = threading.RLock()
        self._enabled = bool(
            config.load_completion_sound()
        )
        self._audio_path = Path(
            audio_path or DEFAULT_AUDIO_PATH
        )
        self._play_fn = (
            play_fn
            if play_fn is not None
            else self._play_windows_audio
        )
        self._seen = set()
        self._seen_order = []

    @property
    def enabled(self):
        with self._lock:
            return self._enabled

    @property
    def audio_path(self):
        return self._audio_path

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        with self._lock:
            self._enabled = enabled
        self._config.save_completion_sound(
            enabled
        )
        return enabled

    def toggle(self):
        return self.set_enabled(
            not self.enabled
        )

    def notify(
        self,
        completion_id,
        state,
        target=None,
    ):
        key = str(
            completion_id
            or (
                str(target or "")
                + ":"
                + str(state or "")
            )
        )

        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            self._seen_order.append(key)

            if len(self._seen_order) > 1024:
                old = self._seen_order.pop(0)
                self._seen.discard(old)

            enabled = self._enabled

        if not enabled:
            return False

        try:
            return bool(self._play_fn())
        except Exception:
            return False

    @staticmethod
    def _mci_error_text(code):
        buffer = ctypes.create_unicode_buffer(256)
        try:
            ok = ctypes.windll.winmm.mciGetErrorStringW(
                int(code),
                buffer,
                len(buffer),
            )
        except Exception:
            return f"MCI error {code}"
        if ok:
            return buffer.value
        return f"MCI error {code}"

    def _audio_worker(self):
        alias = (
            "CodeBridgeCompletionAudio_"
            + str(threading.get_ident())
        )
        with self._audio_lock:
            winmm = None
            opened = False
            try:
                winmm = ctypes.windll.winmm
                send = winmm.mciSendStringW
                audio = str(
                    self._audio_path.resolve()
                )
                command = (
                    'open "'
                    + audio
                    + '" type mpegvideo alias '
                    + alias
                )
                result = send(
                    command,
                    None,
                    0,
                    None,
                )
                if result:
                    raise OSError(
                        self._mci_error_text(result)
                    )
                opened = True

                result = send(
                    "play " + alias + " wait",
                    None,
                    0,
                    None,
                )
                if result:
                    raise OSError(
                        self._mci_error_text(result)
                    )
            except Exception:
                try:
                    ctypes.windll.user32.MessageBeep(
                        0x40
                    )
                except Exception:
                    pass
            finally:
                if opened and winmm is not None:
                    try:
                        winmm.mciSendStringW(
                            "close " + alias,
                            None,
                            0,
                            None,
                        )
                    except Exception:
                        pass

    def _play_windows_audio(self):
        if not self._audio_path.is_file():
            return False
        threading.Thread(
            target=self._audio_worker,
            name="CodeBridgeCompletionAudio",
            daemon=True,
        ).start()
        return True
