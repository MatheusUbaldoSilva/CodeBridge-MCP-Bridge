import unittest
from installer.rag_p9b_winreg_adapter import ScopedHKCU
from installer.rag_p9b_windows_shell_scope import APP_KEYS


class RegistryHandle:
    def __init__(self,reg,key):
        self.reg=reg
        self.key=key
    def __enter__(self):return self
    def __exit__(self,*args):return False


class FakeWinreg:
    HKEY_CURRENT_USER=100
    REG_SZ=1
    REG_DWORD=4
    KEY_READ=1
    KEY_WRITE=2
    def __init__(self):
        self.data={}
    def OpenKey(self,root,key):
        if key not in self.data:raise FileNotFoundError(key)
        return RegistryHandle(self,key)
    def CreateKeyEx(self,root,key,unused,flags):
        self.data.setdefault(key,{})
        return RegistryHandle(self,key)
    def QueryValueEx(self,handle,name):
        if name not in self.data[handle.key]:raise FileNotFoundError(name)
        return self.data[handle.key][name]
    def SetValueEx(self,handle,name,unused,kind,value):
        self.data[handle.key][name]=(value,kind)
    def DeleteValue(self,handle,name):
        if name not in self.data[handle.key]:raise FileNotFoundError(name)
        del self.data[handle.key][name]
    def QueryInfoKey(self,handle):
        return 0,len(self.data[handle.key]),0
    def EnumValue(self,handle,index):
        name=list(self.data[handle.key])[index]
        value,kind=self.data[handle.key][name]
        return name,value,kind
    def DeleteKey(self,root,key):
        if key not in self.data:raise FileNotFoundError(key)
        del self.data[key]


class WinregTests(unittest.TestCase):
    def setUp(self):
        self.fake=FakeWinreg()
        self.api=ScopedHKCU(self.fake)

    def test_read_missing(self):
        self.assertEqual(self.api.read_key(APP_KEYS[0]),{"exists":False,"values":{}})

    def test_replace_and_verify(self):
        entry={"exists":True,"values":{"InstallDir":{"type":1,"value":r"C:\Tools"},
                                        "Version":{"type":1,"value":"2.0"}}}
        self.api.replace_key(APP_KEYS[0],entry)
        self.assertEqual(self.api.read_key(APP_KEYS[0]),entry)
        self.api.replace_key(APP_KEYS[0],{"exists":True,"values":{"Version":{"type":1,"value":"3.0"}}})
        self.assertNotIn("InstallDir",self.api.read_key(APP_KEYS[0])["values"])

    def test_delete_missing_key(self):
        self.api.replace_key(APP_KEYS[0],{"exists":False,"values":{}})

    def test_foreign_values_prevent_delete(self):
        key=APP_KEYS[0]
        self.fake.data[key]={"OtherCompanyValue":("do-not-delete",1)}
        with self.assertRaisesRegex(ValueError,"FOREIGN_VALUES"):
            self.api.replace_key(key,{"exists":False,"values":{}})
        self.assertIn(key,self.fake.data)

    def test_other_key_refused(self):
        with self.assertRaises(ValueError):
            self.api.replace_key(r"Software\Unrelated",{"exists":False,"values":{}})

    def test_unknown_value_refused(self):
        with self.assertRaises(ValueError):
            self.api.replace_key(APP_KEYS[0],{"exists":True,"values":{"API_KEY":{"type":1,"value":"X"}}})

    def test_boolean_dword_refused(self):
        with self.assertRaises(ValueError):
            self.api.replace_key(APP_KEYS[1],{"exists":True,"values":{"NoRepair":{"type":4,"value":True}}})


if __name__=="__main__":
    unittest.main()
