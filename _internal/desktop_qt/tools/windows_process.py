"""Create suspended Win32 processes with an actual STARTUPINFO.lpDesktop.

Python's subprocess.STARTUPINFO does not marshal an added lpDesktop attribute.
Keep the native structure here and verify the primary thread before any code runs.
"""
import ctypes as c
from ctypes import wintypes as w
import msvcrt
import os
import subprocess
import struct
from pathlib import Path

from private_profile import isolate

k = c.WinDLL("kernel32", use_last_error=True)
u = c.WinDLL("user32", use_last_error=True)

class Startup(c.Structure):
    _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR), ("title", w.LPWSTR),
        *[(n, w.DWORD) for n in ("x", "y", "width", "height", "cols", "rows", "fill", "flags")],
        ("show", w.WORD), ("reserved_size", w.WORD), ("reserved_bytes", c.c_void_p),
        ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]

class Info(c.Structure):
    _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]

k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD,
    c.c_void_p, w.LPCWSTR, c.POINTER(Startup), c.POINTER(Info)]
k.CreateProcessW.restype = w.BOOL
k.GetCurrentProcess.restype = w.HANDLE
k.DuplicateHandle.argtypes = [w.HANDLE,w.HANDLE,w.HANDLE,c.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD]
k.CloseHandle.argtypes = [w.HANDLE]
k.WaitForSingleObject.argtypes = [w.HANDLE,w.DWORD]
k.GetExitCodeProcess.argtypes = [w.HANDLE,c.POINTER(w.DWORD)]
k.TerminateProcess.argtypes = [w.HANDLE,w.UINT]
u.GetThreadDesktop.argtypes = [w.DWORD]
u.GetThreadDesktop.restype = w.HANDLE
u.GetUserObjectInformationW.argtypes = [w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
k.ReadProcessMemory.argtypes = [w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]

def startup_desktop(handle):
    # x64 PEB.ProcessParameters -> RTL_USER_PROCESS_PARAMETERS.DesktopInfo.
    # Only read the desktop name, never the command/environment or user data.
    if c.sizeof(c.c_void_p)!=8:raise RuntimeError("Desktop verification requires x64")
    nt=c.WinDLL("ntdll")
    nt.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.c_void_p]
    basic=(c.c_uint64*6)()
    if nt.NtQueryInformationProcess(handle,0,basic,c.sizeof(basic),None)!=0:raise RuntimeError("Cannot read own suspended process PEB")
    def read(at,size):
        buf=c.create_string_buffer(size);got=c.c_size_t()
        if not k.ReadProcessMemory(handle,c.c_void_p(at),buf,size,c.byref(got)) or got.value!=size:raise c.WinError(c.get_last_error())
        return buf.raw
    params=struct.unpack("<Q",read(basic[1]+0x20,8))[0]
    value=read(params+0xc0,16);length=struct.unpack_from("<H",value)[0];address=struct.unpack_from("<Q",value,8)[0]
    if not length or length>4096:raise RuntimeError("Invalid suspended process desktop name")
    return read(address,length).decode("utf-16-le")

def thread_desktop(tid):
    name=c.create_unicode_buffer(256);size=w.DWORD()
    handle=u.GetThreadDesktop(tid)
    if not handle or not u.GetUserObjectInformationW(handle,2,name,c.sizeof(name),c.byref(size)):
        raise c.WinError(c.get_last_error())
    return name.value

class Process:
    def __init__(self, args, info, desktop):
        self.args=args;self.pid=info.pid;self._handle=info.process;self.returncode=None
        self.primary_thread_id=info.tid;self.desktop=desktop
    def poll(self):
        if self.returncode is None and k.WaitForSingleObject(self._handle,0)==0:
            code=w.DWORD()
            if not k.GetExitCodeProcess(self._handle,c.byref(code)):raise c.WinError(c.get_last_error())
            self.returncode=code.value
        return self.returncode
    def wait(self,timeout=None):
        result=k.WaitForSingleObject(self._handle,0xffffffff if timeout is None else min(0xfffffffe,max(0,int(timeout*1000))))
        if result==258:raise subprocess.TimeoutExpired(self.args,timeout)
        if result!=0:raise c.WinError(c.get_last_error())
        return self.poll()
    def kill(self):
        if self.poll() is None and not k.TerminateProcess(self._handle,1):raise c.WinError(c.get_last_error())
    def __del__(self):
        if getattr(self,"_handle",None):k.CloseHandle(self._handle)

def create_suspended(args, *, cwd, env, log, desktop, show=0):
    if Path(str(args[0])).name.lower() == "abookdesk.exe":
        env = isolate(dict(env))
    current=k.GetCurrentProcess();handles=[]
    def inherit(file):
        target=w.HANDLE()
        if not k.DuplicateHandle(current,w.HANDLE(msvcrt.get_osfhandle(file.fileno())),current,c.byref(target),0,True,2):
            raise c.WinError(c.get_last_error())
        handles.append(target);return target.value
    info=Info()
    try:
        with open(os.devnull,"rb") as null:
            startup=Startup();startup.cb=c.sizeof(startup);startup.desktop="winsta0\\"+desktop
            startup.flags=0x101;startup.show=show
            startup.stdin=inherit(null);startup.stdout=startup.stderr=inherit(log)
            command=c.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in args]))
            block=c.create_unicode_buffer("\0".join(f"{a}={b}" for a,b in sorted(env.items(),key=lambda p:p[0].upper()))+"\0\0")
            # Con (và cả cây của nó) thừa hưởng chế độ lỗi lúc tạo: chết lúc khởi động thì trả mã, không để csrss vẽ hộp lỗi
            # lên màn hình chủ máy - hộp ấy không nằm trên desktop riêng (31-10 0xc0000142).
            previous=k.SetErrorMode(0x8003)
            try:
                if not k.CreateProcessW(None,command,None,None,True,0x08000404,block,str(cwd),c.byref(startup),c.byref(info)):
                    raise c.WinError(c.get_last_error())
            finally:
                k.SetErrorMode(previous)
        process=Process(args,info,desktop)
        try:
            actual=startup_desktop(process._handle)
            if actual!="winsta0\\"+desktop:raise RuntimeError(f"Desktop mismatch before resume: {actual!r} != {desktop!r}")
        except Exception:
            process.kill();process.wait(5);raise
        finally:k.CloseHandle(info.thread)
        return process
    finally:
        for handle in handles:k.CloseHandle(handle)
