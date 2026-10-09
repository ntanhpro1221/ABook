import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/studio/api";
import { useClip } from "./clip";
import { refreshAfterEdit } from "./EditBook";
import { chosenVoice, resolveVoice } from "./readAloudVoice";
import { useReadAloudVoices, useSource } from "./source";
import { splitPieces } from "./words";

// Cách đọc riêng của một cuốn chỉ có chữ ("Đọc từ này là…", lớp sửa `readings` - abook/readaloud/readings.py, BookEdits.kt): người
// nghe dạy giọng đọc một từ hay một cụm 2..6 từ liền nhau (thường là tên riêng, "Hạ Vy") cho cả cuốn. Chỉ giọng đọc đổi, chữ của sách giữ nguyên.
// Khoá khớp cả từ, phân biệt hoa thường - cùng luật với máy chủ và điện thoại (bỏ dấu câu / ngoặc hai đầu cụm, không dấu câu chen giữa).

export interface BookReading {
  surface: string;
  spoken: string;
}

const EDGE = /^[^\p{L}\p{M}\p{N}]+|[^\p{L}\p{M}\p{N}]+$/gu;

/** Lõi của một chữ hiện: bỏ dấu câu, ngoặc, gạch... ở hai đầu ("“Haruto,”" -> "Haruto"); NFC như khoá của máy chủ. */
export function wordCore(token: string): string {
  return token.normalize("NFC").replace(EDGE, "");
}

/** Chữ hiện thứ `word` của câu (đơn vị `\S+` như words.ts) đã bỏ dấu câu hai đầu, hay "" nếu không có. */
export function wordOf(text: string, word: number): string {
  const piece = splitPieces(text).find((item) => item.word === word);
  return piece ? wordCore(piece.text) : "";
}

/** Một cụm tối đa chừng này chữ liền nhau (cùng giới hạn `KEY_WORDS_MAX` của máy chủ và điện thoại). */
export const MAX_PHRASE_WORDS = 6;

/** Một chữ hiện của câu: `core` đã bỏ dấu câu hai đầu ("" cho chữ chỉ có dấu câu), `lead` / `tail` = còn dấu câu ở đầu / ở đuôi chữ. */
export interface SentenceToken {
  core: string;
  lead: boolean;
  tail: boolean;
}

/** Các chữ hiện của câu theo thứ tự (đơn vị `\S+` như mốc từng chữ): chỉ số trong mảng = thứ tự chữ (cùng số với `word` của `splitPieces`). */
export function sentenceTokens(text: string): SentenceToken[] {
  return splitPieces(text)
    .filter((piece) => piece.word >= 0)
    .map((piece) => {
      const token = piece.text.normalize("NFC");
      const core = wordCore(token);
      const at = core ? token.indexOf(core) : 0;
      return { core, lead: at > 0, tail: Boolean(core) && at + core.length < token.length };
    });
}

/** Khoá của cụm gồm các chữ hiện từ `from` tới `to` (cùng luật khớp cụm với readings.py): null khi quá `MAX_PHRASE_WORDS` chữ, có chữ chỉ là dấu câu, hay có
 *  dấu câu chen GIỮA cụm. Dấu câu ở đầu chữ đầu và đuôi chữ cuối thì được ("“Hạ Vy,”" -> "Hạ Vy"). */
export function phraseKey(tokens: readonly SentenceToken[], from: number, to: number): string | null {
  if (from < 0 || to < from || to >= tokens.length || to - from + 1 > MAX_PHRASE_WORDS) return null;
  const cores: string[] = [];
  for (let at = from; at <= to; at++) {
    const token = tokens[at];
    if (!token.core || (at > from && token.lead) || (at < to && token.tail)) return null;
    cores.push(token.core);
  }
  return cores.join(" ");
}

/** Vùng đang chọn trong câu: các chữ hiện từ `from` tới `to` (kể cả). */
export interface PhraseSelection {
  from: number;
  to: number;
}

/** Bấm chữ `at`: đang chọn đúng MỘT chữ khác thì mở rộng thành cụm tới chữ ấy (bấm chữ đầu rồi chữ cuối) nếu cụm hợp lệ; còn lại thì chọn riêng chữ ấy. */
export function pickWord(tokens: readonly SentenceToken[], current: PhraseSelection | null, at: number): PhraseSelection {
  if (current && current.from === current.to && current.from !== at) {
    const from = Math.min(current.from, at);
    const to = Math.max(current.from, at);
    if (phraseKey(tokens, from, to) !== null) return { from, to };
  }
  return { from: at, to: at };
}

/** Cách đọc người gõ, đã gọn: bỏ khoảng trắng hai đầu, gộp khoảng trắng giữa (máy chủ làm sạch cùng cách). */
export function cleanSpoken(value: string): string {
  return value.normalize("NFC").trim().replace(/\s+/gu, " ");
}

/** Cách đọc đem "Nghe thử" (chưa lưu): bảng một mục, hay `undefined` khi chưa gõ gì / gõ đúng chữ của sách (đọc như thường). */
export function trialReadings(surface: string, spoken: string): Record<string, string> | undefined {
  const word = wordCore(surface);
  const said = cleanSpoken(spoken);
  return word && said && said !== word ? { [word]: said } : undefined;
}

/** Cách đọc đang đặt cho `word` trong danh sách của cuốn (khớp đúng hoa thường, như lúc đọc). */
export function readingFor(list: readonly BookReading[] | undefined, word: string): string {
  return list?.find((item) => item.surface === word)?.spoken ?? "";
}

/** Danh sách "Cách đọc tên" của cuốn (`GET /api/books/<mã>/readings`; điện thoại: LocalStudio). */
export function useBookReadings(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["book", bookId, "readings"],
    queryFn: async () => (await api<{ readings: BookReading[] }>(`/api/books/${bookId}/readings`)).readings,
    enabled: enabled && Boolean(bookId),
    staleTime: 60_000,
  });
}

/** Đặt (hay bỏ - `spoken` rỗng) cách đọc của một từ cho cả cuốn. Xong thì làm mới danh sách và số thay đổi của sách. */
export function useSaveReading(bookId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ surface, spoken }: BookReading) =>
      api<{ readings: BookReading[] }>(`/api/books/${bookId}/readings`, { method: "PUT", body: { surface, spoken: cleanSpoken(spoken) } }),
    onSuccess: (view) => {
      client.setQueryData(["book", bookId, "readings"], view.readings);
      refreshAfterEdit(client, bookId);
    },
  });
}

/** "Nghe thử" một cách đọc bằng giọng đang đọc cuốn này (giọng chọn cho cuốn - Cài đặt / menu giọng): máy tính `/api/readaloud/clip`,
 *  điện thoại `ReadAloud.sample`, cách đọc gửi kèm chưa lưu vào sách. `available`: máy này có giọng đọc. */
export function useReadAloudTry(bookId: string) {
  const source = useSource();
  const clip = useClip();
  const { data: voices } = useReadAloudVoices();
  const [loading, setLoading] = useState("");
  const [failed, setFailed] = useState("");
  const voice = voices?.length ? resolveVoice(voices, chosenVoice(bookId)) : undefined;
  const idOf = (surface: string, spoken: string) => `reading-${surface}\u0000${cleanSpoken(spoken)}`;
  const play = async (surface: string, spoken: string) => {
    const id = idOf(surface, spoken);
    setFailed("");
    if (clip.current === id) {
      clip.stop();
      return;
    }
    if (!voice || !source.readAloudSample) return;
    setLoading(id);
    try {
      // Ô trống / đúng chữ của sách: {} - nghe từ ấy đọc như thường, không lấy cách đọc đã lưu.
      clip.toggle(id, await source.readAloudSample(voice.id, wordCore(surface), { bookId, readings: trialReadings(surface, spoken) ?? {} }));
    } catch (error) {
      setFailed((error as Error)?.message || "Chưa nghe thử được lúc này.");
    } finally {
      setLoading("");
    }
  };
  return {
    available: Boolean(voice && source.readAloudSample),
    play,
    playing: (surface: string, spoken: string) => clip.current === idOf(surface, spoken),
    loading: (surface: string, spoken: string) => loading === idOf(surface, spoken),
    failed,
  };
}

export type ReadAloudTry = ReturnType<typeof useReadAloudTry>;
