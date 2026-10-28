"""Resolve recorded Win32 starts off-line with DbgHelp and public Microsoft PDBs.

Run after timing, so symbol downloading cannot contaminate a benchmark.
Qt export-only answers retain their displacement; never call a nearby export
the actual thread function. No process attachment or administrator rights.
"""
import ctypes as c
from ctypes import wintypes as w
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "build/idlecpu-evidence"
KIT = Path("C:/Program Files (x86)/Windows Kits/10/Debuggers/x64")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, action="append", help="thread summary JSON (repeatable)")
    ap.add_argument("--output", type=Path, default=ROOT / "symbols-final.json")
    args = ap.parse_args()
    dll_dir = os.add_dll_directory(str(KIT))
    dbg = c.WinDLL(str(KIT / "dbghelp.dll"), use_last_error=True)
    dbg.SymInitializeW.argtypes = [w.HANDLE, w.LPCWSTR, w.BOOL]
    dbg.SymLoadModuleExW.argtypes = [w.HANDLE, w.HANDLE, w.LPCWSTR, w.LPCWSTR, c.c_ulonglong, w.DWORD, c.c_void_p, w.DWORD]
    dbg.SymLoadModuleExW.restype = c.c_ulonglong
    dbg.SymFromAddr.argtypes = [w.HANDLE, c.c_ulonglong, c.POINTER(c.c_ulonglong), c.c_void_p]
    dbg.SymCleanup.argtypes = [w.HANDLE]
    dbg.SymUnloadModule64.argtypes = [w.HANDLE, c.c_ulonglong]
    dbg.SymSetOptions(0x00000004 | 0x00000200 | 0x00080000)  # deferred, fail critical, no prompts
    cache = ROOT / "symbols"
    cache.mkdir(exist_ok=True)
    kernel = c.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = w.HANDLE
    token = kernel.GetCurrentProcess()  # no invasion or attachment
    if not dbg.SymInitializeW(token, f"srv*{cache}*https://msdl.microsoft.com/download/symbols", False):
        raise c.WinError(c.get_last_error())
    starts, result = {}, []
    # Do not resolve rejected prototypes against a different executable now
    # occupying build/ABookDesk.exe. Only measured final artifacts by default.
    inputs = args.input or [ROOT / "stage1/ab.json", ROOT / "native/ab.json", ROOT / "hidden/thread-summary.json"]
    for path in inputs:
        data = json.loads(path.read_bytes())
        groups = [data] if data and "identity" in data[0] else [row["threads"] for row in data]
        for group in groups:
            for thread in group:
                ident = thread.get("identity", {})
                if "module" in ident:
                    starts[(ident["module"], ident["module_offset"])] = ident
    try:
        for (path, offset), ident in starts.items():
            # DLLs share the same preferred PE base. Unload between images so
            # the next image can use its preferred base without overlap.
            base = dbg.SymLoadModuleExW(token, None, path, None, 0, 0, None, 0)
            row = dict(module=path, module_offset=offset, loaded=bool(base), symbol_base=hex(base))
            if base:
                info = c.create_string_buffer(88 + 2048)
                c.c_ulong.from_buffer(info).value = 88
                c.c_ulong.from_buffer(info, 80).value = 2048
                delta = c.c_ulonglong()
                if dbg.SymFromAddr(token, base + int(offset, 16), c.byref(delta), info):
                    row.update(symbol=c.string_at(c.addressof(info) + 84).decode("utf-8", "replace"), displacement=hex(delta.value),
                               exact=delta.value == 0, flags=hex(c.c_ulong.from_buffer(info, 28).value))
                else:
                    row["error"] = c.get_last_error()
                dbg.SymUnloadModule64(token, base)
            result.append(row)
            print(Path(path).name, offset, row.get("symbol"), row.get("displacement"), flush=True)
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    finally:
        dbg.SymCleanup(token)
        dll_dir.close()


if __name__ == "__main__":
    main()
