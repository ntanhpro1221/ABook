import { S } from "../shared/strings.generated";
import { voiceName, type CastChapter, type CastNarrator, type NarratorRowView } from "./model";

// Danh sách "Người kể chuyện" của tab Nhân vật (CastList), chung trang nghe và Studio. Android: data/ListenExtras.kt (Cast.narratorRows),
// Qt: CastLogic.js - cùng luật, cùng chữ.

/** "Chương 5, 7" khi mọi tên là "Chương <số>"; không thì các tên nối bằng dấu phẩy. `lower`: đứng sau chữ khác ("… trừ chương 5, 7"). */
export function chapterList(chapters: CastChapter[], lower = false): string {
  const numbers = chapters.map((chapter) => /^Chương\s+(\d+)$/.exec(chapter.title.trim())?.[1]);
  const joined = numbers.join(", ");
  if (chapters.length && numbers.every(Boolean)) return lower ? S.s_chuong_0_55d256d1(joined) : S.s_chuong_0_268b0521(joined);
  return chapters.map((chapter) => chapter.title).join(", ");
}

/** Danh sách "Người kể chuyện" đúng như cast.json ghi: giọng chính rồi từng giọng kể theo chương. Mục không đúng dạng thì bỏ qua. */
export function narratorRows(narrator: CastNarrator): NarratorRowView[] {
  const others = (narrator.chapterVoices ?? []).filter((entry) => entry && typeof entry === "object" && Array.isArray(entry.chapters));
  const several = others.length > 0;
  const except = narrator.exceptChapters ?? [];
  const main: NarratorRowView = {
    key: "main", voice: narrator.voice || S.s_mac_dinh_9a1af367, preset: narrator.voice, main: true,
    scope: several && except.length ? S.s_toan_sach_tru_0_baff4d91(chapterList(except, true)) : "",
    lines: narrator.voiceLines ?? narrator.lines, seconds: narrator.voiceSeconds ?? narrator.seconds,
  };
  return [main, ...others.map((entry, index) => ({
    key: `chapter-${index}-${entry.voice}`, voice: voiceName(entry.profile) || entry.voice, preset: entry.profile?.preset || entry.voice, main: false,
    scope: chapterList(entry.chapters), lines: entry.lines, seconds: entry.seconds,
  }))];
}

/** Ô giới của một người trong tab Nhân vật: giới cast.json ghi; trống thì lý do (store.cast_gender_note) - "Nhóm", "Trẻ em" hay
 *  "Chưa rõ". Không bao giờ để trống, không bao giờ bịa giới. Android: Cast.genderText, Qt: CastLogic.genderText - cùng chữ. */
export function genderText(person: { gender: string; genderNote?: string }): string {
  if (person.gender) return person.gender;
  if (person.genderNote === "group") return S.s_cast_gender_group;
  return person.genderNote === "child" ? S.s_cast_gender_child : S.s_chua_ro_be464a5a;
}
