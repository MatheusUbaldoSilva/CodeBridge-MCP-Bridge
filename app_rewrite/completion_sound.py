import ctypes
import threading
import time

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


class CompletionSound:
    def __init__(self, config, play_fn=None):
        self._config = config
        self._lock = threading.RLock()
        self._enabled = bool(
            config.load_completion_sound()
        )
        self._play_fn = (
            play_fn
            if play_fn is not None
            else self._play_windows_notification
        )
        self._seen = set()
        self._seen_order = []

    @property
    def enabled(self):
        with self._lock:
            return self._enabled

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
    def _ring_worker():
        try:
            user32 = ctypes.windll.user32
        except Exception:
            return

        for index in range(5):
            user32.MessageBeep(0x40)
            if index < 4:
                time.sleep(1.5)

    @staticmethod
    def _play_windows_notification():
        threading.Thread(
            target=CompletionSound._ring_worker,
            name="CodeBridgeCompletionBell",
            daemon=True,
        ).start()
        return True
