"""Read CPU times/cycles and scheduler dispatch counts without enabling system tracing.

SYSTEM_PROCESS_INFORMATION (class 5), x64 Windows. Context switches count
dispatches, including preemption; render-loop wakes are counted separately in the app.
"""
import ctypes as c
from ctypes import wintypes as w

k32 = c.WinDLL("kernel32", use_last_error=True)
nt = c.WinDLL("ntdll")
k32.OpenThread.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.OpenThread.restype = w.HANDLE
k32.CloseHandle.argtypes = [w.HANDLE]
k32.QueryThreadCycleTime.argtypes = [w.HANDLE, c.POINTER(c.c_ulonglong)]
k32.GetThreadDescription.argtypes = [w.HANDLE, c.POINTER(c.c_void_p)]
k32.LocalFree.argtypes = [c.c_void_p]


def sample(pid):
    if c.sizeof(c.c_void_p) != 8:
        raise RuntimeError("Thread sampler requires x64")
    size = 1024 * 1024
    while True:
        buf = c.create_string_buffer(size)
        used = w.ULONG()
        status = nt.NtQuerySystemInformation(5, buf, size, c.byref(used))
        if status == 0:
            break
        if status & 0xffffffff != 0xc0000004:
            raise RuntimeError(f"NtQuerySystemInformation: {status & 0xffffffff:x}")
        size = max(size * 2, used.value + 65536)
    at = 0
    while at < size:
        address = c.addressof(buf) + at
        count = c.c_uint32.from_address(address + 4).value
        process = c.c_uint64.from_address(address + 80).value
        if process == pid:
            result = []
            for i in range(count):
                thread = address + 256 + i * 80
                tid = c.c_uint64.from_address(thread + 48).value
                kernel = c.c_int64.from_address(thread).value / 1e7
                user = c.c_int64.from_address(thread + 8).value / 1e7
                switches = c.c_uint32.from_address(thread + 64).value
                handle = k32.OpenThread(0x0800, False, tid)
                cycles, name = c.c_ulonglong(), ""
                if handle:
                    desc = c.c_void_p()
                    try:
                        k32.QueryThreadCycleTime(handle, c.byref(cycles))
                        if k32.GetThreadDescription(handle, c.byref(desc)) == 0 and desc.value:
                            name = c.wstring_at(desc)
                    finally:
                        if desc.value:
                            k32.LocalFree(desc)
                        k32.CloseHandle(handle)
                result.append(dict(id=tid, cpu_s=kernel + user, cycles=cycles.value,
                                   context_switches=switches, name=name))
            return result
        step = c.c_uint32.from_address(address).value
        if not step:
            break
        at += step
    return []
