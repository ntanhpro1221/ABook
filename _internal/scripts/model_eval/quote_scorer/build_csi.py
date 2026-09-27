"""CSI + JY + WP (nhận dạng người nói trong tiểu thuyết TIẾNG TRUNG) -> cửa sổ cùng dạng build_vi.py, để học trước.

    D:/Novels/LLM_Train/.venv/Scripts/python.exe scripts/model_eval/quote_scorer/build_csi.py \
        --repo D:/Novels/LLM_Train/csi --out D:/Novels/LLM_Train/data/zh_windows

Nguồn: github.com/yudiandoris/csi (Yu, Zhou, Yu - "End-to-End Chinese Speaker Identification", NAACL 2022). CSI là
TRUYỆN MẠNG Trung Quốc (死亡万花筒, 残次品...) - đúng thể loại gốc của phần lớn truyện dịch app đọc, gần hơn PDNC (tiểu
thuyết Anh cổ điển) nhiều; JY là Kim Dung, WP là 平凡的世界. GIẤY PHÉP: dữ liệu CSI "chỉ cho nghiên cứu phi thương mại" -
không commit dữ liệu, không phát hành mô hình học từ nó mà chưa hỏi chủ sách.

Dữ liệu gốc là hỏi-đáp trích đoạn (ngữ cảnh ~270 chữ, câu hỏi = câu thoại, đáp án = MỘT chỗ nhắc người nói), không có
danh sách nhân vật. Dựng lại cho bộ chấm:
- từ điển tên = mọi chuỗi đáp án của cùng bộ dữ liệu (bỏ đại từ 我/你/他/她..., bỏ chuỗi 1 chữ hoặc có □ - CSI che ~10%
  số chữ bằng □); tên là HẬU TỐ của tên dài hơn 1-2 chữ (少平 / 孙少平: tên / họ + tên) gộp làm một người;
- chỗ nhắc = mọi lần khớp tên trong ngữ cảnh, dài trước (孙少平 không bị cắt thành 少平);
- câu thoại = vị trí câu hỏi trong ngữ cảnh; người nói = người của chuỗi đáp án; câu mà đáp án là đại từ thì bỏ.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

PRONOUNS = {"我", "你", "他", "她", "它", "我们", "你们", "他们", "她们", "咱", "咱们", "俺", "本座", "在下", "老子", "朕"}
# Đáp án là cụm chỉ định chung ("其中一个" = một trong số đó) thì không phải tên: khớp nó sẽ gắn chỗ nhắc giả vào "一个"
# ở gần như mọi ngữ cảnh. Từ chỉ vai ("姑娘" = cô gái) vẫn là tên được nếu truyện dùng thế, nhưng không được gộp hậu tố
# vào tên riêng ("莉莉姑娘").
DESCRIPTOR = re.compile("一个|其中|那个|这个|某个|有人|众人|大家|对方|那人|此人|两人|几人|所有")
ROLE_WORDS = {"姑娘", "少年", "少女", "公子", "小姐", "先生", "夫人", "大人", "师父", "师兄", "师姐", "师妹", "师弟", "老人",
              "男人", "女人", "大哥", "大姐", "哥哥", "姐姐", "妹妹", "弟弟", "老板", "老师", "同学", "医生", "队长"}
SOURCES = {
    "csi": ["data/CSI/train_v1.json", "data/CSI/dev_v1.json"],
    "jy": ["data/JY/train.json", "data/JY/dev.json", "data/JY/test.json"],
    "wp": ["data/WP2021/train_unsplit.json", "data/WP2021/dev_unsplit.json", "data/WP2021/test_unsplit.json"],
}


def entity_table(names: Counter) -> dict[str, str]:
    """tên -> thực thể (tên dài nhất trong nhóm hậu tố)."""
    usable = [name for name in names
              if len(name) >= 2 and "□" not in name and name not in PRONOUNS and not DESCRIPTOR.search(name)]
    parent = {name: name for name in usable}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    by_suffix: dict[str, list[str]] = {}
    for name in usable:
        by_suffix.setdefault(name[-2:], []).append(name)
    for group in by_suffix.values():
        for long in group:
            for short in group:
                if short != long and short not in ROLE_WORDS and long.endswith(short) and 1 <= len(long) - len(short) <= 2:
                    a, b = find(long), find(short)
                    if a != b:
                        parent[b] = a if len(a) >= len(b) else b
                        parent[a] = parent[b]
    return {name: find(name) for name in usable}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    stats: Counter = Counter()
    with (args.out / "train.jsonl").open("w", encoding="utf-8") as writer:
        for source, files in SOURCES.items():
            documents = [paragraph for name in files
                         for document in json.loads((args.repo / name).read_text(encoding="utf-8"))["data"]
                         for paragraph in document["paragraphs"]]
            names = Counter(qa["answers"][0]["text"] for paragraph in documents for qa in paragraph["qas"] if qa["answers"])
            names = Counter({name: count for name, count in names.items() if re.fullmatch(r"\w+", name)})
            # Chuỗi đáp án gán nhầm (东西 = đồ vật, 眼睛 = mắt, 电话 = điện thoại): xuất hiện hàng nghìn lần mà hiếm khi là
            # người nói -> bỏ khỏi từ điển, kẻo mọi "东西" trong văn bản thành ứng viên.
            everywhere = Counter()
            rough = re.compile("|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)))
            for paragraph in documents:
                everywhere.update(match.group(0) for match in rough.finditer(paragraph["context"]))
            names = Counter({name: count for name, count in names.items()
                             if count > 5 or count >= 0.01 * everywhere.get(name, 0)})
            entity = entity_table(names)
            ordered = sorted(entity, key=len, reverse=True)
            pattern = re.compile("|".join(re.escape(name) for name in ordered))
            print(f"  {source}: {len(documents)} ngữ cảnh, {len(entity)} tên -> {len(set(entity.values()))} người", flush=True)
            for paragraph in documents:
                text = paragraph["context"]
                mentions = [{"start": m.start(), "end": m.end(), "entities": [entity[m.group(0)]]} for m in pattern.finditer(text)]
                quotes = []
                for qa in paragraph["qas"]:
                    stats[f"{source} câu"] += 1
                    answer = qa["answers"][0]["text"] if qa["answers"] else ""
                    speaker = entity.get(answer)
                    start = text.find(qa["question"])
                    if speaker is None or start < 0:
                        stats[f"{source} bỏ (đáp án đại từ/không phải tên)"] += 1
                        continue
                    covered = any(speaker in mention["entities"] for mention in mentions)
                    stats[f"{source} người nói có trong ứng viên"] += covered
                    quotes.append({"start": start, "end": start + len(qa["question"]), "speaker": speaker, "kind": "D",
                                   "book": f"zh/{source}", "chapter": source, "seq": len(quotes) + 1000 * stats["cửa sổ"]})
                if quotes:
                    writer.write(json.dumps({"text": text, "quotes": quotes, "mentions": mentions}, ensure_ascii=False) + "\n")
                    stats["cửa sổ"] += 1
    print(dict(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
