r"""Every DLL a shipped binary imports must come with the package or with Windows itself (docs/QT_INSTALLER.md, cỡ bộ cài).

The build machine has the VC++ redistributable in System32, so a dist missing msvcp140_2.dll (say) still starts here and
fails on a PC without it; smoke tests cannot see that. This reads the import tables (normal + delay-load) of every .exe /
.dll / .pyd under <dist> and resolves each name the way Windows does for an app-local install: the binary's own folder,
then its app folder (dist\ for the Qt app and its plugins, resources\python\ for everything Python loads). A name found
neither there nor in System32 fails, and so does a VC++ runtime name (vcruntime*, msvcp*, concrt*, vccorlib*, vcomp*)
found only in System32: Windows ships no such DLL.

check_imports.py <dist>   -> IMPORTS_OK <n> binaries / IMPORTS_FAIL <binary>: <dll> ...
"""
import argparse
import os
import re
import struct
import sys
from pathlib import Path

REDIST = re.compile(r"^(vcruntime|msvcp|concrt|vccorlib|vcomp|ucrtbased)\d", re.I)
SYSTEM32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"


def imports(path: Path) -> list[str]:
    """DLL names in the import and delay-import tables of a PE32+ file."""
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE file")
    sections_count, optional_size = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("not PE32+ (x64)")
    directories = optional + 112
    sections = [struct.unpack_from("<IIII", data, optional + optional_size + 40 * i + 8) for i in range(sections_count)]

    def offset(rva: int) -> int:
        for virtual_size, address, raw_size, raw in sections:
            if address <= rva < address + max(virtual_size, raw_size):
                return raw + rva - address
        raise ValueError(f"RVA {rva:#x} outside every section")

    def name(rva: int) -> str:
        start = offset(rva)
        return data[start:data.index(b"\0", start)].decode("ascii")

    found = []
    for index, size, name_field in ((1, 20, 12), (13, 32, 4)):
        table = struct.unpack_from("<I", data, directories + 8 * index)[0]
        if not table:
            continue
        at = offset(table)
        while data[at:at + size].strip(b"\0"):
            found.append(name(struct.unpack_from("<I", data, at + name_field)[0]))
            at += size
    return found


def missing(dist: Path) -> dict[Path, list[str]]:
    python = dist / "resources" / "python"
    problems = {}
    for binary in sorted(p for p in dist.rglob("*") if p.suffix.lower() in {".exe", ".dll", ".pyd"} and p.is_file()):
        home = python if binary.is_relative_to(python) else dist
        lacking = []
        for dll in imports(binary):
            if (binary.parent / dll).is_file() or (home / dll).is_file() or dll.lower().startswith(("api-ms-win-", "ext-ms-")):
                continue
            if REDIST.match(dll) or not (SYSTEM32 / dll).is_file():
                lacking.append(dll)
        if lacking:
            problems[binary] = lacking
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", type=Path)
    args = ap.parse_args()
    dist = args.dist.resolve()
    count = sum(1 for p in dist.rglob("*") if p.suffix.lower() in {".exe", ".dll", ".pyd"})
    problems = missing(dist)
    for binary, lacking in problems.items():
        print(f"IMPORTS_FAIL {binary.relative_to(dist)}: {', '.join(lacking)}")
    if problems:
        return 1
    print(f"IMPORTS_OK {count} binaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
