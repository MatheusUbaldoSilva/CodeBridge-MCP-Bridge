import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app_rewrite"))
import ipc_named_pipe


class NamedPipeBoundedFrameTests(unittest.TestCase):
    def test_rejects_oversized_for_receiver_after_header_before_body_read(self):
        header=struct.pack("<I",8193)
        with patch.object(ipc_named_pipe,"_read_exact",return_value=header) as read:
            with self.assertRaises(ipc_named_pipe.NamedPipeProtocolError):
                ipc_named_pipe.read_frame(123,max_bytes=8192)
        read.assert_called_once_with(123,4)

    def test_accepts_frame_at_receiver_limit(self):
        header=struct.pack("<I",8)
        with patch.object(ipc_named_pipe,"_read_exact",side_effect=[header,b"12345678"]) as read:
            self.assertEqual(ipc_named_pipe.read_frame(123,max_bytes=8),b"12345678")
        self.assertEqual(read.call_count,2)
        self.assertEqual(read.call_args_list[1].args,(123,8))

    def test_invalid_receiver_limits_are_rejected_before_io(self):
        for value in (0,-1,True,False,1.5,ipc_named_pipe.MAX_MESSAGE_BYTES+1):
            with self.subTest(value=value), patch.object(ipc_named_pipe,"_read_exact") as read:
                with self.assertRaises(ValueError):
                    ipc_named_pipe.read_frame(123,max_bytes=value)
                read.assert_not_called()

    def test_default_frame_limit_remains_backward_compatible(self):
        header=struct.pack("<I",8)
        with patch.object(ipc_named_pipe,"_read_exact",side_effect=[header,b"12345678"]) as read:
            self.assertEqual(ipc_named_pipe.read_frame(123),b"12345678")
        self.assertEqual(read.call_count,2)


if __name__=="__main__":
    unittest.main()

