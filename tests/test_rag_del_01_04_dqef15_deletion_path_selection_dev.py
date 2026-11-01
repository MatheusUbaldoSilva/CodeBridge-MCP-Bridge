"""F15 lexical deletion selection: never installed or authorized."""
from unittest import TestCase
from rag.runtime.knowledge_deletion_selection_contract_dev import review_explicit_deletion_paths_dev as review

class F15SelectionTests(TestCase):
    def test_positive_remains_unapproved(self):
        x=review("demo",["src/a.py","docs/b.md"])
        self.assertEqual(x["count"],2)
        self.assertFalse(x["activation_authorized"])
        self.assertFalse(x["operational_use_allowed"])
        self.assertIn("SYMLINK_AND_REPARSE_POINT_RESOLUTION_NOT_ATTESTED",x["blockers"])
    def test_order_independent_hash(self):
        a=review("demo",["a.md","b.py"])["selection_sha256"]
        b=review("demo",["b.py","a.md"])["selection_sha256"]
        self.assertEqual(a,b)
    def test_project_bound(self):
        a=review("foo",["a"])["selection_sha256"]
        b=review("bar",["a"])["selection_sha256"]
        self.assertNotEqual(a,b)
    def test_unicode_and_case_collisions(self):
        for paths in (["x.py","X.PY"],["folder","folder/a"],
                      ["docs/READme","DOCS/readme"],
                      ["A.txt","?.txt"]):
            with self.subTest(paths=paths),self.assertRaises(ValueError):
                review("demo",paths)
    def test_reserved_win_devices(self):
        for name in ("CON","con.txt","aux.js","PRN","NUL",
                     "com1","COM9.txt","lpt1","LPT9.cfg","dir/CON.md"):
            with self.subTest(path=name),self.assertRaises(ValueError):
                review("demo",[name])
    def test_traversal_altstream_and_sep(self):
        for name in ("../x","a/../b","a//b","./x","/x","x/",
                     "C:/x","x:ads","x:Zone.Identifier","a/b"+chr(92)+"c"):
            with self.subTest(path=name),self.assertRaises(ValueError):
                review("demo",[name])
    def test_metachar_dot_space(self):
        for name in ("a.","a ","a?.txt","x*","x|y","a<b","b>c",
                     'a"b',"a\b"):
            with self.subTest(path=name),self.assertRaises(ValueError):
                review("demo",[name])
    def test_control_and_format(self):
        for ch in (chr(0),chr(31),chr(127),chr(0x202e),chr(0x200e),chr(0xd800)):
            with self.subTest(ch=repr(ch)),self.assertRaises(ValueError):
                review("demo",["x"+ch+".txt"])
    def test_invalid_shapes_and_duplicates(self):
        for paths in ([],["a"]*2,["a"]*501,["a"*4097],None,{},["a",None],True):
            with self.subTest(type=type(paths)),self.assertRaises(ValueError):
                review("demo",paths)
    def test_private_id_only(self):
        for project in ("","codebridge","x/y","x:y",None,True,"a b","a"*129):
            with self.subTest(project=project),self.assertRaises(ValueError):
                review(project,["a"])
    def test_no_names_in_receipt(self):
        r=review("demo",["confidential/client.md"])
        self.assertNotIn("client",str(r))
        self.assertEqual(len(r["selection_sha256"]),64)
    def test_nfc_unicode(self):
        r=review("demo",["relat"+chr(0xf3)+"rios/a"+chr(0xe7)+chr(0xe3)+"o.md"])
        self.assertEqual(r["count"],1)
        self.assertFalse(r["activation_authorized"])
