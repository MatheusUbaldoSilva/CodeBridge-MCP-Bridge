import sys
import unittest
from pathlib import Path


APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "app"
)

if str(APP_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(APP_DIR),
    )

from ipc_named_pipe import NamedPipeClient
from windows_control_channel import (
    WindowsControlChannel,
)


class WindowsControlChannelTests(
    unittest.TestCase
):
    def test_handshake_ping_and_close(self):
        channel = WindowsControlChannel()

        try:
            channel.start()

            with NamedPipeClient.connect(
                channel.pipe_name,
                timeout=2.0,
            ) as client:
                client.send(
                    b"READY"
                )

                self.assertEqual(
                    client.receive(),
                    b"ACK:READY",
                )

                self.assertTrue(
                    channel.wait_ready(
                        timeout=2.0
                    )
                )

                client.send(
                    b"PING"
                )

                self.assertEqual(
                    client.receive(),
                    b"ACK:PING",
                )

                client.send(
                    b"CLOSE"
                )

                self.assertEqual(
                    client.receive(),
                    b"ACK:CLOSE",
                )

        finally:
            channel.close()

    def test_close_unblocks_pending_accept(
        self,
    ):
        channel = WindowsControlChannel()

        channel.start()
        channel.close()

        self.assertFalse(
            channel.is_ready
        )

    def test_close_unblocks_connected_receive(
        self,
    ):
        channel = WindowsControlChannel()
        client = None

        try:
            channel.start()

            client = NamedPipeClient.connect(
                channel.pipe_name,
                timeout=2.0,
            )

            client.send(
                b"READY"
            )

            self.assertEqual(
                client.receive(),
                b"ACK:READY",
            )

            self.assertTrue(
                channel.wait_ready(
                    timeout=2.0
                )
            )

            thread = channel._thread

            channel.close()

            self.assertFalse(
                thread.is_alive()
            )

            self.assertFalse(
                channel.is_ready
            )

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

            channel.close()


if __name__ == "__main__":
    unittest.main()
