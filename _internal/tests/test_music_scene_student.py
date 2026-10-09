"""Học sinh hình không khí trong chương, đường q06 (webui/music_scene_student.py + music_scenes.apply_student): nhúng bằng Qwen3-0.6B cắt lớp,
căn giữa trong chương + đầu hồi quy, đầu mức chương (LV-Q06), bộ nhớ đệm, kiểu số CPU, áp vào đoạn (mức chương + hình), móc sau pha phân tích, bộ ví dụ cố định với gói
thật (chỉ chạy khi ABOOK_MUSIC_SCENE_STUDENT_DIR trỏ tới gói). Gói giả nhỏ dựng ngay trong test (Qwen3 4 lớp, hidden 32, tokenizer WordLevel);
không cần mạng, không GPU."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
from tokenizers import Tokenizer, models, pre_tokenizers  # noqa: E402
from transformers import AutoModel, AutoTokenizer, PreTrainedTokenizerFast, Qwen3Config  # noqa: E402

from abook.webui import music_module, music_plan, music_scene_student as student, music_scenes  # noqa: E402

WIDTH, LAYER, MAX_TOKENS = 32, 2, 7
VOCAB = ["[UNK]"] + [f"w{i}" for i in range(24)]


# ---- gói giả --------------------------------------------------------------------------------------------------------------------
def _build_package(root: Path, *, cut: bool = False, seed: int = 0) -> Path:
    """Qwen3 4 lớp (bf16, như gói thật) + tokenizer + đầu hồi quy ngẫu nhiên có hạt. `cut`: file đã cắt sẵn còn LAYER lớp (như gói phát hành)."""
    root.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(seed)
    config = Qwen3Config(vocab_size=len(VOCAB), hidden_size=WIDTH, intermediate_size=64, num_hidden_layers=4, num_attention_heads=4,
                         num_key_value_heads=2, head_dim=8, max_position_embeddings=256, initializer_range=0.5)
    model = AutoModel.from_config(config).to(torch.bfloat16)
    if cut:
        model.layers = model.layers[:LAYER]
        model.config.num_hidden_layers = LAYER
        model.config.layer_types = model.config.layer_types[:LAYER]
    model.save_pretrained(root)
    tokenizer = Tokenizer(models.WordLevel({word: index for index, word in enumerate(VOCAB)}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    PreTrainedTokenizerFast(tokenizer_object=tokenizer, unk_token="[UNK]").save_pretrained(root)
    rng = np.random.default_rng(seed)
    np.savez(root / student.HEAD_FILE, mu=rng.normal(size=WIDTH), sd=rng.uniform(0.5, 1.5, size=WIDTH), coef=rng.normal(size=(WIDTH, 3)),
             intercept=np.array([0.01, -0.02, 0.03]), layer=LAYER, maxTokens=MAX_TOKENS)
    np.savez(root / student.CHAPTER_HEAD_FILE, mu=rng.normal(size=WIDTH), sd=rng.uniform(0.5, 1.5, size=WIDTH), coef=rng.normal(size=(WIDTH, 2)),
             intercept=np.array([0.05, -0.04]), axes=np.array(["V", "T"]), alpha=1000.0)
    # Kiểu số CPU đã "đo" sẵn (fp32: trọng số bf16 nở ra đúng từng bit) để test không đo thật.
    student.remember_cpu_dtype(root, "fp32", torch.__version__)
    (root / "LICENSE").write_bytes(b"Apache-2.0 (gia)")
    return root


@pytest.fixture(scope="module")
def package_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build_package(tmp_path_factory.mktemp("scene_q06"))


@pytest.fixture
def package(package_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "package"
    shutil.copytree(package_template, directory)
    monkeypatch.setenv(student.ENV_DIR, str(directory))
    return directory


def _reference_embedding(directory: Path, text: str) -> Any:
    """Tính tay: model ĐỦ 4 lớp ở fp32, hidden state sau LAYER lớp (hidden_states[LAYER], trước norm), trung bình theo token từng khúc."""
    tokenizer = AutoTokenizer.from_pretrained(str(directory))
    model = AutoModel.from_pretrained(str(directory), dtype=torch.float32).eval()
    ids = tokenizer(text, add_special_tokens=True, return_tensors="pt")["input_ids"][0]
    total, count = np.zeros(WIDTH), 0
    with torch.inference_mode():
        for start in range(0, len(ids), MAX_TOKENS):
            part = ids[start:start + MAX_TOKENS][None]
            hidden = model(input_ids=part, output_hidden_states=True).hidden_states[LAYER]
            total += hidden[0].double().sum(0).numpy()
            count += part.shape[1]
    return total / count


def _text(rng: np.random.Generator, words: int = 3) -> str:
    return " ".join(f"w{i}" for i in rng.integers(0, 24, size=words))


def _chapter(chapter: int, first_id: int, *, seed: int, blocks: int = 3) -> dict:
    """`blocks` khúc 12 câu x 6 giây (72 giây), cách nhau bằng dòng ngăn cảnh: mỗi khúc một đoạn."""
    rng = np.random.default_rng(seed)
    segments, clock, index = [], 0.0, first_id
    for block in range(blocks):
        if block:
            segments.append({"id": index, "text": "***", "kind": "narration", "emotion": "neutral", "intensity": 0,
                             "start": clock, "end": clock + 1.0})
            index, clock = index + 1, clock + 1.4
        for _ in range(12):
            segments.append({"id": index, "text": _text(rng), "kind": "narration", "emotion": "neutral", "intensity": 0,
                             "start": clock, "end": clock + 6.0})
            index, clock = index + 1, clock + 6.4
    return {"chapterId": chapter, "segments": segments}


@pytest.fixture
def book(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    scripts = [_chapter(1, 1, seed=1), _chapter(2, 101, seed=2)]
    monkeypatch.setattr(music_plan, "book_scripts", lambda _root: iter(scripts))
    return scripts


class Spy:
    """Đếm lượt nhúng (mỗi lượt = các lần forward của MỘT đoạn) và lượt nạp model."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.embeds, self.loads = [], 0
        embed, init = student._Embedder.embed, student._Embedder.__init__

        def counting_embed(this: Any, text: str) -> Any:
            self.embeds.append(text)
            return embed(this, text)

        def counting_init(this: Any, *args: Any, **kwargs: Any) -> None:
            self.loads += 1
            init(this, *args, **kwargs)

        monkeypatch.setattr(student._Embedder, "embed", counting_embed)
        monkeypatch.setattr(student._Embedder, "__init__", counting_init)


def _compute(root: Path, **kwargs: Any) -> int:
    return student.compute(root, log=lambda _line: None, **kwargs)


# ---- nhúng ----------------------------------------------------------------------------------------------------------------------
def test_the_cut_model_embeds_like_the_hidden_state_of_the_full_model(package: Path) -> None:
    text = "\n".join(_text(np.random.default_rng(5), 5) for _ in range(4))  # ~20 token > 2 khúc MAX_TOKENS
    embedder = student._Embedder(package, student.Head(package / student.HEAD_FILE), text)
    forwards = []
    embedder.model.register_forward_hook(lambda *_args: forwards.append(1))
    got = embedder.embed(text)
    ids = AutoTokenizer.from_pretrained(str(package))(text, add_special_tokens=True, return_tensors="pt")["input_ids"][0]
    assert len(embedder.model.layers) == LAYER and isinstance(embedder.model.norm, torch.nn.Identity)
    assert len(forwards) == math.ceil(len(ids) / MAX_TOKENS) > 2, "chia khúc maxTokens: mỗi khúc một lần forward"
    assert got.dtype == np.float32 and got.shape == (WIDTH,)
    assert np.allclose(got, _reference_embedding(package, text), rtol=1e-4, atol=1e-5)
    embedder.close()


def test_a_package_cut_in_advance_embeds_the_same(package: Path, tmp_path: Path) -> None:
    cut = _build_package(tmp_path / "cut", cut=True)
    text = "w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11"
    full, short = (student._Embedder(directory, student.Head(directory / student.HEAD_FILE), text) for directory in (package, cut))
    assert len(short.model.layers) == LAYER and isinstance(short.model.norm, torch.nn.Identity)
    assert np.allclose(full.embed(text), short.embed(text), rtol=1e-5, atol=1e-6)
    full.close(), short.close()


def test_an_empty_scene_embeds_to_zeros_and_a_too_shallow_package_is_refused(package: Path) -> None:
    embedder = student._Embedder(package, student.Head(package / student.HEAD_FILE), "w1 w2")
    assert not embedder.embed("").any()
    embedder.close()
    head = student.Head(package / student.HEAD_FILE)
    head.layer = 9
    with pytest.raises(ValueError):
        student._Embedder(package, head, "w1")


# ---- căn giữa + đầu hồi quy ------------------------------------------------------------------------------------------------------
def test_deviations_are_centred_in_the_chapter_then_standardised_and_regressed(package: Path) -> None:
    head = student.Head(package / student.HEAD_FILE)
    rng = np.random.default_rng(3)
    x, words = rng.normal(size=(4, WIDTH)).astype(np.float32), [5, 40, 12, 1]
    # Tính độc lập: trung bình theo số chữ, trừ đi, (x - mu) / sd, nhân coef, cộng intercept.
    mean = sum(w * row.astype(np.float64) for w, row in zip(words, x)) / sum(words)
    expected = np.array([(((row - mean) - head.mu) / head.sd) @ head.coef + head.intercept for row in x.astype(np.float64)])
    got = head.deviations(x, words)
    assert got.shape == (4, 3) and np.allclose(got, expected, atol=1e-9)
    assert not np.allclose(got, head.deviations(x, [1, 1, 1, 1])), "trọng số là số chữ, không phải đều nhau"


def test_a_chapter_with_one_scene_has_no_deviation(package: Path) -> None:
    head = student.Head(package / student.HEAD_FILE)
    assert (head.deviations(np.ones((1, WIDTH)), [10]) == 0).all() and head.deviations(np.zeros((0, WIDTH)), []).shape == (0, 3)


def test_a_head_of_the_wrong_shape_is_refused(package: Path) -> None:
    data = dict(np.load(package / student.HEAD_FILE))
    np.savez(package / student.HEAD_FILE, **{**data, "coef": data["coef"][:, :2]})
    with pytest.raises(ValueError):
        student.Head(package / student.HEAD_FILE)


def test_a_chapter_head_of_the_wrong_shape_or_axes_is_refused_and_a_broken_one_only_costs_the_chapter_level(package: Path) -> None:
    path = package / student.CHAPTER_HEAD_FILE
    data = dict(np.load(path))
    student.ChapterHead(path)
    for broken in ({**data, "coef": data["coef"][:, :1]}, {**data, "intercept": np.zeros(3)}, {**data, "sd": data["sd"][:-1]},
                   {**data, "axes": np.array(["T", "V"])}, {**data, "mu": np.zeros((WIDTH, 1))}):
        np.savez(path, **broken)
        with pytest.raises(ValueError):
            student.ChapterHead(path)
        lines: list[str] = []
        assert student.load_chapter_head(package, lines.append) is None and len(lines) == 1, "hỏng: một dòng log, không ném"
    path.write_bytes(b"khong phai npz")
    assert student.load_chapter_head(package) is None
    path.unlink()
    lines = []
    assert student.load_chapter_head(package, lines.append) is None and lines == [], "gói cũ chưa có file: không phải lỗi, không log"
    assert student.load_chapter_head(None) is None


# ---- tính cả cuốn, bộ nhớ đệm -----------------------------------------------------------------------------------------------------
def test_compute_matches_the_head_applied_to_the_reference_embeddings(package: Path, book: list[dict], tmp_path: Path) -> None:
    project = tmp_path / "project"
    assert _compute(project) == 6
    saved = student.load(project)
    assert saved["package"] == student.package_sha(package) and saved["version"] == 1 and len(saved["scenes"]) == 6
    head, chapter = student.Head(package / student.HEAD_FILE), student.ChapterHead(package / student.CHAPTER_HEAD_FILE)
    for script in book:
        segments, scenes = script["segments"], music_scenes.chapter_scenes(script)
        assert len(scenes) == 3
        position = {segment["id"]: index for index, segment in enumerate(segments)}
        texts = ["\n".join(segments[i]["text"] for i in range(position[s["firstSegment"]], position[s["lastSegment"]] + 1)) for s in scenes]
        expected = head.deviations([_reference_embedding(package, text) for text in texts], [len(text.split()) for text in texts])
        mine = [item for item in saved["scenes"] if item["chapterId"] == script["chapterId"]]
        assert [(i["firstSegment"], i["lastSegment"]) for i in mine] == [(s["firstSegment"], s["lastSegment"]) for s in scenes]
        assert np.allclose([[i["dV"], i["dE"], i["dT"]] for i in mine], expected, atol=2e-3)
        # Mức V của chương: đầu mức chương trên TB nhúng (trọng số số chữ, không căn giữa); cùng giá trị ở mọi đoạn của chương.
        embeddings = np.array([_reference_embedding(package, text) for text in texts])
        weights = np.array([len(text.split()) for text in texts], dtype=float)
        mean = (embeddings * weights[:, None]).sum(0) / weights.sum()
        expected_v = float((((mean - chapter.mu) / chapter.sd) @ chapter.coef + chapter.intercept)[0])
        assert {i["chapterV"] for i in mine} == {mine[0]["chapterV"]} and mine[0]["chapterV"] == pytest.approx(expected_v, abs=2e-3)


def test_an_old_package_without_the_chapter_head_still_runs_keeps_the_embedding_key_and_writes_no_chapter_level(
        package: Path, book: list[dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, spy = tmp_path / "project", Spy(monkeypatch)
    key = student.package_sha(package)
    assert _compute(project) == 6
    assert all("chapterV" in item for item in student.load(project)["scenes"])
    (package / student.CHAPTER_HEAD_FILE).unlink()
    assert student.present() and student.available() == student.dependencies_ok(), "thiếu đầu mức chương không làm gói thành thiếu"
    assert student.package_sha(package) == key, "thêm / bỏ đầu mức chương không đổi khoá nhúng: không nhúng lại cả cuốn"
    spy.embeds.clear()
    assert _compute(project) == 0 and not spy.embeds
    saved = student.load(project)
    assert len(saved["scenes"]) == 6 and not any("chapterV" in item for item in saved["scenes"])
    assert {s["levelSource"]["V"] for s in music_scenes.book_scenes(book, student=saved["scenes"])} == {"labels"}


def test_a_second_run_loads_no_model_and_a_changed_scene_embeds_only_that_scene(package: Path, book: list[dict], tmp_path: Path,
                                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    project, spy = tmp_path / "project", Spy(monkeypatch)
    assert _compute(project) == 6 and len(spy.embeds) == 6 and spy.loads == 1
    first = student.load(project)["scenes"]
    spy.embeds.clear()
    assert _compute(project) == 0 and not spy.embeds and spy.loads == 1, "đủ bộ nhớ đệm: không nạp model"
    assert student.load(project)["scenes"] == first
    # Sửa chữ MỘT câu của đoạn đầu chương 1 (id giữ nguyên): chỉ đoạn ấy nhúng lại, nhưng độ lệch cả chương 1 đổi (căn giữa); chương 2 không.
    book[0]["segments"][3]["text"] = "w23 w22 w21"
    assert _compute(project) == 1 and len(spy.embeds) == 1 and "w23 w22 w21" in spy.embeds[0]
    after = student.load(project)["scenes"]
    assert [i for i in after if i["chapterId"] == 2] == [i for i in first if i["chapterId"] == 2]
    assert all(a != b for a, b in zip([i for i in after if i["chapterId"] == 1], [i for i in first if i["chapterId"] == 1]))
    with np.load(project / student.CACHE_FILE) as cache:
        assert len(cache["keys"]) == 6, "bộ nhớ đệm bỏ nhúng cũ của đoạn đã sửa"


def test_a_changed_package_embeds_everything_again(package: Path, book: list[dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, spy = tmp_path / "project", Spy(monkeypatch)
    _compute(project)
    before = student.package_sha(package)
    data = dict(np.load(package / student.HEAD_FILE))
    np.savez(package / student.HEAD_FILE, **{**data, "intercept": np.array([0.5, 0.5, 0.5])})  # gói khác (cùng hình)
    assert student.package_sha(package) != before, "băm đổi theo nội dung, không bị nhớ nhầm"
    spy.embeds.clear()
    assert _compute(project) == 6 and len(spy.embeds) == 6
    assert student.load(project)["package"] == student.package_sha(package)
    with np.load(project / student.CACHE_FILE) as cache:
        assert len(cache["keys"]) == 6 and all(key.endswith(student.package_sha(package)) for key in cache["keys"])


def test_stopping_keeps_the_embeddings_and_the_next_run_continues(package: Path, book: list[dict], tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    project, spy = tmp_path / "project", Spy(monkeypatch)
    assert _compute(project, stop_requested=lambda: len(spy.embeds) >= 4) == 4  # dừng giữa chương 2
    assert [i["chapterId"] for i in student.load(project)["scenes"]] == [1, 1, 1], "chương chưa đủ nhúng thì chưa ghi"
    spy.embeds.clear()
    assert _compute(project) == 2 and len(spy.embeds) == 2
    assert len(student.load(project)["scenes"]) == 6


def test_pausing_waits_between_scenes_without_embedding(package: Path, book: list[dict], tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    spy, sleeps = Spy(monkeypatch), []
    monkeypatch.setattr(student.time, "sleep", sleeps.append)
    paused = lambda: bool(spy.embeds) and len(sleeps) < 3  # noqa: E731
    assert _compute(tmp_path / "project", pause_requested=paused) == 6 and len(sleeps) == 3


def test_load_ignores_a_file_of_another_version_or_a_broken_one(tmp_path: Path) -> None:
    assert student.load(tmp_path) is None
    good = {"version": 1, "package": "x", "scenes": [{"chapterId": 1}]}
    (tmp_path / student.FILE).write_text(json.dumps(good), encoding="utf-8")
    assert student.load(tmp_path) == good
    for changed in ({"version": 2}, {"scenes": None}):
        (tmp_path / student.FILE).write_text(json.dumps({**good, **changed}), encoding="utf-8")
        assert student.load(tmp_path) is None, changed
    (tmp_path / student.FILE).write_text("{hỏng", encoding="utf-8")
    assert student.load(tmp_path) is None


# ---- kiểu số CPU ------------------------------------------------------------------------------------------------------------------
def _embedder_with_timings(package: Path, monkeypatch: pytest.MonkeyPatch, timings: list[float]) -> tuple[Any, list[int]]:
    measured: list[int] = []

    def fake_time(this: Any, ids: Any) -> float:
        measured.append(ids.shape[1])
        return timings[len(measured) - 1]

    monkeypatch.setattr(student._Embedder, "_time_forward", fake_time)
    embedder = student._Embedder(package, student.Head(package / student.HEAD_FILE), "w1 w2 w3")
    return embedder, measured


def test_the_cpu_dtype_is_measured_once_remembered_and_measured_again_for_another_torch(package: Path,
                                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    (package / student.CPU_DTYPE_FILE).unlink()
    embedder, measured = _embedder_with_timings(package, monkeypatch, [0.5, 0.2])  # bf16 chậm hơn fp32 (CPU không có lệnh bf16)
    assert measured == [student.BENCH_TOKENS] * 2, "đo cùng một khúc ở hai kiểu"
    assert embedder.model.embed_tokens.weight.dtype == torch.float32
    assert json.loads((package / student.CPU_DTYPE_FILE).read_text(encoding="utf-8")) == {"dtype": "fp32", "torch": torch.__version__}
    embedder.close()
    # Đã nhớ: không đo, nạp thẳng kiểu đã chọn.
    embedder, measured = _embedder_with_timings(package, monkeypatch, [])
    assert measured == [] and embedder.model.embed_tokens.weight.dtype == torch.float32
    embedder.close()
    # Đổi phiên bản torch: đo lại; lần này bf16 nhanh hơn -> giữ bf16 và ghi lại.
    monkeypatch.setattr(torch, "__version__", "0.0.1+test")
    embedder, measured = _embedder_with_timings(package, monkeypatch, [0.1, 0.4])
    assert len(measured) == 2 and embedder.model.embed_tokens.weight.dtype == torch.bfloat16
    assert json.loads((package / student.CPU_DTYPE_FILE).read_text(encoding="utf-8")) == {"dtype": "bf16", "torch": "0.0.1+test"}
    embedder.close()


def test_a_broken_dtype_note_counts_as_not_measured(tmp_path: Path) -> None:
    assert student.read_cpu_dtype(tmp_path, "1") is None
    (tmp_path / student.CPU_DTYPE_FILE).write_text(json.dumps({"dtype": "int4", "torch": "1"}), encoding="utf-8")
    assert student.read_cpu_dtype(tmp_path, "1") is None
    (tmp_path / student.CPU_DTYPE_FILE).write_text("{hỏng", encoding="utf-8")
    assert student.read_cpu_dtype(tmp_path, "1") is None


# ---- không có gói / lỗi -----------------------------------------------------------------------------------------------------------
def _run(root: Path) -> tuple[list[str], list[tuple[str, dict]]]:
    lines: list[str] = []
    events: list[tuple[str, dict]] = []
    student.run_after_analysis(root, lambda: False, lines.append, lambda kind, payload: events.append((kind, payload)))
    return lines, events


def test_without_a_package_nothing_runs_and_nothing_is_invented(book: list[dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(student.ENV_DIR, raising=False)
    monkeypatch.setattr(student, "_directory", None)
    assert not student.available() and student.package_sha() == ""
    assert _run(tmp_path) == ([], []) and student.load(tmp_path) is None


def test_without_torch_the_student_is_not_available(package: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert student.available()
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "torch" else real(name, *a))
    assert not student.available()
    (package / student.HEAD_FILE).unlink()
    monkeypatch.setattr(importlib.util, "find_spec", real)
    assert not student.available(), "thiếu file gói"


def test_any_failure_becomes_one_log_line_and_never_raises(package: Path, book: list[dict], tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("không đủ RAM")

    monkeypatch.setattr(student._Embedder, "__init__", broken)
    lines, events = _run(tmp_path)
    assert len(lines) == 1 and "không đủ RAM" in lines[0] and events == []
    assert student.load(tmp_path) is None, "lỗi thì không có kết quả: nhạc chạy đường hôm nay"


def test_a_broken_package_file_is_one_log_line_too(package: Path, book: list[dict], tmp_path: Path) -> None:
    (package / "model.safetensors").write_bytes(b"khong phai safetensors")
    lines, events = _run(tmp_path)
    assert len(lines) == 1 and events == []


def test_the_hook_runs_the_whole_book_and_reports(package: Path, book: list[dict], tmp_path: Path) -> None:
    lines, events = _run(tmp_path)
    assert events == [("music_scene_student_done", {"embedded": 6})] and len(student.load(tmp_path)["scenes"]) == 6
    assert lines and all("Lỗi" not in line and "Bỏ qua" not in line for line in lines)


def test_the_hook_skips_a_book_with_its_music_turned_off(package: Path, book: list[dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / music_plan.OVERRIDES_FILE).write_text(json.dumps({"enabled": False}), encoding="utf-8")
    spy = Spy(monkeypatch)
    assert _run(tmp_path) == ([], []) and spy.loads == 0 and student.load(tmp_path) is None


def test_the_worker_hook_runs_the_student_even_when_the_llm_part_fails(package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abook import worker
    from abook.webui import music_moods

    calls: list[str] = []
    monkeypatch.setattr(music_moods, "run_after_analysis", lambda *_a, **_k: (_ for _ in ()).throw(ConnectionError("Ollama chết")))
    monkeypatch.setattr(student, "run_after_analysis", lambda *_a, **_k: calls.append("student"))
    with pytest.raises(ConnectionError):  # lỗi của LLM vẫn tới dây chuyền (ghi music_moods_skipped), sau khi học sinh đã chạy
        worker.run_music_after_analysis(tmp_path, "http://x", lambda: False, lambda _line: None, lambda *_args: None, pause_requested=lambda: False)
    assert calls == ["student"]
    monkeypatch.setattr(music_moods, "run_after_analysis", lambda *_a, **_k: calls.append("moods"))
    worker.run_music_after_analysis(tmp_path, "http://x", lambda: False, lambda _line: None, lambda *_args: None, pause_requested=lambda: False)
    assert calls == ["student", "moods", "student"]


# ---- áp vào đoạn --------------------------------------------------------------------------------------------------------------------
def _scene(start: float, end: float, label_v: float, label_t: float, first: int, last: int, *, p_v: float | None = None,
           p_t: float | None = None) -> dict:
    """Đoạn ngay từ `_view` (chưa qua mức chương). Có P0 (p_v, p_t) thì valence / tension là của P0 và moodSource "llm"; không thì đường nhãn."""
    llm = p_v is not None
    return {"chapterId": 7, "firstSegment": first, "lastSegment": last, "start": start, "end": end,
            "valence": p_v if llm else label_v, "arousal": 0.25, "tension": p_t if llm else label_t,
            "moodSource": "llm" if llm else "labels", "labelValence": label_v, "labelTension": label_t, "emotions": {"joy": 0.5}}


def _item(first: int, last: int, d_v: float, d_e: float, d_t: float, chapter: int = 7) -> dict:
    return {"chapterId": chapter, "firstSegment": first, "lastSegment": last, "dV": d_v, "dE": d_e, "dT": d_t}


# Ba đoạn 60 / 120 / 60 giây (w = 60, 120, 60; tổng 240). Nhãn V = .2 / 0 / -.2 nên TB = 0 và L_V = .068. dV = .3 / 0 / -.2 -> TB = .025.
# dT = .1 / -.2 / .4 -> TB = .025. Độ lệch căn giữa lại: dV - TB = .275 / -.025 / -.225, dT - TB = .075 / -.225 / .375.
ITEMS = [_item(1, 10, 0.3, -0.1, 0.1), _item(11, 20, 0.0, 0.2, -0.2), _item(21, 30, -0.2, -0.1, 0.4)]
VALENCE = [pytest.approx(0.068 + 0.275, abs=6e-4), pytest.approx(0.068 - 0.025, abs=6e-4), pytest.approx(0.068 - 0.225, abs=6e-4)]


def test_apply_student_with_p0_on_every_scene_takes_the_t_level_from_p0_with_numbers_worked_by_hand() -> None:
    # P0 chấm T = .8 / .6 / .4 -> TB = (48 + 72 + 24) / 240 = .6 -> L_T = 1.066 * .6 - .49 = .1496. Hình đầy đủ (k = 1, không nhân .5).
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10, p_v=0.5, p_t=0.8), _scene(60, 180, 0.0, 0.2, 11, 20, p_v=0.1, p_t=0.6),
              _scene(180, 240, -0.2, 0.0, 21, 30, p_v=-0.3, p_t=0.4)]
    before = copy.deepcopy(scenes)
    got = music_scenes.apply_student(scenes, ITEMS)
    assert scenes == before, "thuần hàm: không sửa đoạn đưa vào"
    assert [s["valence"] for s in got] == VALENCE
    assert [s["tension"] for s in got] == [pytest.approx(0.1496 + 0.075, abs=6e-4), pytest.approx(0.1496 - 0.225, abs=6e-4),
                                           pytest.approx(0.1496 + 0.375, abs=6e-4)]
    assert all(s["moodSource"] == "student" for s in got)
    assert [(s["studentValence"], s["studentArousal"], s["studentTension"]) for s in got] == [(0.3, -0.1, 0.1), (0.0, 0.2, -0.2),
                                                                                         (-0.2, -0.1, 0.4)], "độ lệch thô"
    assert [(s["llmValence"], s["llmTension"]) for s in got] == [(0.5, 0.8), (0.1, 0.6), (-0.3, 0.4)], "giữ giá trị P0 để so"
    # arousal: mức = TB nhãn .25 (mọi đoạn .25); dE = -.1 / .2 / -.1 -> TB = (-6 + 24 - 6) / 240 = .05 -> .25 - .15 / .25 + .15 / .25 - .15
    assert [s["arousal"] for s in got] == [pytest.approx(0.1, abs=6e-4), pytest.approx(0.4, abs=6e-4), pytest.approx(0.1, abs=6e-4)]
    for field in ("labelValence", "labelTension", "emotions", "start", "end", "firstSegment", "lastSegment"):
        assert [s[field] for s in got] == [s[field] for s in scenes], field


def test_apply_student_takes_the_energy_shape_from_the_student_around_the_label_level_with_numbers_worked_by_hand() -> None:
    # Q06-E (Corpus PLAN_q06_e.md): mức E giữ TB nhãn câu theo thời lượng, hình E từ dE. Nhãn arousal .6 / 0 / .2 -> TB = (36 + 0 + 12) / 240
    # = .2; dE - TB = -.15 / .15 / -.15 -> .05 / .35 / .05. Có P0 hay không thì E cũng vậy (P0 không chấm E).
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    for scene, arousal in zip(scenes, (0.6, 0.0, 0.2)):
        scene["arousal"] = arousal
    got = music_scenes.apply_student(scenes, ITEMS)
    assert [s["arousal"] for s in got] == [pytest.approx(0.05, abs=6e-4), pytest.approx(0.35, abs=6e-4), pytest.approx(0.05, abs=6e-4)]
    hot = [dict(scene, arousal=0.95) for scene in scenes]
    assert max(s["arousal"] for s in music_scenes.apply_student(hot, ITEMS)) == 1.0, "kẹp về thang [-1, 1]"


def test_apply_student_without_p0_on_every_scene_takes_the_t_level_from_the_labels_with_numbers_worked_by_hand() -> None:
    # Đoạn giữa chưa có P0 -> L_T = 4.022 * TB(nhãn T) - .056. Nhãn T = .1 / .2 / 0 -> TB = (6 + 24 + 0) / 240 = .125 -> L_T = .44675.
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10, p_v=0.5, p_t=0.8), _scene(60, 180, 0.0, 0.2, 11, 20),
              _scene(180, 240, -0.2, 0.0, 21, 30, p_v=-0.3, p_t=0.4)]
    got = music_scenes.apply_student(scenes, ITEMS)
    assert [s["valence"] for s in got] == VALENCE, "mức V luôn từ nhãn câu"
    assert [s["tension"] for s in got] == [pytest.approx(0.44675 + 0.075, abs=6e-4), pytest.approx(0.44675 - 0.225, abs=6e-4),
                                           pytest.approx(0.44675 + 0.375, abs=6e-4)]
    assert all(s["moodSource"] == "student" for s in got)
    assert ["llmValence" in s for s in got] == [True, False, True] and ["llmTension" in s for s in got] == [True, False, True], "P0 chỉ ở đoạn có"
    assert (got[0]["llmValence"], got[0]["llmTension"], got[2]["llmValence"], got[2]["llmTension"]) == (0.5, 0.8, -0.3, 0.4)
    labels = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    assert [s["tension"] for s in music_scenes.apply_student(labels, ITEMS)] == [s["tension"] for s in got], "không P0 nào: cùng mức"
    assert not any("llmValence" in s or "llmTension" in s for s in music_scenes.apply_student(labels, ITEMS))


def _with_level(items: list[dict], level: float) -> list[dict]:
    return [dict(item, chapterV=level) for item in items]


def test_apply_student_takes_the_v_level_from_the_chapter_head_with_numbers_worked_by_hand() -> None:
    # chapterV = .25 thay L_V = .068 (từ nhãn); hình V vẫn dV - TB(dV) = .275 / -.025 / -.225 -> .525 / .225 / .025.
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10, p_v=0.5, p_t=0.8), _scene(60, 180, 0.0, 0.2, 11, 20, p_v=0.1, p_t=0.6),
              _scene(180, 240, -0.2, 0.0, 21, 30, p_v=-0.3, p_t=0.4)]
    items = _with_level(ITEMS, 0.25)
    before = copy.deepcopy(items)
    got = music_scenes.apply_student(scenes, items)
    assert items == before
    assert [s["valence"] for s in got] == [pytest.approx(0.525, abs=6e-4), pytest.approx(0.225, abs=6e-4), pytest.approx(0.025, abs=6e-4)]
    # Mức T giữ nguyên: P0 đủ -> L_T = .1496 như khi chưa có chapterV, không đổi theo chapterV.
    assert [s["tension"] for s in got] == [pytest.approx(0.1496 + 0.075, abs=6e-4), pytest.approx(0.1496 - 0.225, abs=6e-4),
                                           pytest.approx(0.1496 + 0.375, abs=6e-4)]
    assert [s["tension"] for s in got] == [s["tension"] for s in music_scenes.apply_student(scenes, ITEMS)]
    assert all(s["levelSource"] == {"V": "student", "T": "p0"} and s["moodSource"] == "student" for s in got)
    assert [s["arousal"] for s in got] == [s["arousal"] for s in music_scenes.apply_student(scenes, ITEMS)], "mức E không đổi"


def test_apply_student_takes_the_v_level_from_the_chapter_head_and_the_t_level_from_the_labels_without_p0() -> None:
    # Không P0: L_T = .44675 (nhãn) như cũ; chapterV = -.4 -> V = -.125 / -.425 / -.625. Mức T không đổi theo chapterV.
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    got = music_scenes.apply_student(scenes, _with_level(ITEMS, -0.4))
    assert [s["valence"] for s in got] == [pytest.approx(-0.125, abs=6e-4), pytest.approx(-0.425, abs=6e-4), pytest.approx(-0.625, abs=6e-4)]
    assert [s["tension"] for s in got] == [pytest.approx(0.44675 + 0.075, abs=6e-4), pytest.approx(0.44675 - 0.225, abs=6e-4),
                                           pytest.approx(0.44675 + 0.375, abs=6e-4)]
    assert all(s["levelSource"] == {"V": "student", "T": "labels"} for s in got)
    other = music_scenes.apply_student(scenes, _with_level(ITEMS, 0.6))
    assert [s["tension"] for s in other] == [s["tension"] for s in got], "T không phụ thuộc chapterV"


def test_apply_student_clips_the_chapter_level_and_a_one_scene_chapter_sits_at_it() -> None:
    scenes = [_scene(0, 60, 0.0, 0.1, 1, 10), _scene(60, 120, 0.0, 0.1, 11, 20)]
    got = music_scenes.apply_student(scenes, _with_level([_item(1, 10, 0.3, 0, 0), _item(11, 20, -0.3, 0, 0)], 1.4))  # kẹp 1 -> 1.3 / .7
    assert [s["valence"] for s in got] == [1.0, pytest.approx(0.7)]
    got, = music_scenes.apply_student([_scene(0, 90, 0.3, 0.1, 1, 10)], _with_level([_item(1, 10, 0.0, 0.0, 0.0)], -1.7))
    assert got["valence"] == -1.0 and got["levelSource"] == {"V": "student", "T": "labels"}
    got, = music_scenes.apply_student([_scene(0, 90, 0.3, 0.1, 1, 10)], _with_level([_item(1, 10, 0.0, 0.0, 0.0)], 0.2))
    assert got["valence"] == 0.2, "một đoạn: đúng mức chương, không phụ thuộc nhãn"


def test_apply_student_falls_back_to_the_label_level_without_a_usable_chapter_level() -> None:
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 180, 0.0, 0.2, 11, 20), _scene(180, 240, -0.2, 0.0, 21, 30)]
    labels = music_scenes.apply_student(scenes, ITEMS)
    assert [s["valence"] for s in labels] == VALENCE and all(s["levelSource"] == {"V": "labels", "T": "labels"} for s in labels)
    for odd in (None, "x", float("nan"), float("inf")):
        got = music_scenes.apply_student(scenes, [dict(ITEMS[0], chapterV=odd), *ITEMS[1:]])
        assert [s["valence"] for s in got] == [s["valence"] for s in labels] and got[0]["levelSource"]["V"] == "labels", odd
    partial = music_scenes.apply_student(scenes, [dict(ITEMS[0], chapterV=0.25), *ITEMS[1:]])
    assert partial[0]["levelSource"]["V"] == "labels", "thiếu ở một đoạn: cả chương về nhãn"


def test_apply_student_clips_to_the_scale_and_keeps_a_one_scene_chapter_at_the_level() -> None:
    hot = [_scene(0, 60, 0.0, 0.5, 1, 10), _scene(60, 120, 0.0, 0.5, 11, 20)]  # L_T = 4.022 * .5 - .056 = 1.955 -> kẹp 1
    got = music_scenes.apply_student(hot, [_item(1, 10, 0, 0, 0.3), _item(11, 20, 0, 0, -0.3)])
    assert [s["tension"] for s in got] == [1.0, pytest.approx(0.7)]
    # Một đoạn: độ lệch 0 -> đoạn = mức chương: L_V = 1.876 * .3 + .068 = .6308, L_T = 4.022 * .1 - .056 = .3462.
    got, = music_scenes.apply_student([_scene(0, 90, 0.3, 0.1, 1, 10)], [_item(1, 10, 0.0, 0.0, 0.0)])
    assert (got["valence"], got["tension"], got["arousal"]) == (0.631, 0.346, 0.25) and got["moodSource"] == "student"


def test_apply_student_gives_up_when_any_scene_has_no_item() -> None:
    scenes = [_scene(0, 60, 0.2, 0.1, 1, 10), _scene(60, 120, 0.1, 0.2, 11, 20)]
    before = copy.deepcopy(scenes)
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1)]) is None
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), _item(11, 19, 0.1, 0.1, 0.1)]) is None, "ranh giới khác thì không khớp"
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), _item(11, 20, 0.1, 0.1, 0.1, chapter=8)]) is None
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), {**_item(11, 20, 0.0, 0.0, 0.0), "dV": "hỏng"}]) is None
    assert music_scenes.apply_student(scenes, None) is None and music_scenes.apply_student(scenes, []) is None
    assert music_scenes.apply_student([], [_item(1, 10, 0, 0, 0)]) is None and scenes == before


def test_chapter_scenes_takes_the_shape_from_the_student_and_falls_back_to_the_chapter_level(book: list[dict]) -> None:
    script = book[0]
    plain = music_scenes.chapter_scenes(script)
    items = [_item(s["firstSegment"], s["lastSegment"], d, -d, d / 2, chapter=1) for s, d in zip(plain, (0.2, -0.1, -0.1))]
    moods = [{"chapterId": 1, "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"], "V": v, "E": 0.0, "T": t}
             for s, v, t in zip(plain, (2.0, 0.0, -2.0), (1.0, 0.0, -1.0))]
    level = music_scenes.chapter_scenes(script, moods)
    assert [s["moodSource"] for s in level] == ["chapter"] * 3
    got = music_scenes.chapter_scenes(script, moods, student=items)
    assert [s["moodSource"] for s in got] == ["student"] * 3
    weights = [s["end"] - s["start"] for s in plain]
    mean = lambda values: sum(w * v for w, v in zip(weights, values)) / sum(weights)  # noqa: E731
    centred = lambda key: [item[key] - mean([i[key] for i in items]) for item in items]  # noqa: E731
    level_v = max(-1.0, min(1.0, 1.876 * mean([s["valence"] for s in plain]) + 0.068))  # nhãn V = valence đường nhãn
    level_t = 1.066 * mean([s["llmTension"] for s in level]) - 0.49  # đủ P0: mức T từ P0
    assert [s["valence"] for s in got] == [pytest.approx(level_v + d, abs=2e-3) for d in centred("dV")]
    assert [s["tension"] for s in got] == [pytest.approx(max(-1.0, min(1.0, level_t + d)), abs=2e-3) for d in centred("dT")]
    assert [(s["llmValence"], s["llmTension"]) for s in got] == [(s["llmValence"], s["llmTension"]) for s in level]
    assert [(s["studentValence"], s["studentTension"]) for s in got] == [(i["dV"], i["dT"]) for i in items]
    level_e = mean([s["arousal"] for s in plain])  # mức E = TB nhãn câu, hình E từ dE (Q06-E)
    assert [s["arousal"] for s in got] == [pytest.approx(max(-1.0, min(1.0, level_e + d)), abs=2e-3) for d in centred("dE")]
    assert [s["studentArousal"] for s in got] == [i["dE"] for i in items]
    for field in ("start", "end", "firstSegment", "lastSegment", "reason", "lines", "sd", "emotions", "confidence"):
        assert [s[field] for s in got] == [s[field] for s in level], field  # ranh giới, chữ không đổi
    # Không có LLM: học sinh vẫn chạy, mức T từ nhãn.
    no_llm = music_scenes.chapter_scenes(script, None, None, items)
    assert [s["moodSource"] for s in no_llm] == ["student"] * 3
    level_t_labels = 4.022 * mean([s["labelTension"] for s in no_llm]) - 0.056
    assert [s["tension"] for s in no_llm] == [pytest.approx(max(-1.0, min(1.0, level_t_labels + d)), abs=2e-3) for d in centred("dT")]
    # Thiếu mục ở một đoạn của chương: đường hôm nay (mức chương của P0 / nhãn).
    assert music_scenes.chapter_scenes(script, moods, student=items[:2]) == level
    assert music_scenes.chapter_scenes(script, None, None, items[:2]) == plain
    everything = music_scenes.book_scenes(book, moods, student=items)  # chương 2 không có mục nào (và không có LLM): đường nhãn
    assert everything[:3] == got and {s["moodSource"] for s in everything[3:]} == {"labels"}


def test_the_plan_is_built_from_the_students_file(package: Path, book: list[dict], tmp_path: Path) -> None:
    project = tmp_path / "project"
    _compute(project)
    saved = student.load(project)
    scenes = music_scenes.book_scenes(book, student=saved["scenes"])
    assert len(scenes) == 6 and {s["moodSource"] for s in scenes} == {"student"}
    assert [s["valence"] for s in scenes] != [s["valence"] for s in music_scenes.book_scenes(book)]
    assert {s["levelSource"]["V"] for s in scenes} == {"student"}
    for chapter_id in (1, 2):
        mine = [s for s in scenes if s["chapterId"] == chapter_id]
        level = next(i["chapterV"] for i in saved["scenes"] if i["chapterId"] == chapter_id)
        total = sum(s["end"] - s["start"] for s in mine)
        shape_mean = sum((s["end"] - s["start"]) * s["studentValence"] for s in mine) / total
        assert all(s["valence"] == pytest.approx(max(-1.0, min(1.0, max(-1.0, min(1.0, level)) + s["studentValence"] - shape_mean)), abs=2e-3) for s in mine)


# ---- công thức đầu giữ cứng (luôn chạy, không cần model) ------------------------------------------------------------------------------
def test_the_head_formula_is_pinned_with_a_fake_package_and_fixed_embeddings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gói giả: đủ file tên thật nhưng nội dung giả, đầu hồi quy 2 chiều viết tay, nhúng giả cố định theo chữ đầu của đoạn. Ba đoạn nặng 37 / 37 / 74 chữ (dòng ngăn "***" tính một chữ vào đoạn trước nó; đoạn cuối có thêm hai chữ).
    x = [1, 0], [0, 1], [2, 2]: TB theo chữ = [1.25, 1.25] -> căn giữa [-.25, -1.25], [-1.25, -.25], [.75, .75]; trừ mu = [.25, -.25] rồi chia sd = [.5, 2]
    -> z = (-1, -.5), (-3, 0), (1, .5); nhân coef [[1, 2, 0], [2, 0, 1]], cộng intercept [.1, 0, -.1]."""
    directory = tmp_path / "package"
    directory.mkdir()
    for file in student.REQUIRED_FILES:
        (directory / file).write_bytes(b"gia")
    # Đầu mức chương viết tay: TB nhúng theo chữ = (37 [1,0] + 37 [0,1] + 74 [2,2]) / 148 = [1.25, 1.25]; trừ mu [.25, .25] rồi chia sd [.5, 2] -> z = (2, .5);
    # V = 2 * 1 + .5 * 2 + .1 = 3.1 (chưa kẹp; apply_student kẹp), T = 2 * .5 - .5 * 1 + .2 = .7 (app không dùng).
    np.savez(directory / student.CHAPTER_HEAD_FILE, mu=np.array([0.25, 0.25]), sd=np.array([0.5, 2.0]), coef=np.array([[1.0, 0.5], [2.0, -1.0]]),
             intercept=np.array([0.1, 0.2]), axes=np.array(["V", "T"]), alpha=1000.0)
    np.savez(directory / student.HEAD_FILE, mu=np.array([0.25, -0.25]), sd=np.array([0.5, 2.0]), coef=np.array([[1.0, 2.0, 0.0], [2.0, 0.0, 1.0]]),
             intercept=np.array([0.1, 0.0, -0.1]), layer=1, maxTokens=8)
    monkeypatch.setenv(student.ENV_DIR, str(directory))
    vectors = {"w1": [1.0, 0.0], "w4": [0.0, 1.0], "w7": [2.0, 2.0]}

    class FakeEmbedder:
        def __init__(self, _directory: Path, _head: Any, _sample: str) -> None:
            pass

        def embed(self, text: str) -> Any:
            return np.array(vectors[text.split()[0]], dtype=np.float32)

        def close(self) -> None:
            pass

    monkeypatch.setattr(student, "_Embedder", FakeEmbedder)
    segments, clock = [], 0.0
    for block, (first_word, sentences) in enumerate(((1, 12), (4, 12), (7, 24))):
        if block:
            segments.append({"id": len(segments) + 1, "text": "***", "kind": "narration", "emotion": "neutral", "intensity": 0,
                             "start": clock, "end": clock + 1.0})
            clock += 1.4
        for number in range(sentences):
            extra = " w0 w0" if block == 2 and number == 0 else ""
            segments.append({"id": len(segments) + 1, "kind": "narration", "emotion": "neutral", "intensity": 0,
                             "text": f"w{first_word} w{first_word + 1} w{first_word + 2}{extra}", "start": clock, "end": clock + 6.0})
            clock += 6.4
    monkeypatch.setattr(music_plan, "book_scripts", lambda _root: iter([{"chapterId": 3, "segments": segments}]))
    assert _compute(tmp_path / "project") == 3
    items = student.load(tmp_path / "project")["scenes"]
    assert [(i["dV"], i["dE"], i["dT"]) for i in items] == [(-1.9, -2.0, -0.6), (-2.9, -6.0, -0.1), (2.1, 2.0, 0.4)]
    assert [i["chapterV"] for i in items] == [3.1, 3.1, 3.1]
    head = student.ChapterHead(directory / student.CHAPTER_HEAD_FILE)
    assert head.level([[1.0, 0.0], [0.0, 1.0], [2.0, 2.0]], [37, 37, 74]).tolist() == pytest.approx([3.1, 0.7])


# ---- bộ ví dụ cố định với gói thật ------------------------------------------------------------------------------------------------------
GOLDEN = Path(__file__).parent / "fixtures" / "music_scene_q06_golden.json"


def test_the_golden_fixture_matches_the_pin_the_app_carries() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["chapterHeadRevision"] == student.REVISION, "bộ ví dụ mức chương làm ở đúng bản gói app mang"
    assert golden["headSha256"] == student.PACKAGE_HASHES[student.HEAD_FILE][0]
    assert golden["modelSha256"] == student.PACKAGE_HASHES["model.safetensors"][0]


def _golden_deviations(directory: Path, dtype: str, monkeypatch: pytest.MonkeyPatch) -> tuple[list[list[float]], list[list[float]]]:
    """(tính được, mong đợi) của mọi đoạn mọi chương, qua ĐÚNG đường nhúng + Head.deviations của mô-đun. Kiểu số ép sẵn, không ghi gì vào gói."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    monkeypatch.setattr(student, "read_cpu_dtype", lambda *_args: dtype)
    monkeypatch.setattr(student, "remember_cpu_dtype", lambda *_args: None)
    head = student.Head(directory / student.HEAD_FILE)
    embedder = student._Embedder(directory, head, "")
    got, expected = [], []
    try:
        for chapter in golden["chapters"]:
            scenes = chapter["scenes"]
            vectors = [embedder.embed("\n".join(scene["sentences"])) for scene in scenes]
            got += head.deviations(vectors, [scene["words"] for scene in scenes]).tolist()
            expected += [scene["expected"] for scene in scenes]
    finally:
        embedder.close()
    return got, expected


def _golden_chapter_levels(directory: Path, dtype: str, monkeypatch: pytest.MonkeyPatch) -> tuple[list[list[float]], list[list[float]]]:
    """(tính được, mong đợi) (V, T) thô của từng chương, qua đường nhúng + `ChapterHead.level` (TB nhúng theo số chữ) của mô-đun."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    monkeypatch.setattr(student, "read_cpu_dtype", lambda *_args: dtype)
    monkeypatch.setattr(student, "remember_cpu_dtype", lambda *_args: None)
    chapter_head = student.ChapterHead(directory / student.CHAPTER_HEAD_FILE)
    embedder = student._Embedder(directory, student.Head(directory / student.HEAD_FILE), "")
    got, expected = [], []
    try:
        for chapter in golden["chapters"]:
            scenes = chapter["scenes"]
            vectors = [embedder.embed("\n".join(scene["sentences"])) for scene in scenes]
            got.append(chapter_head.level(vectors, [scene["words"] for scene in scenes]).tolist())
            expected.append(chapter["expectedChapterLevel"])
    finally:
        embedder.close()
    return got, expected


def _real_package() -> Path:
    where = os.environ.get(student.ENV_DIR)
    if not where:
        pytest.skip(f"đặt {student.ENV_DIR} trỏ tới gói q06 thật (vd D:/Novels/LLM_Train/music/pkg_scene_q06) để chạy bộ ví dụ cố định")
    directory = Path(where)
    if not student._complete(directory) or not (directory / student.CHAPTER_HEAD_FILE).is_file():
        pytest.skip(f"{student.ENV_DIR}={where} chưa đủ file gói q06")
    return directory


def test_the_real_package_reproduces_the_golden_deviations_in_fp32(monkeypatch: pytest.MonkeyPatch) -> None:
    got, expected = _golden_deviations(_real_package(), "fp32", monkeypatch)
    assert len(got) == len(expected) >= 6
    worst = float(np.abs(np.array(got) - np.array(expected)).max())
    print(f"golden fp32: max abs deviation {worst:.3e}")
    assert worst < json.loads(GOLDEN.read_text(encoding="utf-8"))["tolerance"]["fp32_max_abs"]


def test_the_real_package_in_bf16_still_follows_the_golden_deviations(monkeypatch: pytest.MonkeyPatch) -> None:
    got, expected = _golden_deviations(_real_package(), "bf16", monkeypatch)
    floor = json.loads(GOLDEN.read_text(encoding="utf-8"))["tolerance"]["bf16_min_corr"]
    corr = [float(np.corrcoef(np.array(got)[:, axis], np.array(expected)[:, axis])[0, 1]) for axis in range(3)]
    print(f"golden bf16: corr V/E/T {corr}")
    assert min(corr) >= floor, corr


def test_the_real_package_reproduces_the_golden_chapter_level_in_fp32(monkeypatch: pytest.MonkeyPatch) -> None:
    got, expected = _golden_chapter_levels(_real_package(), "fp32", monkeypatch)
    assert len(got) == len(expected) >= 2
    worst = float(np.abs(np.array(got) - np.array(expected)).max())
    print(f"golden chapter level fp32: max abs deviation {worst:.3e}")
    assert worst < 1e-5


def test_the_real_package_in_bf16_keeps_the_golden_chapter_level_within_five_thousandths(monkeypatch: pytest.MonkeyPatch) -> None:
    got, expected = _golden_chapter_levels(_real_package(), "bf16", monkeypatch)
    worst = float(np.abs(np.array(got) - np.array(expected)).max())
    print(f"golden chapter level bf16: max abs deviation {worst:.3e}")
    assert worst < 5e-3


# ---- gói tải theo yêu cầu --------------------------------------------------------------------------------------------------------------
def test_the_optional_download_part_is_pinned_to_the_published_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(student.ENV_DIR, raising=False)
    monkeypatch.delenv(student.ENV_DOWNLOAD, raising=False)
    part = music_module.scene_student_part()
    assert part.id == "scene_q06" and part.label == "Học sinh không khí cảnh" and part.blocked == ""
    assert [d.name for d in part.downloads] == list(student.PACKAGE_FILES) == ["config.json", "model.safetensors", "tokenizer.json",
                                                                              "tokenizer_config.json", "LICENSE", "scene_head_q06.npz",
                                                                              "chapter_head_q06.npz"]
    assert part.downloads[1].url == ("https://huggingface.co/NGDtuanh/abook-music-student/resolve/182d945e4129165f2be9e69b50be919eb1078d63/"
                                      "scene_q06/model.safetensors")
    assert student.PACKAGE_HASHES["chapter_head_q06.npz"] == ("63b5c7d3f2e21796cec7307630bd6ba39b585f684f86e6c2b73e73467833c858", 17874)
    assert student.REQUIRED_FILES == tuple(student.PACKAGE_FILES[:-1]), "đầu mức chương là phần thêm, không bắt buộc"
    assert part.downloads[1].sha256 == "7005be7da7f28271f15f0102ecefe19da6b80b0af6b5ba9477e278ed8430c2d1" and part.size == student.total_bytes()
    assert 0.70 < part.size / 2 ** 30 < 0.72, "0,71 GiB"
    assert "scene_q06" not in [component.id for component in music_module._components()], "tuỳ chọn: không đòi người dùng tải"
    assert "scene_q06" in [component.id for component in music_module._components(scene=True)]
    monkeypatch.setenv(student.ENV_DOWNLOAD, "0")
    assert "đang bị tắt" in student.cannot_download()


def test_the_download_urls_follow_the_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(student, "REVISION", "abc123")
    monkeypatch.delenv(student.ENV_DIR, raising=False)
    assert student.model_downloads()[1].url == "https://huggingface.co/NGDtuanh/abook-music-student/resolve/abc123/scene_q06/model.safetensors"
    pin = student.model_pin()
    monkeypatch.setattr(student, "REVISION", "def456")
    assert student.model_pin() != pin
    monkeypatch.setattr(student, "REVISION", "")
    assert student.model_downloads() == [] and student.cannot_download() == "chưa có bản model để tải"


# ---- chạy bằng Python của Studio (tiến trình server của bản cài không có torch) -----------------------------------------------------------
class _FakeProcess:
    def __init__(self, lines: list[str], code: int) -> None:
        self.stdout, self._code = iter(lines), code

    def wait(self) -> int:
        return self._code


def _studio_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, lines: list[str], code: int, enabled: bool = True) -> tuple[bool, list[str], list[dict]]:
    package = tmp_path / "package"
    package.mkdir(exist_ok=True)
    for file in student.PACKAGE_FILES:
        (package / file).write_bytes(b"gia")
    if not enabled:
        (tmp_path / music_plan.OVERRIDES_FILE).write_text(json.dumps({"enabled": False}), encoding="utf-8")
    spawned: list[dict] = []

    def fake_popen(command: list[str], **kwargs: Any) -> _FakeProcess:
        spawned.append({"command": command, **kwargs})
        return _FakeProcess(lines, code)

    monkeypatch.setattr(student.subprocess, "Popen", fake_popen)
    logged: list[str] = []
    ok = student.run_in_studio(tmp_path, "C:/Studio/venv/Scripts/python.exe", "C:/Studio/code/abc", {"PYTHONPATH": "C:/Studio/code/abc", "ABOOK_RUNTIME": "R"},
                               logged.append, package=package)
    return ok, logged, spawned


def test_the_studio_child_runs_the_module_with_the_studio_python_from_the_code_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ok, logged, spawned = _studio_run(tmp_path, monkeypatch, lines=["Hình không khí trong chương: xong chương 1 (3 đoạn)\n"], code=0)
    assert ok and len(spawned) == 1 and logged == ["Hình không khí trong chương: xong chương 1 (3 đoạn)"]
    call = spawned[0]
    assert call["command"] == ["C:/Studio/venv/Scripts/python.exe", "-m", "abook.webui.music_scene_student", str(tmp_path), "--package", str(tmp_path / "package")]
    assert call["cwd"] == "C:/Studio/code/abc", "chạy từ thư mục mã (python -m ưu tiên thư mục làm việc hơn PYTHONPATH)"
    assert call["env"]["PYTHONPATH"] == "C:/Studio/code/abc" and call["env"]["ABOOK_RUNTIME"] == "R" and call["env"]["PYTHONIOENCODING"] == "utf-8"
    assert call["stdout"] == student.subprocess.PIPE and call["stderr"] == student.subprocess.STDOUT
    if os.name == "nt":
        assert call["creationflags"] == student.subprocess.CREATE_NO_WINDOW, "không hiện cửa sổ"


def test_a_failing_studio_child_is_one_log_line_and_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ok, logged, _spawned = _studio_run(tmp_path, monkeypatch, lines=["Bỏ qua: hết RAM\n"], code=3)
    assert not ok and len(logged) == 2 and "mã 3" in logged[1] and "hết RAM" in logged[1]
    monkeypatch.setattr(student.subprocess, "Popen", lambda *_a, **_k: (_ for _ in ()).throw(OSError("không có python")))
    lines: list[str] = []
    assert student.run_in_studio(tmp_path, "x", "y", {}, lines.append, package=tmp_path / "package") is False
    assert len(lines) == 1 and "OSError" in lines[0]


def test_the_studio_child_is_not_started_without_a_package_or_with_the_books_music_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ok, logged, spawned = _studio_run(tmp_path, monkeypatch, lines=[], code=0, enabled=False)
    assert not ok and spawned == [] and logged == []
    monkeypatch.setattr(student.subprocess, "Popen", lambda *_a, **_k: pytest.fail("không có gói thì không chạy gì"))
    assert student.run_in_studio(tmp_path / "other", "x", "y", {}, print, package=tmp_path / "missing") is False


def test_the_module_entry_point_reports_through_the_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: list[Any] = []
    monkeypatch.setattr(student, "_directory", None)
    monkeypatch.delenv(student.ENV_DIR, raising=False)
    monkeypatch.setattr(student, "available", lambda: True)
    monkeypatch.setattr(student, "compute", lambda project, **kwargs: (seen.append(project), kwargs["log"]("xong"), 6)[2])
    assert student.main([str(tmp_path / "project"), "--package", str(tmp_path / "pkg")]) == 0
    assert seen == [tmp_path / "project"] and student.package_dir() == tmp_path / "pkg" and "xong" in capsys.readouterr().out
    monkeypatch.setattr(student, "compute", lambda *_a, **_k: (_ for _ in ()).throw(MemoryError("hết RAM")))
    assert student.main([str(tmp_path)]) == 1 and "MemoryError" in capsys.readouterr().out
    monkeypatch.setattr(student, "available", lambda: False)
    assert student.main([str(tmp_path)]) == 2


def test_the_server_runs_the_student_in_process_with_torch_and_in_the_studio_child_without(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from abook.webui import server

    calls: list[tuple] = []
    monkeypatch.setattr(student, "run_after_analysis", lambda *args, **_k: calls.append(("local", args[0])))
    monkeypatch.setattr(student, "run_in_studio", lambda *args, **_k: calls.append(("studio", args[:4])))
    code = Path("C:/Studio/code/abc")
    studio = SimpleNamespace(installed=lambda: True, python=Path("C:/Studio/venv/Scripts/python.exe"), pythonw=Path("C:/Studio/venv/Scripts/pythonw.exe"),
                             code_for=lambda project: code, environment=lambda root: {"PYTHONPATH": str(root)})
    app = SimpleNamespace(studio=studio)
    monkeypatch.setattr(student, "dependencies_ok", lambda: True)
    server.App._scene_student_run(app, tmp_path)
    assert calls == [("local", tmp_path)], "máy dev có torch: tại chỗ như trước"
    calls.clear()
    monkeypatch.setattr(student, "dependencies_ok", lambda: False)
    server.App._scene_student_run(app, tmp_path)
    assert calls == [("studio", (tmp_path, Path("C:/Studio/venv/Scripts/python.exe"), code, {"PYTHONPATH": str(code)}))], \
        "python.exe của Studio (cần stdout), không phải pythonw"
    calls.clear()
    server.App._scene_student_run(SimpleNamespace(studio=SimpleNamespace(installed=lambda: False)), tmp_path)
    server.App._scene_student_run(SimpleNamespace(studio=None), tmp_path)
    assert calls == [("local", tmp_path)] * 2, "không torch, không Studio: đường tại chỗ tự bỏ qua vì không có phần chạy"
    monkeypatch.setattr(student, "run_in_studio", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("hỏng")))
    server.App._scene_student_run(app, tmp_path)  # không ném
