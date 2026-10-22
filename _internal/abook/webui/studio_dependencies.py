"""Render hash checked Studio requirements from the lock shipped inside the signed app."""
from pathlib import Path
import re
import tomllib


def locked_requirements(requirements: Path, lock_path: Path) -> tuple[str, list[str]]:
    packages = {re.sub(r"[-_.]+", "-", p["name"]).lower(): p
                for p in tomllib.loads(lock_path.read_text(encoding="utf-8"))["package"]}
    lines, git = [], []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--extra-index-url "):
            lines.append(line)
            continue
        match = re.fullmatch(r"([\w.-]+)==([^\s;]+)", line)
        vcs = re.fullmatch(r"([\w.-]+)\s+@\s+git\+https://[^\s]+@([a-f0-9]{40})", line)
        if not match and not vcs:
            raise ValueError(f"Không có ghim đầy đủ cho {line}")
        name, version = (match or vcs).groups()
        package = packages.get(re.sub(r"[-_.]+", "-", name).lower(), {})
        if vcs:
            source = package.get("source", {}).get("git", "")
            if not source.endswith("#" + version) or source.split("?", 1)[0].split("#", 1)[0] != line.split("git+", 1)[1].rsplit("@", 1)[0]:
                raise ValueError(f"Git commit không khớp lock: {name}")
            git.append(line)
            continue
        files = package.get("wheels", []) + ([package["sdist"]] if "sdist" in package else [])
        hashes = sorted({f["hash"] for f in files if re.fullmatch(r"sha256:[a-f0-9]{64}", f.get("hash", ""))})
        if package.get("version") != version or not hashes:
            raise ValueError(f"Thiếu hash tin cậy trong uv.lock: {name}=={version}")
        lines.append(line + " " + " ".join("--hash=" + h for h in hashes))
    return "\n".join(lines) + "\n", git
