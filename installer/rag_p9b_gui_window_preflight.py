"""Read-only Win32 CodeBridge window inspection for external recovery."""
from __future__ import annotations
import ctypes
import json
import os


def inspect_gui_windows(pid: int, *, user32=None):
    base={"state":"GUI_WINDOW_UNVERIFIED","read_only":True,"pid":pid,
          "windows":[]}
    if os.name!="nt" and user32 is None:
        return {**base,"reason":"WINDOWS_REQUIRED"}
    try:
        api=user32 or ctypes.windll.user32
        windows=[]
        @ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
        def check(hwnd, _):
            owner=ctypes.c_ulong()
            api.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
            if owner.value != pid:
                return True
            title=ctypes.create_unicode_buffer(256)
            api.GetWindowTextW(hwnd,title,256)
            windows.append({"hwnd":int(hwnd),
                            "title":title.value,
                            "visible":bool(api.IsWindowVisible(hwnd))})
            return True
        api.EnumWindows(check,None)
        matched=[w for w in windows
                 if w["title"]=="CodeBridge 2.0 - MCP Bridge"]
        return {**base,"state":("GUI_WINDOW_MATCHED" if len(matched)==1
                                   else "GUI_WINDOW_UNVERIFIED"),
                "windows":windows,"matched":matched}
    except (OSError,ValueError,TypeError,AttributeError):
        return {**base,"reason":"WINDOW_ENUMERATION_FAILED"}


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--pid",required=True,type=int)
    args=p.parse_args()
    print(json.dumps(inspect_gui_windows(args.pid),sort_keys=True))
