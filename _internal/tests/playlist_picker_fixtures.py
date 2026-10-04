"""Sinh bộ ví dụ DÙNG CHUNG cho bộ chọn danh sách phát của "Nghe ngay" (tests/fixtures/playlist_picker/cases.json): pytest
(test_music_playlist.py) và test JVM Kotlin (PlaylistPickerTest) cùng đọc file này và phải ra đúng mã + điểm đã ghi.

Mã và điểm KHÔNG do code của app sinh mà do bản tham chiếu gốc (LLM_Train/music/listen_genre/picker.py + prepare.py, thứ đã đo
0,838 trên nửa đo) - app chép thuật toán ấy sang Python + Kotlin, bộ ví dụ này là thứ bảo đảm chép đúng. Chữ trong ví dụ đều TỰ ĐẶT
(repo công khai): không có một câu nào của truyện thật.

    cd _internal && runtime/.venv/Scripts/python.exe -m tests.playlist_picker_fixtures [thư mục LLM_Train/music/listen_genre]
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures" / "playlist_picker"
BUNDLED = Path(__file__).resolve().parents[1] / "abook" / "webui" / "assets" / "playlist_picker.json"
REFERENCE = Path("D:/Novels/LLM_Train/music/listen_genre")


def _module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def chapter(sentences: list[str], minimum: int = 1700) -> str:
    """Một chương: các câu lặp lại cho đủ `minimum` ký tự, xen câu trung tính để chương không chỉ toàn từ khoá."""
    filler = ["Trời đã về chiều, gió thổi qua bậu cửa.", "Anh ngồi yên một lúc rồi đứng dậy đi ra phía sân.",
              "Con đường trước mặt dài và vắng, chỉ có vài chiếc lá rơi.", "Không ai nói thêm điều gì nữa."]
    out: list[str] = []
    index = 0
    while sum(len(line) + 1 for line in out) < minimum:
        out.append(filler[(index // 2) % len(filler)] if index % 2 else sentences[(index // 2) % len(sentences)])
        index += 1
    return "\n".join(out)


def neutral(minimum: int) -> str:
    """Chương toàn câu trung tính, đúng `minimum` ký tự trở lên."""
    return chapter(["Chiếc đèn trên bàn vẫn sáng.", "Bà đặt tách trà xuống rồi nhìn ra cửa sổ."], minimum)


GENRES: dict[str, list[str]] = {
    "eastern": ["Hắn ngồi tu luyện suốt đêm, linh khí quanh đan điền dần đặc lại.", "Đạo hữu ở tông môn bên kia vừa đến thăm.",
                "Trưởng lão nói cảnh giới của hắn đã chạm tới trúc cơ."],
    "fantasy_adventure": ["Cô là mạo hiểm giả hạng thấp, vừa nhận nhiệm vụ ở hội mạo hiểm.", "Ma vương ở thế giới khác này chưa từng xuất hiện.",
                          "Kỹ năng mới của cậu mở ra khi xuống hầm ngục."],
    "action": ["Trận chiến nổ ra ngay khi binh lính vượt qua cổng.", "Anh là thợ săn hồi quy, tấn công liên tục không nghỉ.",
               "Tiếng súng và đạn xé ngang quân đội địch."],
    "school_light": ["Giờ ra chơi, học sinh lớp trưởng chạy vào lớp học tìm bài kiểm tra.", "Câu lạc bộ họp sau giờ tan học.",
                     "Bạn cùng lớp mặc đồng phục mới đến sớm."],
    "romance": ["Cậu tỏ tình ngay sau buổi hẹn hò đầu tiên.", "Cô đỏ mặt, cả hai ngượng ngùng không dám nhìn nhau.",
                "Người yêu cũ gửi lời chúc, còn hôn ước thì đã hủy."],
    "horror": ["Xác sống lảo đảo bước ra từ con ngõ tối.", "Tiếng thét vang lên, ai cũng rùng mình trước oán linh.",
               "Hồn ma ấy bị nguyền rủa từ lâu."],
    "mystery": ["Thám tử đến hiện trường vụ án từ sớm.", "Hung thủ để lại manh mối, nhưng nghi phạm nào cũng có bằng chứng ngoại phạm.",
                "Cảnh sát phong tỏa nơi xảy ra án mạng để điều tra."],
    "scifi": ["Phi thuyền rời hành tinh khi trí tuệ nhân tạo báo động.", "Robot kiểm tra máy chủ của tàu vũ trụ.",
              "Công nghệ thực tế ảo vận hành suốt chuyến đi trong vũ trụ."],
    "comedy": ["Cô phì cười vì cậu bạn đúng là đồ ngốc.", "Cậu ấy tsukkomi đúng lúc, cả phòng phì cười.",
               "Đồ ngốc, cậu lại quên mang ví rồi."],
    "fantasy_calm": ["Ông làm ruộng cả ngày ở nông trại nhỏ.", "Quán trọ cuối làng thảnh thơi như một buổi nghỉ hưu.",
                     "Bà nấu ăn cho khách trọ rồi ngồi hiên nhà."],
    "sad": ["Tang lễ diễn ra trong im lặng, nước mắt rơi không ngừng.", "Nỗi mất mát đè nặng lên cả gia đình.",
            "Nước mắt cô cứ rơi mãi sau tang lễ."],
}

TITLES = {"eastern": "Bên dòng sông cũ", "fantasy_adventure": "Chuyện ở thị trấn nhỏ", "action": "Những ngày cuối mùa",
          "school_light": "Một năm ở trường", "romance": "Mùa gió chướng", "horror": "Đêm không ngủ",
          "mystery": "Căn nhà cuối phố", "scifi": "Chuyến đi dài", "comedy": "Hàng xóm kỳ lạ",
          "fantasy_calm": "Buổi sáng yên ả", "sad": "Lá thư chưa gửi"}


def case(name: str, title: str, chapters: list[str], **extra: Any) -> dict[str, Any]:
    return {"name": name, "title": title, "chapters": chapters, **extra}


def small_picker(**changes: Any) -> dict[str, Any]:
    """Luật nhỏ cho các ca riêng: mặc định "calm", không prior, nên điểm thấp là rơi về mặc định thật sự."""
    picker: dict[str, Any] = {"version": 7, "cap": 3, "title_weight": 5.0, "min_score": 4.0, "default": "calm", "order": ["calm", "storm", "dusk"],
                              "playlists": {"calm": {"title": ["yen"], "text": {"gió nhẹ": 1}},
                                            "storm": {"title": ["bao"], "text": {"giông bão": 2, "sấm": 1}},
                                            "dusk": {"title": [], "text": {"hoàng hôn": 2.5}, "prior": 0.5}}}
    picker.update(changes)
    return picker


def cases() -> list[dict[str, Any]]:
    out = [case(f"{code}_from_the_text", TITLES[code], [chapter(GENRES[code])]) for code in GENRES]
    out += [
        # tên không dấu / có dấu: tên so ở dạng bỏ dấu
        case("title_without_marks", "Tu Tien Ky", [neutral(1700)]),
        case("title_with_marks_and_capitals", "Đạo Thiên Lộ", [neutral(1700)]),
        case("title_beats_a_light_body", "Kiếm Và Hoa", [chapter(GENRES["romance"][:1])]),
        # chương phụ: ngắn, hay mở bằng minh hoạ / mục lục -> bị bỏ
        case("short_and_front_chapters_are_skipped", "Một cuốn sách",
             ["Minh họa\n" + chapter(GENRES["eastern"]), chapter(GENRES["scifi"], 1200), "Mục lục\n" + chapter(GENRES["mystery"]),
              "  \n" + chapter(GENRES["horror"]).replace("\n", "\n\n")]),
        case("only_front_chapters_means_no_body", "Một cuốn sách", ["Lời bạt\n" + chapter(GENRES["romance"]), chapter(GENRES["sad"])[:1400]]),
        # 6.000 ký tự đầu: từ khoá nằm sau mốc không được tính
        case("keywords_after_the_6000_mark_do_not_count", "Một cuốn sách", [neutral(6100) + "\n" + chapter(GENRES["sad"], 3000)]),
        case("keywords_inside_the_6000_mark_count", "Một cuốn sách", [neutral(5000) + "\n" + chapter(GENRES["sad"], 1700)]),
        case("body_stops_at_6000_across_chapters", "Một cuốn sách", [neutral(3000), neutral(3200), chapter(GENRES["horror"], 2000)]),
        # hoà theo `order` (không theo chữ cái): scifi đứng trước comedy
        case("tie_follows_order_not_alphabet", "Một cuốn sách",
             [neutral(1500) + "\nPhi thuyền đến. Phi thuyền đi. Tsukkomi một. Tsukkomi hai.\n"]),
        case("repeated_keyword_is_capped", "Một cuốn sách", [chapter(["Cậu tỏ tình. " * 30])]),
        # đếm không chồng lấn như str.count: bảy chữ elf liền nhau chỉ tính bốn
        case("overlapping_keyword_counts_like_str_count", "Một cuốn sách", [neutral(1500) + "\nelf elf elf elf elf elf elf\n"]),
        case("empty_book_uses_the_title_only", "Sword Art", []),
        case("nothing_matches", "Một cuốn sách", [neutral(1700)]),
        # chuẩn hoá chữ: NFD, hoa / thường, dấu câu, khoảng trắng lạ
        case("decomposed_marks_and_capitals", "Một cuốn sách",
             [unicodedata.normalize("NFD", chapter(GENRES["eastern"])).upper()]),
        case("punctuation_and_odd_spaces", "Một cuốn sách",
             [chapter(["(Tu luyện), linh\u00a0khí; đan\tđiền... tông\u2028môn!", "“Đạo hữu”—trúc cơ?"]).replace(". ", ".\u0085")]),
        case("keywords_must_be_whole_words", "Một cuốn sách", [chapter(["Anh ấy tu luyện hơn, tu luyệnnn thì không tính, tuluyện cũng không."])]),
        # luật riêng của ca: dưới min_score về mặc định, cap, order lạ
        case("below_min_score_falls_back_to_the_default", "Một cuốn sách", [chapter(["Gió nhẹ thổi qua. Một tiếng sấm xa."])],
             picker=small_picker(default="dusk")),
        case("score_at_min_score_wins", "Một cuốn sách", [chapter(["Giông bão kéo đến. Giông bão chưa dứt."])], picker=small_picker()),
        case("prior_and_fractions_add_up", "Bão Yên", [chapter(["Hoàng hôn buông. Hoàng hôn đỏ."])], picker=small_picker()),
        case("order_names_a_list_without_text", "Một cuốn sách", [neutral(1700)],
             picker=small_picker(order=["ghost", "calm"], min_score=0.0)),
        # luật không dùng được -> không chọn
        case("no_picker_means_no_pick", "Một cuốn sách", [chapter(GENRES["eastern"])], picker=None),
        case("malformed_picker_means_no_pick", "Một cuốn sách", [chapter(GENRES["eastern"])], picker={"version": 1, "order": "calm"}),
    ]
    return out


# ---- chọn luật: của mục lục hay bản đóng kèm ----------------------------------------------------------------------------


def catalogue(*codes: str, **extra: Any) -> dict[str, Any]:
    return {"format": "abook-music-catalog", "version": 1, "revision": "r1",
            "playlists": [{"id": code, "name": code, "description": "", "minutes": 5, "tracks": [f"https://x/{code}.mp3"]} for code in codes], **extra}


def manifest_picker(**changes: Any) -> dict[str, Any]:
    picker: dict[str, Any] = {"version": 3, "cap": 5, "title_weight": 12.0, "min_score": 4.0, "default": "b", "order": ["a", "b"],
                              "playlists": {"a": {"title": ["alpha"], "text": {"bão tố": 2}}, "b": {"title": ["beta"], "text": {"nắng": 1}}}}
    picker.update(changes)
    return picker


def selection() -> list[dict[str, Any]]:
    book = [chapter(GENRES["eastern"])]
    title = "Một cuốn sách"
    storm = [chapter(["Bão tố đổ xuống. Bão tố chưa dứt."])]
    cat = ("a", "b")
    out = [
        {"name": "valid_picker_in_the_manifest", "manifest": catalogue(*cat, playlistPicker=manifest_picker()), "source": "manifest",
         "title": title, "chapters": storm},
        {"name": "manifest_picker_may_name_fewer_lists", "manifest": catalogue("a", "b", "c", playlistPicker=manifest_picker()), "source": "manifest",
         "title": "Alpha", "chapters": [neutral(1700)]},
        {"name": "no_picker_in_the_manifest", "manifest": catalogue(*cat), "source": "bundled", "title": title, "chapters": book},
        {"name": "no_manifest_yet", "manifest": None, "source": "bundled", "title": title, "chapters": book},
        {"name": "empty_manifest", "manifest": {}, "source": "bundled", "title": title, "chapters": book},
    ]
    broken: dict[str, dict[str, Any]] = {
        "default_not_in_the_catalogue": manifest_picker(default="z"),
        "order_names_a_list_the_catalogue_lacks": manifest_picker(order=["a", "z"]),
        "playlists_name_a_list_the_catalogue_lacks": manifest_picker(playlists={"a": {"title": [], "text": {}}, "z": {"title": [], "text": {}}}),
        "version_is_not_an_integer": manifest_picker(version="3"),
        "version_is_a_boolean": manifest_picker(version=True),
        "cap_is_text": manifest_picker(cap="5"),
        "title_weight_is_missing": {key: value for key, value in manifest_picker().items() if key != "title_weight"},
        "min_score_is_a_boolean": manifest_picker(min_score=False),
        "a_text_weight_is_text": manifest_picker(playlists={"a": {"title": [], "text": {"bão tố": "2"}}, "b": {"title": [], "text": {}}}),
        "a_title_entry_is_a_number": manifest_picker(playlists={"a": {"title": [7], "text": {}}, "b": {"title": [], "text": {}}}),
        "prior_is_text": manifest_picker(playlists={"a": {"title": [], "text": {}, "prior": "x"}, "b": {"title": [], "text": {}}}),
        "order_is_empty": manifest_picker(order=[]),
        "picker_is_not_an_object": ["a", "b"],
    }
    for name, picker in broken.items():
        out.append({"name": f"invalid_{name}_falls_back_to_the_bundled_one", "manifest": catalogue(*cat, playlistPicker=picker),
                    "source": "bundled", "title": title, "chapters": book})
    return out


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else REFERENCE
    reference = _module("listen_genre_picker", root / "picker.py")
    prepare = _module("listen_genre_prepare", root / "prepare.py")
    bundled = json.loads(BUNDLED.read_text(encoding="utf-8"))
    assert BUNDLED.read_bytes() == (root / "genre_lexicon.json").read_bytes(), "assets/playlist_picker.json khác genre_lexicon.json gốc"

    def run(picker: dict[str, Any] | None, title: str, chapters: list[str]) -> tuple[str | None, dict[str, float] | None]:
        if picker is None or not _plausible(picker):
            return None, None
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for number, text in enumerate(chapters):
                (folder / f"{number:04d}.txt").write_bytes(text.encode("utf-8"))
            body = prepare.squash("\n".join(prepare.content_chapters(folder)))[:prepare.PICKER_CHARS]
            lexicon_file = folder / "lexicon.json"
            lexicon_file.write_bytes(json.dumps(picker, ensure_ascii=False).encode("utf-8"))
            lexicon = reference.load(lexicon_file)
        return reference.choose(lexicon, title, body), reference.scores(lexicon, title, body)

    result = {"picker": bundled, "cases": [], "selection": []}
    for item in cases():
        picker = item.pop("picker", bundled)
        expect, scores = run(picker, item["title"], item["chapters"])
        out = dict(item)
        if picker is not bundled:
            out["picker"] = picker
        out.update(expect=expect, scores=scores)
        result["cases"].append(out)
    for item in selection():
        manifest = item["manifest"]
        picker = bundled
        if item["source"] == "manifest":
            picker = manifest["playlistPicker"]
        expect, _ = run(picker, item["title"], item["chapters"])
        result["selection"].append({**item, "expect": expect})
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "cases.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    picks = [item["expect"] for item in result["cases"]]
    print(f"{len(result['cases'])} ca chọn, {len(result['selection'])} ca chọn luật; mã ra: {sorted(set(map(str, picks)))}")


def _plausible(picker: Any) -> bool:
    """Luật đủ hình dạng để bản tham chiếu chạy được (bản tham chiếu không kiểm, ca hỏng thì app trả None)."""
    try:
        return (isinstance(picker["order"], list) and isinstance(picker["playlists"], dict) and isinstance(picker["default"], str)
                and all(isinstance(item, dict) for item in picker["playlists"].values()))
    except (KeyError, TypeError):
        return False


if __name__ == "__main__":
    main()
