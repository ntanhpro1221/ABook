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
nt.NtQueryInformationThread.argtypes = [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.c_void_p]
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.OpenProcess.restype = w.HANDLE
dbg = c.WinDLL("dbghelp", use_last_error=True)
dbg.SymInitializeW.argtypes = [w.HANDLE, w.LPCWSTR, w.BOOL]
dbg.SymFromAddr.argtypes = [w.HANDLE, c.c_ulonglong, c.POINTER(c.c_ulonglong), c.c_void_p]
dbg.SymGetModuleBase64.argtypes = [w.HANDLE, c.c_ulonglong]
dbg.SymGetModuleBase64.restype = c.c_ulonglong
dbg.SymCleanup.argtypes = [w.HANDLE]
psapi = c.WinDLL("psapi")
psapi.GetModuleFileNameExW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]
_identities = {}
_address_identities = {}


def modules(pid):
    """Address map for separate diagnostic traces; not used in CPU timing runs."""
    class ModuleInfo(c.Structure):
        _fields_ = [("base", c.c_void_p), ("size", w.DWORD), ("entry", c.c_void_p)]
    psapi.EnumProcessModulesEx.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), w.DWORD]
    psapi.GetModuleInformation.argtypes = [w.HANDLE, w.HMODULE, c.POINTER(ModuleInfo), w.DWORD]
    process = k32.OpenProcess(0x0410, False, pid)
    result = []
    if not process: return result
    try:
        handles = (w.HMODULE * 2048)()
        used = w.DWORD()
        if not psapi.EnumProcessModulesEx(process, handles, c.sizeof(handles), c.byref(used), 3): return result
        for handle in list(handles)[:used.value // c.sizeof(w.HMODULE)]:
            info = ModuleInfo()
            path = c.create_unicode_buffer(32768)
            if psapi.GetModuleInformation(process, handle, c.byref(info), c.sizeof(info)) and psapi.GetModuleFileNameExW(process, handle, path, len(path)):
                result.append(dict(base=hex(info.base), size=info.size, path=path.value))
    finally:
        k32.CloseHandle(process)
    return result


def identity(pid, tid):
    """Class 9 returns the Win32 start, unlike the kernel's common thread thunk.

    DbgHelp uses loaded modules/exports and local PDBs only: no network or admin.
    Called on the sampler thread, since DbgHelp is single-threaded.
    """
    key = (pid, tid)
    if key in _identities:
        return _identities[key]
    result = {}
    thread = k32.OpenThread(0x0040, False, tid)
    address = c.c_void_p()
    if thread:
        try:
            status = nt.NtQueryInformationThread(thread, 9, c.byref(address), c.sizeof(address), None)
            result["start_query_status"] = status
        finally:
            k32.CloseHandle(thread)
    if address.value:
        result["start_address"] = hex(address.value)
        address_key = (pid, address.value)
        if address_key in _address_identities:
            result.update(_address_identities[address_key])
            _identities[key] = result
            return result
        process = k32.OpenProcess(0x0410, False, pid)
        if process:
            initialized = False
            try:
                initialized = bool(dbg.SymInitializeW(process, "", True))
                if initialized:
                    base = dbg.SymGetModuleBase64(process, address.value)
                    path = c.create_unicode_buffer(32768)
                    if base and psapi.GetModuleFileNameExW(process, w.HMODULE(base), path, len(path)):
                        result.update(module=path.value, module_offset=hex(address.value - base))
                    # SYMBOL_INFO: fixed header 88 bytes, Name starts at offset 84.
                    symbol = c.create_string_buffer(88 + 1024)
                    c.c_ulong.from_buffer(symbol, 0).value = 88
                    c.c_ulong.from_buffer(symbol, 80).value = 1024
                    delta = c.c_ulonglong()
                    if dbg.SymFromAddr(process, address.value, c.byref(delta), symbol):
                        result.update(symbol=c.string_at(c.addressof(symbol) + 84).decode("utf-8", "replace"), symbol_offset=hex(delta.value))
                    else:
                        result["symbol_error"] = c.get_last_error()
            finally:
                if initialized:
                    dbg.SymCleanup(process)
                k32.CloseHandle(process)
        _address_identities[address_key] = {k: v for k, v in result.items() if k != "start_query_status"}
    _identities[key] = result
    return result


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
                        if k32.GetThreadDescription(handle, c.byref(desc)) >= 0 and desc.value:
                            name = c.wstring_at(desc)
                    finally:
                        if desc.value:
                            k32.LocalFree(desc)
                        k32.CloseHandle(handle)
                result.append(dict(id=tid, cpu_s=kernel + user, cycles=cycles.value,
                                   context_switches=switches, name=name,
                                   state=c.c_uint32.from_address(thread + 68).value,
                                   wait_reason=c.c_uint32.from_address(thread + 72).value,
                                   **identity(pid, tid)))
            return result
        step = c.c_uint32.from_address(address).value
        if not step:
            break
        at += step
    return []
