import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app_rewrite"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from completion_sound import CompletionSound
from config_store import ConfigStore


class CompletionSoundTests(unittest.TestCase):
    def test_default_is_enabled_and_persists_toggle(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config = ConfigStore(config_path)

            self.assertTrue(
                config.load_completion_sound()
            )

            config.save_completion_sound(False)
            reopened = ConfigStore(config_path)
            self.assertFalse(
                reopened.load_completion_sound()
            )

    def test_notify_plays_once_per_completion(self):
        calls = []
        class FakeConfig:
            def load_completion_sound(self):
                return True

            def save_completion_sound(
                self,
                enabled,
            ):
                return bool(enabled)

        sound = CompletionSound(
            FakeConfig(),
            play_fn=lambda: (
                calls.append("bell") or True
            ),
        )

        self.assertTrue(
            sound.notify(
                "exec_1",
                "FINISHED",
                "POWERSHELL5.1",
            )
        )
        self.assertFalse(
            sound.notify(
                "exec_1",
                "FINISHED",
                "POWERSHELL5.1",
            )
        )
        self.assertEqual(calls, ["bell"])
    def test_default_audio_asset_exists(self):
        class FakeConfig:
            def load_completion_sound(self):
                return True

            def save_completion_sound(
                self,
                enabled,
            ):
                return bool(enabled)

        sound = CompletionSound(FakeConfig())
        self.assertTrue(sound.audio_path.is_file())
        self.assertEqual(
            sound.audio_path.name,
            "completion_execucao_concluida.mp3",
        )

    def test_missing_audio_does_not_start_playback(self):
        class FakeConfig:
            def load_completion_sound(self):
                return True

            def save_completion_sound(
                self,
                enabled,
            ):
                return bool(enabled)

        sound = CompletionSound(
            FakeConfig(),
            audio_path=Path(
                "__missing_completion_audio__.mp3"
            ),
        )
        self.assertFalse(
            sound._play_windows_audio()
        )
    def test_disabled_marks_completion_without_playing(self):
        calls = []

        class FakeConfig:
            def load_completion_sound(self):
                return False

            def save_completion_sound(
                self,
                enabled,
            ):
                return bool(enabled)

        sound = CompletionSound(
            FakeConfig(),
            play_fn=lambda: (
                calls.append("bell") or True
            ),
        )

        self.assertFalse(
            sound.notify(
                "exec_2",
                "FAILED",
                "CMD",
            )
        )
        self.assertEqual(calls, [])

        sound.set_enabled(True)
        self.assertFalse(
            sound.notify(
                "exec_2",
                "FAILED",
                "CMD",
            )
        )
        self.assertEqual(calls, [])

        self.assertTrue(
            sound.notify(
                "exec_3",
                "FINISHED",
                "CMD",
            )
        )
        self.assertEqual(calls, ["bell"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
