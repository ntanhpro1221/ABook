"""Đăng model phân tích tự huấn luyện để Studio tải về (chủ sách 28-09: đăng công khai - "có").

    python scripts/publish_model.py lora28v3-4b:latest abook-analysis:v3 --notes docs/models/abook-analysis-v3.md \
        --out D:/Novels/LLM_Train/release --hf <tài khoản>/abook-analysis     # Hugging Face (nơi nên dùng)
    python scripts/publish_model.py ... --github                               # GitHub Release (dự phòng)
    python scripts/publish_model.py ...                                         # chỉ chuẩn bị file, không đăng

Lấy ĐÚNG file GGUF mà Ollama của máy dev đang phục vụ (lớp model trong manifest - thứ mọi lượt đo đã chạy), kiểm băm khớp
digest của Ollama, rồi in mục `PUBLISHED_MODELS` cho `webui/studio_setup.py`. Model tạo lại ở Studio bằng /api/create từ
đúng file ấy trùng từng byte bản đã đo (thử 28-09), nên model có lớp nào ngoài lớp GGUF (template, tham số, adapter) thì
từ chối.

Hugging Face: một file, đường tải ghim theo commit (không đổi dưới chân Studio). Tách khỏi repo app có chủ ý: model học từ
nhãn trên truyện có bản quyền - khiếu nại nếu có chỉ chạm model, không khoá repo cùng đường tự cập nhật của app. Đăng nhập
một lần bằng `hf auth login` (chủ sách tự dán token; script không bao giờ đọc hay in token).

GitHub Release: cắt phần dưới 2 GiB (giới hạn MỖI tệp; tổng và băng thông không giới hạn), tạo với `--latest=false`: app
đã cài đọc `releases/latest/download/latest.json` để tự cập nhật - release model mà thành "latest" thì mọi bản cài mất
đường cập nhật (docs/RELEASING.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "ntanhpro1221/ABook"
OWNER = "ntanhpro1221"
PART_BYTES = 1_900_000_000  # dưới 2 GiB (2 147 483 648) một khoảng an toàn
MODEL_LAYER = "application/vnd.ollama.image.model"


def models_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def model_layer(name: str) -> tuple[Path, str, int]:
    """(file blob, băm hex, cỡ) của lớp GGUF duy nhất của model `name` ("lora28v3-4b:latest")."""
    base, _, tag = name.partition(":")
    manifest = models_dir() / "manifests" / "registry.ollama.ai" / "library" / base / (tag or "latest")
    layers = json.loads(manifest.read_text(encoding="utf-8"))["layers"]
    models = [layer for layer in layers if layer["mediaType"] == MODEL_LAYER]
    if len(models) != 1 or len(layers) != 1:
        raise SystemExit(f"{name}: cần đúng một lớp GGUF, có {[layer['mediaType'] for layer in layers]} - Studio tạo model "
                         "chỉ từ file GGUF, lớp khác (template, tham số, adapter) sẽ mất")
    digest = models[0]["digest"].removeprefix("sha256:")
    return models_dir() / "blobs" / f"sha256-{digest}", digest, int(models[0]["size"])


def quantization(name: str) -> str:
    try:
        request = urllib.request.Request("http://127.0.0.1:11434/api/show", data=json.dumps({"model": name}).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return str(json.loads(response.read())["details"]["quantization_level"])
    except (OSError, ValueError, KeyError):
        return "gguf"


def copy_checked(blob: Path, digest: str, size: int, target: Path, part_bytes: int = 0) -> list[dict[str, object]]:
    """Chép `blob` ra `target` (cả file) hoặc `target.partN` (khi `part_bytes`), băm từng mảnh; cả file phải khớp digest."""
    target.parent.mkdir(parents=True, exist_ok=True)
    whole = hashlib.sha256()
    pieces: list[dict[str, object]] = []
    limit = part_bytes or size
    with blob.open("rb") as source:
        index = 0
        while True:
            index += 1
            path = target.with_name(f"{target.name}.part{index}") if part_bytes else target
            piece = hashlib.sha256()
            written = 0
            with path.open("wb") as handle:
                while written < limit and (chunk := source.read(min(1 << 22, limit - written))):
                    handle.write(chunk)
                    piece.update(chunk)
                    whole.update(chunk)
                    written += len(chunk)
            if written == 0:
                path.unlink()
                break
            pieces.append({"name": path.name, "path": path, "sha256": piece.hexdigest(), "size": written})
            print(f"  {path.name}: {written:,} byte, {piece.hexdigest()[:12]}", flush=True)
            if not part_bytes:
                break
    if whole.hexdigest() != digest or sum(int(piece["size"]) for piece in pieces) != size:
        raise SystemExit("Chép xong mà băm cả file không khớp digest của Ollama - blob hỏng?")
    return pieces


def registry_entry(name: str, digest: str, size: int, downloads: list[tuple[str, str, str, int]]) -> str:
    lines = [f'    "{name}": PublishedModel(', f'        "{name}",', "        ("]
    for file, url, sha, length in downloads:
        lines += [f'            Download("{file}", "{url}",', f'                     "{sha}", {length:_}),']
    lines += ["        ),", f'        "{digest}",', f"        {size:_},", "    ),"]
    return "\n".join(lines)


def publish_hf(repo: str, blob: Path, stem: str, notes: Path, modelfile: Path) -> str:
    """Tải lên Hugging Face thẳng từ blob của Ollama (không chép 4 GB ra đĩa), trả commit chứa file GGUF - đường tải ghim
    theo commit."""
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo, repo_type="model", exist_ok=True)
    api.upload_file(path_or_fileobj=str(notes), path_in_repo="README.md", repo_id=repo, commit_message="Model card")
    api.upload_file(path_or_fileobj=str(modelfile), path_in_repo="Modelfile", repo_id=repo, commit_message="Modelfile")
    commit = api.upload_file(path_or_fileobj=str(blob), path_in_repo=stem, repo_id=repo, commit_message=stem)
    return str(commit.oid)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 22):
            digest.update(chunk)
    return digest.hexdigest()


def publish_github(tag: str, name: str, files: list[Path], notes: Path) -> None:
    token = subprocess.run(["gh", "auth", "token", "--user", OWNER], capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["gh", "release", "create", tag, *map(str, files), "--repo", REPO, "--target", "main", "--latest=false",
                    "--title", f"Model phân tích {name}", "--notes-file", str(notes)],
                   env={**os.environ, "GH_TOKEN": token}, check=True)


def check_download(url: str, size: int) -> None:
    """Thử đúng đường Studio sẽ đi: tải được, đúng cỡ, nhận Range (tải tiếp khi đứt mạng)."""
    request = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = response.headers.get("Content-Range", "").rsplit("/", 1)[-1]
        print(f"  {url.rsplit('/', 1)[-1]}: HTTP {response.status}, cỡ {total} "
              f"{'OK' if response.status == 206 and total == str(size) else 'SAI'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="tên model trong Ollama của máy dev, vd lora28v3-4b:latest")
    parser.add_argument("name", help="tên đăng, cũng là tên trong cài đặt phân tích, vd abook-analysis:v3")
    parser.add_argument("--notes", type=Path, required=True, help="thẻ model (docs/models/<tên>.md)")
    parser.add_argument("--out", type=Path, required=True, help="thư mục chứa file chuẩn bị (ngoài repo)")
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--hf", metavar="REPO", help="đăng lên Hugging Face, vd <tài khoản>/abook-analysis")
    where.add_argument("--github", action="store_true", help="đăng lên GitHub Release (cắt phần)")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*:[a-z0-9._-]+", args.name):
        raise SystemExit("Tên đăng dạng tên:nhãn, chữ thường - vd abook-analysis:v3")
    blob, digest, size = model_layer(args.source)
    stem = f"{args.name.replace(':', '-')}.{quantization(args.source)}.gguf"
    tag = "model-" + args.name.replace(":", "-")
    folder = args.out / tag
    print(f"{args.source} -> {args.name}: {size:,} byte, sha256 {digest[:12]}; chuẩn bị ở {folder}", flush=True)
    if args.github:
        pieces = copy_checked(blob, digest, size, folder / stem, PART_BYTES)
    else:
        folder.mkdir(parents=True, exist_ok=True)
        if file_sha256(blob) != digest:
            raise SystemExit("Blob của Ollama không khớp digest của nó - hỏng?")
        pieces = [{"name": stem, "path": blob, "sha256": digest, "size": size}]
    modelfile = folder / "Modelfile"
    modelfile.write_text(f"FROM ./{stem}\n", encoding="utf-8", newline="\n")
    checksums = folder / f"{stem}.sha256"
    checksums.write_text("".join(f"{piece['sha256']}  {piece['name']}\n" for piece in pieces if piece["name"] != stem)
                         + f"{digest}  {stem}\n", encoding="utf-8", newline="\n")
    shutil.copyfile(args.notes, folder / "README.md")

    if args.hf:
        commit = publish_hf(args.hf, blob, stem, folder / "README.md", modelfile)
        url = f"https://huggingface.co/{args.hf}/resolve/{commit}/{stem}"
        downloads = [(stem, url, digest, size)]
    elif args.github:
        publish_github(tag, args.name, [Path(str(piece["path"])) for piece in pieces] + [checksums, modelfile],
                       folder / "README.md")
        base = f"https://github.com/{REPO}/releases/download/{tag}"
        downloads = [(str(piece["name"]), f"{base}/{piece['name']}", str(piece["sha256"]), int(piece["size"]))
                     for piece in pieces]
    else:
        print("\nChưa đăng (thêm --hf hoặc --github).")
        return 0
    for _file, url, _sha, length in downloads:
        check_download(url, length)
    print("\n# webui/studio_setup.py - PUBLISHED_MODELS")
    print(registry_entry(args.name, digest, size, downloads))
    return 0


if __name__ == "__main__":
    sys.exit(main())
