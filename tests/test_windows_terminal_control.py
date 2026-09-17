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

from windows_terminal_session import (
    WindowsTerminalSession,
)


class WindowsTerminalControlTests(
    unittest.TestCase
):
    def test_begin_records_execution_id(
        self,
    ):
        session = WindowsTerminalSession()

        execution_id = (
            "0123456789abcdef"
            "0123456789abcdef"
        )

        state = {
            "done": False,
            "control_begin_seen": False,
            "control_execution_id": None,
        }

        session._execution_state = state

        response = (
            session._handle_control_message(
                (
                    "BEGIN:"
                    + execution_id
                ).encode(
                    "ascii"
                )
            )
        )

        response_text = (
            response.decode(
                "ascii"
            )
        )

        prefix = (
            "ACK:BEGIN:"
            + execution_id
            + ":"
        )

        self.assertTrue(
            response_text.startswith(
                prefix
            )
        )

        fence_token = (
            response_text[
                len(prefix):
            ]
        )

        self.assertEqual(
            len(fence_token),
            32,
        )

        self.assertEqual(
            state[
                "control_start_fence_token"
            ],
            fence_token,
        )

        self.assertEqual(
            state[
                "control_start_fence"
            ],
            (
                "~CBFS"
                + fence_token
                + "~"
            ).encode(
                "ascii"
            ),
        )

        self.assertTrue(
            state[
                "control_begin_seen"
            ]
        )

        self.assertEqual(
            state[
                "control_execution_id"
            ],
            execution_id,
        )

    def test_end_records_status(
        self,
    ):
        session = WindowsTerminalSession()

        execution_id = (
            "0123456789abcdef"
            "0123456789abcdef"
        )

        state = {
            "done": False,
            "control_begin_seen": True,
            "control_execution_id": execution_id,
            "control_end_seen": False,
            "control_failed": None,
            "control_exit_code": None,
        }

        session._execution_state = state

        response = (
            session._handle_control_message(
                (
                    "END:"
                    + execution_id
                    + ":True:0"
                ).encode(
                    "ascii"
                )
            )
        )

        response_text = (
            response.decode(
                "ascii"
            )
        )

        prefix = (
            "ACK:END:"
            + execution_id
            + ":"
        )

        self.assertTrue(
            response_text.startswith(
                prefix
            )
        )

        fence_token = (
            response_text[
                len(prefix):
            ]
        )

        self.assertEqual(
            len(fence_token),
            32,
        )

        self.assertEqual(
            state[
                "control_end_fence_token"
            ],
            fence_token,
        )

        self.assertEqual(
            state[
                "control_end_fence"
            ],
            (
                "~CBFE"
                + fence_token
                + "~"
            ).encode(
                "ascii"
            ),
        )

        self.assertTrue(
            state[
                "control_end_seen"
            ]
        )

        self.assertFalse(
            state[
                "control_failed"
            ]
        )

        self.assertEqual(
            state[
                "control_exit_code"
            ],
            0,
        )

    def test_end_rejects_wrong_execution(
        self,
    ):
        session = WindowsTerminalSession()

        session._execution_state = {
            "done": False,
            "control_execution_id":
                "aaaaaaaaaaaaaaaa"
                "aaaaaaaaaaaaaaaa",
            "control_end_seen": False,
        }

        response = (
            session._handle_control_message(
                b"END:"
                b"bbbbbbbbbbbbbbbb"
                b"bbbbbbbbbbbbbbbb"
                b":True:0"
            )
        )

        self.assertEqual(
            response,
            b"ERROR:END_CONFLICT",
        )

    def test_begin_requires_execution(
        self,
    ):
        session = WindowsTerminalSession()

        response = (
            session._handle_control_message(
                b"BEGIN:"
                b"0123456789abcdef"
                b"0123456789abcdef"
            )
        )

        self.assertEqual(
            response,
            b"ERROR:NO_EXECUTION",
        )

    def test_begin_rejects_invalid_id(
        self,
    ):
        session = WindowsTerminalSession()

        session._execution_state = {
            "done": False,
            "control_begin_seen": False,
            "control_execution_id": None,
        }

        response = (
            session._handle_control_message(
                b"BEGIN:not-a-guid"
            )
        )

        self.assertEqual(
            response,
            b"ERROR:BEGIN_ID",
        )


if __name__ == "__main__":
    unittest.main()
