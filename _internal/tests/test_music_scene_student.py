"""Học sinh hình không khí trong chương (webui/music_scene_student.py + music_scenes.apply_student): nhúng bằng Qwen3 cắt lớp, căn giữa
trong chương + đầu hồi quy, bộ nhớ đệm, kiểu số CPU, áp vào đoạn, móc sau pha phân tích. Gói giả nhỏ dựng ngay trong test (Qwen3 4 lớp,
hidden 32, tokenizer WordLevel); không cần mạng, không GPU."""
from __future__ import annotations

import copy
import importlib.util
import json
import math
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
    # Kiểu số CPU đã "đo" sẵn (fp32: trọng số bf16 nở ra đúng từng bit) để test không đo thật.
    student.remember_cpu_dtype(root, "fp32", torch.__version__)
    return root


@pytest.fixture(scope="module")
def package_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _build_package(tmp_path_factory.mktemp("scene_q17"))


@pytest.fixture
def package(package_template: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "package"
    shutil.copytree(package_template, directory)
    monkeypatch.setenv(student.ENV_DIR, str(directory))
    monkeypatch.setattr(student, "_gpu_ready", lambda _torch: False)
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


# ---- tính cả cuốn, bộ nhớ đệm -----------------------------------------------------------------------------------------------------
def test_compute_matches_the_head_applied_to_the_reference_embeddings(package: Path, book: list[dict], tmp_path: Path) -> None:
    project = tmp_path / "project"
    assert _compute(project) == 6
    saved = student.load(project)
    assert saved["package"] == student.package_sha(package) and saved["version"] == 1 and len(saved["scenes"]) == 6
    head = student.Head(package / student.HEAD_FILE)
    for script in book:
        segments, scenes = script["segments"], music_scenes.chapter_scenes(script)
        assert len(scenes) == 3
        position = {segment["id"]: index for index, segment in enumerate(segments)}
        texts = ["\n".join(segments[i]["text"] for i in range(position[s["firstSegment"]], position[s["lastSegment"]] + 1)) for s in scenes]
        expected = head.deviations([_reference_embedding(package, text) for text in texts], [len(text.split()) for text in texts])
        mine = [item for item in saved["scenes"] if item["chapterId"] == script["chapterId"]]
        assert [(i["firstSegment"], i["lastSegment"]) for i in mine] == [(s["firstSegment"], s["lastSegment"]) for s in scenes]
        assert np.allclose([[i["dV"], i["dE"], i["dT"]] for i in mine], expected, atol=2e-3)


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
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(student._Embedder, "__init__", broken)
    lines, events = _run(tmp_path)
    assert len(lines) == 1 and "CUDA out of memory" in lines[0] and events == []
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
def _scene(start: float, end: float, valence: float, arousal: float, tension: float, first: int, last: int) -> dict:
    return {"chapterId": 7, "firstSegment": first, "lastSegment": last, "start": start, "end": end, "valence": valence, "arousal": arousal,
            "tension": tension, "moodSource": "chapter", "llmValence": 0.9, "llmTension": 0.8}


def _item(first: int, last: int, d_v: float, d_e: float, d_t: float, chapter: int = 7) -> dict:
    return {"chapterId": chapter, "firstSegment": first, "lastSegment": last, "dV": d_v, "dE": d_e, "dT": d_t}


def test_apply_student_adds_the_deviation_to_the_duration_weighted_chapter_mean_with_numbers_worked_by_hand() -> None:
    # Ba đoạn 60 / 120 / 60 giây. TB(V) = (.5*60 + .1*120 - .3*60) / 240 = .1; TB(E) = (.2*60 + 0 - .2*60) / 240 = 0; TB(T) = (.8*60 + .6*120 + .4*60) / 240 = .6.
    scenes = [_scene(0, 60, 0.5, 0.2, 0.8, 1, 10), _scene(60, 180, 0.1, 0.0, 0.6, 11, 20), _scene(180, 240, -0.3, -0.2, 0.4, 21, 30)]
    items = [_item(1, 10, 0.3, -0.1, 0.1), _item(11, 20, 0.0, 0.2, -0.3), _item(21, 30, -0.2, -0.1, 0.5)]
    before = copy.deepcopy(scenes)
    got = music_scenes.apply_student(scenes, items)
    assert scenes == before, "thuần hàm: không sửa đoạn đưa vào"
    assert [s["valence"] for s in got] == [pytest.approx(0.4), pytest.approx(0.1), pytest.approx(-0.1)]
    assert [s["arousal"] for s in got] == [pytest.approx(-0.1), pytest.approx(0.2), pytest.approx(-0.1)]
    assert [s["tension"] for s in got] == [pytest.approx(0.7), pytest.approx(0.3), pytest.approx(1.0)]  # .6 + .5 = 1.1 -> kẹp 1
    assert all(s["moodSource"] == "student" for s in got)
    assert [(s["chapterValence"], s["chapterTension"], s["labelArousal"]) for s in got] == [(0.5, 0.8, 0.2), (0.1, 0.6, 0.0), (-0.3, 0.4, -0.2)]
    assert [(s["llmValence"], s["llmTension"]) for s in got] == [(0.9, 0.8)] * 3, "giữ giá trị LLM để so"


def test_apply_student_keeps_the_chapter_mean_when_the_deviations_cancel_out() -> None:
    scenes = [_scene(0, 60, 0.5, 0.0, 0.2, 1, 10), _scene(60, 120, -0.1, 0.0, 0.4, 11, 20)]  # dài bằng nhau
    got = music_scenes.apply_student(scenes, [_item(1, 10, 0.25, 0.1, -0.1), _item(11, 20, -0.25, -0.1, 0.1)])
    assert sum(s["valence"] for s in got) / 2 == pytest.approx(0.2) and sum(s["tension"] for s in got) / 2 == pytest.approx(0.3)
    assert [s["valence"] for s in got] == [pytest.approx(0.45), pytest.approx(-0.05)]


def test_apply_student_leaves_the_chapter_alone_when_any_scene_has_no_item() -> None:
    scenes = [_scene(0, 60, 0.5, 0.2, 0.8, 1, 10), _scene(60, 120, 0.1, 0.0, 0.6, 11, 20)]
    before = copy.deepcopy(scenes)
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1)]) is scenes
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), _item(11, 19, 0.1, 0.1, 0.1)]) is scenes, "ranh giới khác thì không khớp"
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), _item(11, 20, 0.1, 0.1, 0.1, chapter=8)]) is scenes
    assert music_scenes.apply_student(scenes, [_item(1, 10, 0.1, 0.1, 0.1), {**_item(11, 20, 0.0, 0.0, 0.0), "dV": "hỏng"}]) is scenes
    assert music_scenes.apply_student(scenes, None) is scenes and music_scenes.apply_student(scenes, []) is scenes
    assert music_scenes.apply_student([], [_item(1, 10, 0, 0, 0)]) == [] and scenes == before


def test_a_chapter_with_one_scene_keeps_its_values_and_is_marked_student() -> None:
    scene = _scene(0, 90, 0.3, -0.2, 0.1, 1, 10)
    got, = music_scenes.apply_student([scene], [_item(1, 10, 0.0, 0.0, 0.0)])
    assert (got["valence"], got["arousal"], got["tension"]) == (0.3, -0.2, 0.1) and got["moodSource"] == "student"


def test_chapter_scenes_applies_the_student_after_the_chapter_level(book: list[dict]) -> None:
    script = book[0]
    plain = music_scenes.chapter_scenes(script)
    items = [_item(s["firstSegment"], s["lastSegment"], d, -d, d / 2, chapter=1) for s, d in zip(plain, (0.2, -0.1, -0.1))]
    # LLM đã đọc cả ba đoạn (mức chương áp, "chapter") rồi học sinh chỉnh tiếp quanh mức chương.
    moods = [{"chapterId": 1, "firstSegment": s["firstSegment"], "lastSegment": s["lastSegment"], "V": v, "E": 0.0, "T": t}
             for s, v, t in zip(plain, (2.0, 0.0, -2.0), (1.0, 0.0, -1.0))]
    level = music_scenes.chapter_scenes(script, moods)
    got = music_scenes.chapter_scenes(script, moods, student=items)
    assert [s["moodSource"] for s in level] == ["chapter"] * 3 and [s["moodSource"] for s in got] == ["student"] * 3
    mean = lambda scenes, axis: sum(s[axis] * (s["end"] - s["start"]) for s in scenes) / sum(s["end"] - s["start"] for s in scenes)  # noqa: E731
    for axis, key in (("valence", "dV"), ("arousal", "dE"), ("tension", "dT")):
        for after, item in zip(got, items):
            assert after[axis] == pytest.approx(max(-1.0, min(1.0, mean(level, axis) + item[key])), abs=2e-3), axis
    assert [s["chapterValence"] for s in got] == [s["valence"] for s in level]
    assert [(s["llmValence"], s["llmTension"]) for s in got] == [(s["llmValence"], s["llmTension"]) for s in level]
    # Không đổi ranh giới / chữ / cảm xúc.
    for field in ("start", "end", "firstSegment", "lastSegment", "reason", "lines", "sd", "emotions", "confidence"):
        assert [s[field] for s in got] == [s[field] for s in level], field
    # Không có LLM: học sinh vẫn áp trên giá trị đường nhãn.
    assert [s["moodSource"] for s in music_scenes.chapter_scenes(script, None, None, items)] == ["student"] * 3
    # Thiếu mục ở một đoạn của chương: đường hôm nay.
    assert music_scenes.chapter_scenes(script, moods, student=items[:2]) == level
    everything = music_scenes.book_scenes(book, moods, student=items)  # chương 2 không có mục nào: đường nhãn
    assert everything[:3] == got and {s["moodSource"] for s in everything[3:]} == {"labels"}


def test_the_plan_is_built_from_the_students_file(package: Path, book: list[dict], tmp_path: Path) -> None:
    project = tmp_path / "project"
    _compute(project)
    saved = student.load(project)
    scenes = music_scenes.book_scenes(book, student=saved["scenes"])
    assert len(scenes) == 6 and {s["moodSource"] for s in scenes} == {"student"}
    assert [s["valence"] for s in scenes] != [s["valence"] for s in music_scenes.book_scenes(book)]


# ---- gói tải theo yêu cầu --------------------------------------------------------------------------------------------------------------
def test_the_optional_download_part_is_blocked_while_the_package_is_unpublished(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(student.ENV_DIR, raising=False)
    monkeypatch.delenv(student.ENV_DOWNLOAD, raising=False)
    part = music_module.scene_student_part()
    assert part.label == "Học sinh không khí cảnh (1,9 GB)" and part.blocked == "chưa có bản model để tải" and part.downloads == []
    assert student.REVISION == "" and student.PACKAGE_HASHES == {} and student.model_downloads() == []
    assert "scene_q17" not in [component.id for component in music_module._components()], "tuỳ chọn: không đòi người dùng tải"
    monkeypatch.setenv(student.ENV_DOWNLOAD, "0")
    assert "đang bị tắt" in student.cannot_download()


def test_the_download_urls_follow_the_pin_once_a_revision_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(student, "REVISION", "abc123")
    monkeypatch.setattr(student, "PACKAGE_HASHES", {file: (f"{index:064x}", 100 + index) for index, file in enumerate(student.PACKAGE_FILES)})
    monkeypatch.delenv(student.ENV_DIR, raising=False)
    downloads = student.model_downloads()
    assert [d.name for d in downloads] == list(student.PACKAGE_FILES)
    assert downloads[1].url == "https://huggingface.co/NGDtuanh/abook-music-student/resolve/abc123/scene_q17/model.safetensors"
    assert student.cannot_download() == "" and student.total_bytes() == sum(100 + i for i in range(5))
    pin = student.model_pin()
    monkeypatch.setattr(student, "REVISION", "def456")
    assert student.model_pin() != pin
