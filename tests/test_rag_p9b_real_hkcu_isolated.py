"""Real winreg integration in an isolated temporary HKCU subtree.

The adapter receives a name-remapping facade: production CodeBridge
keys are never opened. Every key is unique in an isolated HKCU test subtree.
"""
import sys
import unittest
import uuid

from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_windows_shell_scope import APP_KEYS


@unittest.skipUnless(sys.platform=="win32","Real HKCU tests require Windows")
class RealHKCUIsolatedTests(unittest.TestCase):
    def setUp(self):
        import winreg
        self.wr=winreg
        self.root="Software"+chr(92)+"CodeBridgeP9BLab"
        self.token=uuid.uuid4().hex
        self.paths={key:self.root+chr(92)+self.token+chr(92)+str(i) for i,key in enumerate(APP_KEYS)}
        actual=winreg

        class Remap:
            HKEY_CURRENT_USER=actual.HKEY_CURRENT_USER
            REG_SZ=actual.REG_SZ
            REG_DWORD=actual.REG_DWORD
            KEY_READ=actual.KEY_READ
            KEY_WRITE=actual.KEY_WRITE
            def mapping(self,k):
                if k not in self_outer.paths:
                    raise ValueError("OUT_OF_SCOPE")
                return self_outer.paths[k]
            def OpenKey(self,h,k,*args):
                return actual.OpenKey(h,self.mapping(k),*args)
            def CreateKeyEx(self,h,k,*args):
                return actual.CreateKeyEx(h,self.mapping(k),*args)
            def DeleteKey(self,h,k):
                return actual.DeleteKey(h,self.mapping(k))
            QueryValueEx=staticmethod(actual.QueryValueEx)
            QueryInfoKey=staticmethod(actual.QueryInfoKey)
            EnumValue=staticmethod(actual.EnumValue)
            DeleteValue=staticmethod(actual.DeleteValue)
            SetValueEx=staticmethod(actual.SetValueEx)
        self_outer=self
        self.adapter=ScopedHKCU(Remap())

    def tearDown(self):
        wr=self.wr
        # Only delete keys beneath this test's cryptographically unique subtree.
        # Never remove pre-existing HKCU CodeBridge production keys.
        for key in self.paths.values():
            try:wr.DeleteKey(wr.HKEY_CURRENT_USER,key)
            except FileNotFoundError:pass
        try:wr.DeleteKey(wr.HKEY_CURRENT_USER,self.root+chr(92)+self.token)
        except FileNotFoundError:pass

    def test_real_hkcu_two_key_write_and_restore(self):
        initial={key:self.adapter.read_key(key) for key in APP_KEYS}
        self.assertTrue(all(not x["exists"] for x in initial.values()))
        for key in APP_KEYS:
            names=self.adapter._validate_scope(key)
            self.assertTrue(names)
            value=names[0]
            self.adapter.replace_key(key,{"exists":True,
                "values":{value:{"type":self.wr.REG_SZ,"value":"isolated-p9b-test"}}})
            self.assertEqual(self.adapter.read_key(key)["values"][value]["value"],
                             "isolated-p9b-test")
        for key in APP_KEYS:
            self.adapter.replace_key(key,initial[key])
            self.assertEqual(self.adapter.read_key(key),initial[key])

    def test_unrelated_production_path_refused(self):
        with self.assertRaises(ValueError):
            self.adapter.replace_key("Software"+chr(92)+"SomeOtherApp",
                  {"exists":True,"values":{}})


if __name__=="__main__":
    unittest.main()
