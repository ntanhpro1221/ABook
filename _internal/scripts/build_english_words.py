"""Sinh danh sách từ tiếng Anh cho "Nghe ngay" (`abook/readaloud/english_words.txt` + bản Kotlin `readaloud/EnglishWords.kt`).

Việc của danh sách: khi một cuốn có gốc Nhật / Hàn (`abook/readaloud/names.py` `book_origin`), tên viết bằng chữ Latin được đọc theo luật phiên âm
(`romanization.py`) - trừ từ tiếng Anh thật ("Rose", "Mike", "Level"), để sea-g2p đọc bằng âm Anh như trước. sea-g2p không có API "từ này có trong
từ điển không" (từ điển Anh của nó chứa cả Yamato, Tanaka, Haruto), nên danh sách này là của app.

Cách lấy: từ nguyên vẹn (không `##`) của từ vựng `bert-base-uncased` (Apache-2.0; id càng nhỏ càng thường gặp), cũng có trong CMU Pronouncing Dictionary
(`abook/assets/cmudict.dict`, BSD) - từ nào cả hai cùng có thì là tiếng Anh thật, không phải mảnh chữ hay tên lạ. Cắt ở id <= BERT_MAX_ID: số
này là KẾT QUẢ ĐO trên kho truyện thử (LN Nhật dịch Việt): tên Nhật thường gặp rơi ra ngoài (Kenji 25894, Sakura 23066, Mori 22993, Chiba 27368,
Kawasaki 27324, Shia 20474, Nana 17810, Mina 19808, Sera 26358) còn tên Anh thường gặp ở trong (Mike 3505, Rose 3123, Tom 3419, Kate 5736, Anne 4776,
Maria 3814, Nina 9401); cao hơn nữa thì thêm tên Nhật (Honda 11990, Shin 12277), thấp hơn thì mất từ Anh thường (orange 4589, horizon 9154).

Chạy lại (chỉ khi cố ý đổi): runtime/.venv/Scripts/python.exe scripts/build_english_words.py
tests/test_names.py kiểm hai file này khớp nhau và khớp lần sinh mới nhất khi có từ vựng bert trong bộ nhớ đệm Hugging Face.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BERT_MAX_ID = 10_000
TEXT = ROOT / "abook" / "readaloud" / "english_words.txt"
KOTLIN = ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "vn" / "abook" / "player" / "readaloud" / "EnglishWords.kt"
CMUDICT = ROOT / "abook" / "assets" / "cmudict.dict"
CHUNK_BYTES = 20_000  # một hằng chuỗi của JVM tối đa 65535 byte

# Tên riêng Anh / Âu thường gặp (tự viết, không chép từ nguồn nào): tên gọi nam, nữ và họ. Từ vựng bert chỉ có tên nào đủ thường gặp trong văn bản tiếng Anh;
# truyện dịch lại hay dùng tên Âu hiếm hơn (Dario, Romeo, Tobias...), mà nhiều tên trong số đó cũng có hình romaji ("Mario" -> "Ma-ri-ô"). Chủ sách đo 04-10:
# VieNeu / Edge đọc tên Anh để nguyên đúng, nên tên Anh / Âu PHẢI giữ nguyên.
GIVEN_NAMES = """
aaron abby abigail adam adrian adrienne agnes alan albert alec alex alexander alexandra alfred alice alicia alison allan allen alma alvin amanda amber amelia amy
andrea andrew andy angela angelica angelo angie anita ann anna annabelle anne annette anthony antonio archer archie arnold arthur ashley audrey august augustus
barbara barney barry beatrice beatrix becky ben benedict benjamin bernard bernice bert beth betty beverly bill billy blake bob bobby bonnie brad bradley brandon
brenda brian bridget britney bruce bryan caleb calvin camille candice carl carla carlos carmen carol caroline carrie casey cassandra catherine cathy cecil cecilia
celeste charles charlie charlotte chloe chris christian christina christine christopher cindy claire clara clarence claude claudia clay clifford clyde colin connie
connor constance cora corey craig cynthia daisy dale damian damien dan dana daniel danielle danny daphne darren dave david dean deborah debra denise dennis derek
diana diane dick dominic donald donna dora doris dorothy doug douglas drew dylan earl ed eddie edgar edith edmund edward edwin eileen elaine eleanor elena elias elijah
elisa elizabeth ella ellen elliot ellis elmer elsa elvis emily emma eric erica erik erin ernest ernie esther ethan eugene eva evan eve evelyn fabian faith felix
fiona florence floyd frances francis frank franklin fred freddie frederick gabriel gabriella gary gavin gene geoffrey george georgia gerald gerard gilbert gina
gladys glen glenn gloria gordon grace graham grant greg gregory gretchen gus guy gwen hank hannah harold harriet harry harvey hazel heather hector heidi helen helena
henry herbert herman hilda holly howard hugh hugo ian ida irene iris isaac isabel isabella isabelle ivan ivy jack jackie jacob jacqueline jade jake james jamie jane
janet janice jared jasmine jason jasper jay jean jeanne jeff jeffrey jenna jennifer jenny jeremy jerome jerry jesse jessica jessie jill jim jimmy joan joanna joe joel
john johnny jon jonathan jordan joseph josephine joshua joy joyce juan judith judy julia julian julie juliet june justin karen kate katherine kathleen kathy katie
kay keith kelly ken kendra kenneth kevin kim kimberly kirk kyle lance larry laura lauren laurence lawrence leah lee leo leon leonard leslie lester lewis lila lillian
lily linda lisa liz lloyd logan lois lola lorenzo lorraine louis louise lucas lucia lucille lucy luke luther lydia lynn mabel mack madeline maggie marc marcel marcus
margaret maria marian marie marilyn marina mario marion mark marshall martha martin marvin mary mason matilda matt matthew maureen max maxwell may megan melanie melissa
melvin meredith michael michelle mike miles mildred milton miranda miriam mitchell molly monica morgan morris murray myra nancy naomi natalie nathan nathaniel neil
nell nelson nicholas nick nicole nigel nina noah noel nora norman norma olga oliver olivia oscar otto owen pamela pat patricia patrick paul paula pauline pearl pedro
peggy penny percy perry pete peter philip phillip phoebe phyllis priscilla rachel ralph ramon randall randy raphael ray raymond rebecca reginald rene renee ricardo
richard rick ricky rita rob robert roberta robin rod rodney roger roland ron ronald ronnie rosa rose rosemary ross roy ruby rudolph rudy russell ruth ryan sabrina sally
sam samantha samuel sandra sara sarah scott sean sebastian sergio seth shane sharon sheila shelley sherry shirley sidney silvia simon sofia sonia sophia sophie stanley
stella stephanie stephen steve steven stuart sue susan susanna suzanne sydney sylvia tamara tammy tanya ted teddy teresa terry theodore theresa thomas tiffany tim
timothy tina toby todd tom tommy tony tracy travis trevor tyler ulysses valerie vanessa vera vernon veronica vicky victor victoria vincent viola violet virginia vivian
wade wallace walter wanda warren wayne wendy wesley whitney wilbur wilfred will william willie willis wilma winston xavier yvonne zachary zoe
adelaide adele aiden alba alberto aldo alessandro alexei alfonso alina allegra amadeus ambrose anastasia anatoly andre andrei angus anton armand astrid aurelia
aurelio balthazar bastian bianca boris bruno carlo cassius cedric celia cesar claudio cornelius cosmo cyril dante delia dimitri dino dmitri domingo dorian dragan edmond
eduardo elmo emil emilia emilio enrico enzo ernesto esmeralda estelle eugenia fabio federico fernando fidel filip flora fortuna francesca francisco franz freya fritz
gaston gemma geoffroy giorgio giovanni giselle gunther gustav hans harlan heinrich helga henri henrik hermann horace hubert ignatius igor ilya imogen ingrid isidore
ivana jacques jakob jana javier jens jerzy joachim jorge josef julius jurgen karl katarina klaus konrad kurt lars laszlo leopold liam lionel lorenz lothar luca
lucien ludwig luis luigi magnus manuel marco margo marguerite mateo matteo mathias maurice mauro maximilian mikhail miguel milena mirabelle monique moritz natasha
nicolas nikolai nikola olaf ophelia orlando oskar pablo paolo pascal pavel penelope petra philippe pierre pietro placido rafael ramona raul reinhard reinhardt remy
renata roberto rodrigo roman romeo rosalind rosalie rufus rupert sabine salvador sandro santiago sasha serena serge sergei silas simone sofie sonja stefan
stefano sven tatiana teodor thea theo thierry tobias tomas ugo ulrich ursula valentin valentina vasily viktor vittorio vladimir walther wilhelm wolfgang yuri yves zelda
"""
SURNAMES = """
adams allen anderson bailey baker barnes bell bennett black bradley brooks brown bryant butler campbell carter clark coleman collins cook cooper cox davis
edwards ellis evans fisher flores ford foster fox gardner gibson gonzalez gordon graham grant gray green griffin hall hamilton harris harrison hart hayes henderson
hill holmes howard hughes hunt jackson james jenkins johnson jones kelly kennedy king knight lee lewis long lopez marshall martin martinez mason mccarthy miller mitchell
moore morgan morris murphy murray myers nelson nichols owens palmer parker patterson perry peterson phillips porter powell price reed reynolds richardson riley rivera
roberts robinson rogers ross russell sanders scott shaw simmons simpson smith spencer stevens stewart sullivan taylor thomas thompson torres turner wagner walker
wallace ward warren washington watson webb wells west white williams wilson wood wright young
"""
# Tên vốn là tên Nhật thường gặp trong light novel và trùng hình với tên Anh / Âu: KHÔNG giữ làm tiếng Anh, để gốc của cuốn quyết (cuốn gốc Nhật -> phiên
# âm theo luật; cuốn không có gốc Nhật thì chẳng có gì đổi). Chủ sách 04-10: Hana, Rika, Mina, Kana, Nana, Sakura... Kate, Mike, Rose, Anne, Emma, Nina, Sara giữ Anh.
JAPANESE_NAMES = """
hana rika mina kana nana sakura mika rina miku saki aki mio emi ami mai rin ren rei ryo kai sora yuki aya ayaka asuna mari maki maya mei miyu nao nono rio ria rena
reina sana sena shiori suzu tama yui yuri hiro kenji ryu shin shu haru riku sho tai tomo yu yuu
"""


def bert_vocab() -> list[str]:
    home = Path.home() / ".cache" / "huggingface" / "hub" / "models--bert-base-uncased" / "snapshots"
    found = sorted(glob.glob(str(home / "*" / "vocab.txt")))
    if not found:
        raise SystemExit("Không thấy vocab.txt của bert-base-uncased trong bộ nhớ đệm Hugging Face")
    return Path(found[0]).read_text(encoding="utf-8").split("\n")


def words() -> list[str]:
    cmu = {line.split(" ", 1)[0].split("(")[0] for line in CMUDICT.read_text(encoding="utf-8").splitlines() if line.strip()}
    vocab = bert_vocab()
    common = {word for word in vocab[:BERT_MAX_ID + 1] if re.fullmatch("[a-z]{2,}", word) and word in cmu}
    return sorted((common | set(GIVEN_NAMES.split()) | set(SURNAMES.split())) - set(JAPANESE_NAMES.split()))


def kotlin_source(listed: list[str]) -> str:
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for word in listed:
        if size + len(word) + 1 > CHUNK_BYTES:
            chunks.append(" ".join(current))
            current, size = [], 0
        current.append(word)
        size += len(word) + 1
    chunks.append(" ".join(current))
    parts = ",\n".join(f'        "{chunk}"' for chunk in chunks)
    return (
        "package vn.abook.player.readaloud\n\n"
        "/**\n"
        " * Từ tiếng Anh thật (viết thường) mà \"Nghe ngay\" giữ cho sea-g2p đọc, không phiên âm theo gốc Nhật / Hàn của cuốn - bản sao CHÍNH XÁC của\n"
        " * `abook/readaloud/english_words.txt` (scripts/build_english_words.py sinh cả hai; tests/test_names.py kiểm khớp). Đừng sửa tay.\n"
        " */\n"
        "object EnglishWords {\n"
        "    val ALL: Set<String> by lazy {\n"
        "        listOf(\n"
        f"{parts},\n"
        '        ).flatMap { it.split(\' \') }.toHashSet()\n'
        "    }\n"
        "}\n"
    )


def main() -> int:
    listed = words()
    TEXT.write_bytes(("\n".join(listed) + "\n").encode("utf-8"))
    KOTLIN.write_bytes(kotlin_source(listed).encode("utf-8"))
    print(f"{len(listed)} words, {TEXT.stat().st_size} bytes -> {TEXT.relative_to(ROOT)} and {KOTLIN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
