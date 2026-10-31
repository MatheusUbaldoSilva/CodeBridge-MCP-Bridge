"""G-13 bounded manual scratch soak parameters."""
from unittest import TestCase
from benchmarks.rag_del_mac_pipe_soak_dev import soak

class SoakRunnerDevTests(TestCase):
    def test_reject_zero(self):
        with self.assertRaises(ValueError):soak(0)
    def test_reject_unbounded(self):
        with self.assertRaises(ValueError):soak(501)
    def test_small_soak_never_authorizes(self):
        result=soak(2)
        self.assertEqual(result["iterations"],2)
        self.assertFalse(result["activation_authorized"])
