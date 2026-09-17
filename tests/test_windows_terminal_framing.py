import codecs
import sys
import threading
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


START_TOKEN = (
    "1111111111111111"
    "1111111111111111"
)

END_TOKEN = (
    "2222222222222222"
    "2222222222222222"
)

START_FENCE = (
    "~CBFS"
    + START_TOKEN
    + "~"
).encode(
    "ascii"
)

END_FENCE = (
    "~CBFE"
    + END_TOKEN
    + "~"
).encode(
    "ascii"
)


def make_state(
    phase="WAIT_START_FENCE",
):
    return {
        "buffer": bytearray(),
        "output": bytearray(),
        "decoder":
            codecs.getincrementaldecoder(
                "utf-8"
            )(
                errors="replace"
            ),
        "on_output": None,
        "phase": phase,
        "accepted": True,
        "control_begin_seen": True,
        "control_execution_id":
            "0123456789abcdef"
            "0123456789abcdef",
        "control_end_seen": False,
        "control_failed": None,
        "control_exit_code": None,
        "control_start_fence_token":
            START_TOKEN,
        "control_start_fence":
            START_FENCE,
        "control_end_fence_token":
            None,
        "control_end_fence":
            None,
        "failed": False,
        "exit_code": None,
        "error_message": "",
        "error": None,
        "cancelled": False,
        "done": False,
        "event": threading.Event(),
    }


class WindowsTerminalFramingTests(
    unittest.TestCase
):
    def test_plain_dynamic_start_fence(
        self,
    ):
        session = WindowsTerminalSession()
        state = make_state()

        session._execution_state = state

        session._process_execution_bytes(
            b"PS C:\\> comando"
            + START_FENCE
        )

        self.assertEqual(
            state[
                "phase"
            ],
            "CAPTURE",
        )

        self.assertEqual(
            bytes(
                state[
                    "output"
                ]
            ),
            b"",
        )

    def test_dynamic_start_redraw(
        self,
    ):
        session = WindowsTerminalSession()
        state = make_state()

        session._execution_state = state

        split = len(
            START_FENCE
        ) // 2

        session._process_execution_bytes(
            b"PS C:\\> comando"
            + START_FENCE[
                :split
            ]
        )

        session._process_execution_bytes(
            b"\r\n\x1b[13;154H"
            + START_FENCE[
                split - 1:
            ]
            + b"\x1b[143C"
        )

        self.assertEqual(
            state[
                "phase"
            ],
            "CAPTURE",
        )

    def test_partial_dynamic_start_is_preserved(
        self,
    ):
        session = WindowsTerminalSession()
        state = make_state()

        session._execution_state = state

        session._process_execution_bytes(
            b"PS C:\\> comando"
            + START_FENCE[:10]
        )

        self.assertEqual(
            bytes(
                state[
                    "buffer"
                ]
            ),
            START_FENCE[:10],
        )

        self.assertEqual(
            state[
                "phase"
            ],
            "WAIT_START_FENCE",
        )

    def test_dynamic_end_completes_and_old_protocol_is_output(
        self,
    ):
        session = WindowsTerminalSession()

        state = make_state(
            phase="CAPTURE"
        )

        state[
            "control_end_seen"
        ] = True

        state[
            "control_failed"
        ] = False

        state[
            "control_exit_code"
        ] = 0

        state[
            "control_end_fence_token"
        ] = END_TOKEN

        state[
            "control_end_fence"
        ] = END_FENCE

        session._execution_state = state

        old_protocol = (
            b"~Bdeadbeef~"
            b"~Sdeadbeef:True:0:E~"
            b"~Pdeadbeef~"
        )

        session._process_execution_bytes(
            b"CB_OUTPUT\r\n"
            + old_protocol
            + b"\r\n"
            + END_FENCE
            + b"PS C:\\> "
        )

        self.assertTrue(
            state[
                "event"
            ].is_set()
        )

        self.assertTrue(
            state[
                "done"
            ]
        )

        self.assertIsNone(
            state[
                "error"
            ]
        )

        self.assertFalse(
            state[
                "failed"
            ]
        )

        self.assertEqual(
            state[
                "exit_code"
            ],
            0,
        )

        output = bytes(
            state[
                "output"
            ]
        )

        self.assertIn(
            b"CB_OUTPUT",
            output,
        )

        self.assertIn(
            old_protocol,
            output,
        )

        self.assertNotIn(
            END_FENCE,
            output,
        )


if __name__ == "__main__":
    unittest.main()
