"""Đăng model phân tích tự huấn luyện lên Hugging Face để Studio tải về (chủ sách 28-09: đăng công khai - "có"; nơi đăng
là Hugging Face, không phải GitHub Release).

    python scripts/publish_model.py lora28v3-4b:latest abook-analyzer:v3 --notes docs/models/abook-analyzer-v3.md \
        --out D:/Novels/LLM_Train/release --hf <tài khoản>/abook-analyzer
    python scripts/publish_model.py ... (không --hf)      # chỉ kiểm và chuẩn bị, không đăng

Lấy ĐÚNG file GGUF mà Ollama của máy dev đang phục vụ (lớp model trong manifest - thứ mọi lượt đo đã chạy), kiểm băm khớp
digest của Ollama, tải thẳng từ blob lên Hugging Face (không chép 4 GB ra đĩa) cùng thẻ model và Modelfile, rồi in mục
`PUBLISHED_MODELS` cho `webui/studio_setup.py` với đường tải ghim theo commit (không đổi dưới chân Studio). Model tạo lại ở
Studio bằng /api/create từ đúng file ấy trùng từng byte bản đã đo (thử 28-09). Lớp khuôn chat và tham số đi theo (nền
Qwen3-8B cần khuôn qwen3 của Ollama - tạo chỉ từ GGUF thì ra khuôn Jinja thô, đo 29-09): khuôn ghi vào
`ebook_reader/webui/model_templates/` để đi cùng app, ghim băm; tham số in thẳng vào mục. Lớp giấy phép chỉ lên Modelfile
ở Hugging Face. Lớp khác (adapter, system, messages...) thì từ chối - Studio không tạo lại được.

Hugging Face tách model khỏi repo app có chủ ý: model học từ nhãn trên truyện có bản quyền - khiếu nại nếu có chỉ chạm
model, không khoá repo cùng đường tự cập nhật của app. Đăng nhập một lần bằng `hf auth login` (chủ sách tự dán token;
script không bao giờ đọc hay in token).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

MODEL_LAYER = "application/vnd.ollama.image.model"
SIDE_LAYERS = {"application/vnd.ollama.image.template": "template", "application/vnd.ollama.image.params": "params",
               "application/vnd.ollama.image.license": "license"}
TEMPLATES = Path(__file__).resolve().parents[1] / "ebook_reader" / "webui" / "model_templates"


def models_dir() -> Path:
    return Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")


def _layers(name: str) -> list[dict]:
    base, _, tag = name.partition(":")
    manifest = models_dir() / "manifests" / "registry.ollama.ai" / "library" / base / (tag or "latest")
    return json.loads(manifest.read_text(encoding="utf-8"))["layers"]


def model_layer(name: str) -> tuple[Path, str, int]:
    """(file blob, băm hex, cỡ) của lớp GGUF duy nhất của model `name` ("lora28v3-4b:latest"). Lớp khác chỉ được là khuôn
    chat / tham số / giấy phép (`side_layers`)."""
    layers = _layers(name)
    models = [layer for layer in layers if layer["mediaType"] == MODEL_LAYER]
    others = [layer["mediaType"] for layer in layers if layer["mediaType"] != MODEL_LAYER and layer["mediaType"] not in SIDE_LAYERS]
    if len(models) != 1 or others:
        raise SystemExit(f"{name}: cần đúng một lớp GGUF và chỉ thêm khuôn/tham số/giấy phép, có "
                         f"{[layer['mediaType'] for layer in layers]} - Studio không tạo lại được lớp khác")
    digest = models[0]["digest"].removeprefix("sha256:")
    return models_dir() / "blobs" / f"sha256-{digest}", digest, int(models[0]["size"])


def side_layers(name: str) -> dict[str, tuple[bytes, str]]:
    """{"template"/"params"/"license": (nội dung, băm hex)} - kiểm từng blob khớp digest của nó."""
    found: dict[str, tuple[bytes, str]] = {}
    for layer in _layers(name):
        kind = SIDE_LAYERS.get(layer["mediaType"])
        if kind is None:
            continue
        digest = layer["digest"].removeprefix("sha256:")
        data = (models_dir() / "blobs" / f"sha256-{digest}").read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"Blob {kind} của {name} không khớp digest - hỏng?")
        found[kind] = (data, digest)
    return found


def quantization(name: str) -> str:
    try:
        request = urllib.request.Request("http://127.0.0.1:11434/api/show", data=json.dumps({"model": name}).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            return str(json.loads(response.read())["details"]["quantization_level"])
    except (OSError, ValueError, KeyError):
        return "gguf"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 22):
            digest.update(chunk)
    return digest.hexdigest()


def publish(repo: str, blob: Path, file: str, folder: Path) -> str:
    """Tải lên Hugging Face, trả commit chứa file GGUF."""
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo, repo_type="model", exist_ok=True)
    api.upload_file(path_or_fileobj=str(folder / "README.md"), path_in_repo="README.md", repo_id=repo,
                    commit_message="Model card")
    api.upload_file(path_or_fileobj=str(folder / "Modelfile"), path_in_repo="Modelfile", repo_id=repo,
                    commit_message="Modelfile")
    return str(api.upload_file(path_or_fileobj=str(blob), path_in_repo=file, repo_id=repo, commit_message=file).oid)


def check_download(url: str, size: int) -> None:
    """Thử đúng đường Studio sẽ đi: tải được, đúng cỡ, nhận Range (tải tiếp khi đứt mạng)."""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-0"}), timeout=60) as response:
        total = response.headers.get("Content-Range", "").rsplit("/", 1)[-1]
        print(f"  tải thử: HTTP {response.status}, cỡ {total} {'OK' if response.status == 206 and total == str(size) else 'SAI'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="tên model trong Ollama của máy dev, vd lora28v3-4b:latest")
    parser.add_argument("name", help="tên đăng, cũng là tên trong cài đặt phân tích, vd abook-analyzer:v3")
    parser.add_argument("--notes", type=Path, required=True, help="thẻ model (docs/models/<tên>.md)")
    parser.add_argument("--out", type=Path, required=True, help="thư mục chuẩn bị (ngoài repo)")
    parser.add_argument("--hf", metavar="REPO", help="repo Hugging Face, vd <tài khoản>/abook-analyzer")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*:[a-z0-9._-]+", args.name):
        raise SystemExit("Tên đăng dạng tên:nhãn, chữ thường - vd abook-analyzer:v3")
    blob, digest, size = model_layer(args.source)
    file = f"{args.name.replace(':', '-')}.{quantization(args.source)}.gguf"
    folder = args.out / args.name.replace(":", "-")
    folder.mkdir(parents=True, exist_ok=True)
    print(f"{args.source} -> {args.name}: {size:,} byte, sha256 {digest[:12]}", flush=True)
    if file_sha256(blob) != digest:
        raise SystemExit("Blob của Ollama không khớp digest của nó - hỏng?")
    side = side_layers(args.source)
    modelfile = f"FROM ./{file}\n"
    template_name = ""
    if "template" in side:
        text, template_digest = side["template"]
        modelfile += f'TEMPLATE """{text.decode("utf-8")}"""\n'
        template_name = f"{args.name.replace(':', '-')}.gotmpl"
        TEMPLATES.mkdir(parents=True, exist_ok=True)
        (TEMPLATES / template_name).write_bytes(text)  # đúng từng byte - Studio kiểm băm trước khi tạo
        print(f"  khuôn chat -> {TEMPLATES / template_name} (sha256 {template_digest[:12]}) - commit cùng mục PUBLISHED_MODELS")
    parameters = json.loads(side["params"][0]) if "params" in side else {}
    for key, value in parameters.items():
        for item in value if isinstance(value, list) else [value]:
            modelfile += f"PARAMETER {key} {json.dumps(item, ensure_ascii=False) if isinstance(item, str) else item}\n"
    if "license" in side:
        modelfile += f'LICENSE """{side["license"][0].decode("utf-8")}"""\n'
    (folder / "Modelfile").write_text(modelfile, encoding="utf-8", newline="\n")
    shutil.copyfile(args.notes, folder / "README.md")
    if not args.hf:
        print(f"Đã kiểm, chuẩn bị ở {folder}. Chưa đăng (thêm --hf <repo>).")
        return 0
    commit = publish(args.hf, blob, file, folder)
    url = f"https://huggingface.co/{args.hf}/resolve/{commit}/{file}"
    check_download(url, size)
    print("\n# webui/studio_setup.py - PUBLISHED_MODELS")
    extra = ""
    if template_name:
        extra += f'        template="{template_name}",\n        template_sha256="{side["template"][1]}",\n'
    if parameters:
        extra += f"        parameters={json.dumps(json.dumps(parameters, separators=(',', ':')))},\n"
    print(f'    "{args.name}": PublishedModel(\n        "{args.name}",\n'
          f'        (Download("{file}", "{url}",\n                  "{digest}", {size:_}),),\n'
          f'        "{digest}",\n        {size:_},\n{extra}    ),')
    return 0


if __name__ == "__main__":
    sys.exit(main())
