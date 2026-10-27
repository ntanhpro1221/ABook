"""Read-only PSAPI/VirtualQueryEx accounting; never read or fault target page contents."""
import ctypes as c
from ctypes import wintypes as w
from collections import Counter
import psutil

k32 = c.WinDLL("kernel32", use_last_error=True)
psapi = c.WinDLL("psapi", use_last_error=True)


class Counters(c.Structure):
    _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD)] + [
        (name, c.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


class Region(c.Structure):
    _fields_ = [("BaseAddress", c.c_void_p), ("AllocationBase", c.c_void_p), ("AllocationProtect", w.DWORD),
                ("PartitionId", w.WORD), ("RegionSize", c.c_size_t), ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]


psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Counters), w.DWORD]
psapi.QueryWorkingSet.argtypes = [w.HANDLE, c.c_void_p, w.DWORD]
k32.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(Region), c.c_size_t]
k32.VirtualQueryEx.restype = c.c_size_t
psapi.GetMappedFileNameW.argtypes = [w.HANDLE, c.c_void_p, w.LPWSTR, w.DWORD]


def counters(handle, pid):
    info = Counters()
    info.cb = c.sizeof(info)
    if not psapi.GetProcessMemoryInfo(handle, c.byref(info), info.cb):
        raise c.WinError(c.get_last_error())
    return {"private_commit_mib": info.PrivateUsage / 1048576,
            "working_set_mib": info.WorkingSetSize / 1048576,
            "page_faults": info.PageFaultCount, "threads": psutil.Process(pid).num_threads()}


def snapshot(handle, pid):
    size = 1 << 17
    while True:
        buf = (c.c_size_t * size)()
        if psapi.QueryWorkingSet(handle, buf, c.sizeof(buf)):
            break
        if c.get_last_error() not in (24, 122) or size >= 1 << 23:
            raise c.WinError(c.get_last_error())
        size *= 2
    # Shared=0 matches measure.private_mb, including private image/COW pages.
    pages = sorted((buf[i] & ~4095, bool(buf[i] & 0x100)) for i in range(1, buf[0] + 1))
    totals = Counter()
    allocations = {}
    address = 0
    index = 0
    while address < 0x7fffffff0000:
        region = Region()
        if not k32.VirtualQueryEx(handle, c.c_void_p(address), c.byref(region), c.sizeof(region)):
            break
        region_base = region.BaseAddress or 0
        end = region_base + region.RegionSize
        if end <= address:
            raise RuntimeError("VirtualQueryEx made no progress")
        kind = {0x20000: "private", 0x40000: "mapped", 0x1000000: "image"}.get(region.Type, "other")
        private = shared = 0
        while index < len(pages) and pages[index][0] < end:
            if pages[index][0] >= region_base:
                if pages[index][1]:
                    shared += 4096
                else:
                    private += 4096
            index += 1
        totals[kind + "_private_resident_bytes"] += private
        totals[kind + "_shared_resident_bytes"] += shared
        if region.State == 0x1000:  # MEM_COMMIT; mapped/image commit is not process PrivateBytes.
            totals[kind + "_committed_virtual_bytes"] += region.RegionSize
        if region.State == 0x1000 or private or shared:
            base = region.AllocationBase or region.BaseAddress
            row = allocations.setdefault(base, {"base": hex(base), "kind": kind, "committed_virtual_bytes": 0,
                                                "private_resident_bytes": 0, "shared_resident_bytes": 0})
            row["committed_virtual_bytes"] += region.RegionSize if region.State == 0x1000 else 0
            row["private_resident_bytes"] += private
            row["shared_resident_bytes"] += shared
            if kind in ("mapped", "image") and "file" not in row:
                name = c.create_unicode_buffer(1024)
                psapi.GetMappedFileNameW(handle, c.c_void_p(base), name, len(name))
                row["file"] = name.value
        address = end
    return {"counters": counters(handle, pid), "totals": dict(totals),
            "allocations": sorted(allocations.values(), key=lambda row: row["private_resident_bytes"], reverse=True)}
