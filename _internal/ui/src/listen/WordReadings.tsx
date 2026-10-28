import { MotionRegion } from "@/shared/MotionRegion";
import { useBackLayer } from "@/shared/backStack";
import { Pause, Pencil, Trash2, Volume2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { Button, Dialog, IconButton, ContentSkeleton, InlineError } from "@/shared/ui";
import {
  cleanSpoken,
  MAX_PHRASE_WORDS,
  phraseKey,
  pickWord,
  readingFor,
  sentenceTokens,
  useBookReadings,
  useReadAloudTry,
  useSaveReading,
  wordCore,
  type BookReading,
  type PhraseSelection,
  type ReadAloudTry,
} from "./readings";
import { cn } from "@/shared/cn";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { useAppInfo } from "@/studio/data";
import { UNDO_MS } from "@/studio/decisions";

// "Đọc từ này là…" (giữ / bấm chuột phải vào một chữ ở màn đọc của cuốn chỉ có chữ) và danh sách "Cách đọc tên" của hộp "Sửa sách": dạy
// giọng đọc một từ hay một cụm chữ liền nhau cho cả cuốn. Chỉ giọng đọc đổi, chữ của sách giữ nguyên (listen/readings.ts).

/** Nút "Nghe thử" bằng giọng đang đọc cuốn này. */
function TryButton({ aloud, surface, spoken }: { aloud: ReadAloudTry; surface: string; spoken: string }) {
  if (!aloud.available) return null;
  const playing = aloud.playing(surface, spoken);
  return (
    <Button
      size="sm"
      type="button"
      loading={aloud.loading(surface, spoken)}
      onClick={() => void aloud.play(surface, spoken)}
      aria-label={playing ? "Dừng nghe thử" : `Nghe thử ${surface}${cleanSpoken(spoken) ? ` đọc là ${cleanSpoken(spoken)}` : ""}`}
    >
      {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Volume2 className="size-4" strokeWidth={2} />}
      {playing ? "Dừng" : "Nghe thử"}
    </Button>
  );
}

/** Ô cách đọc của một từ + "Nghe thử" + "Lưu cho cả cuốn" (+ "Đọc như chữ trong sách" khi từ đã có cách đọc riêng). */
function ReadingForm({ bookId, surface, current, aloud, onDone }: {
  bookId: string;
  surface: string;
  current: string;
  aloud: ReadAloudTry;
  onDone: () => void;
}) {
  const [value, setValue] = useState(current);
  useEffect(() => setValue(current), [current, surface]);
  const save = useSaveReading(bookId);
  const typed = cleanSpoken(value);
  // Đoạn đang đọc nói nốt cách cũ; từ đoạn sau (và khi nghe lại) mới là cách mới - nói đúng thế. Hoàn tác đặt lại đúng cách đọc trước đó (soát a70).
  const store = (spoken: string) =>
    save.mutate(
      { surface, spoken },
      {
        onSuccess: () => {
          toast.success(spoken ? `“${surface}” sẽ đọc là “${cleanSpoken(spoken)}” từ đoạn sau` : `“${surface}” đọc lại như chữ trong sách từ đoạn sau`, {
            id: "reading-saved",
            duration: UNDO_MS,
            action: {
              label: "Hoàn tác",
              onClick: () =>
                save.mutate(
                  { surface, spoken: current },
                  {
                    onSuccess: () => toast.success(current ? `Đã hoàn tác: “${surface}” lại đọc là “${current}”` : `Đã hoàn tác: “${surface}” lại đọc như chữ trong sách`, { id: "reading-saved" }),
                    onError: (error) => toast.error("Không hoàn tác được", { description: (error as Error).message }),
                  },
                ),
            },
          });
          onDone();
        },
        onError: (error) => toast.error("Chưa lưu được cách đọc", { description: (error as Error).message }),
      },
    );
  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (typed && typed !== current) store(typed);
      }}
    >
      <p className="text-xs text-fg-2">
        <span className="font-semibold text-fg">“{surface}”</span> đọc là
      </p>
      <input
        autoFocus
        data-autofocus
        value={value}
        maxLength={200}
        onChange={(event) => setValue(event.target.value)}
        placeholder="vd Ha-ru-tô"
        aria-label={`Cách đọc cho ${surface}`}
        spellCheck={false}
        autoComplete="off"
        className="h-10 w-full rounded-control border border-line bg-bg px-3 text-sm outline-none focus:border-focus"
      />
      <div className="flex flex-wrap items-center gap-2">
        <TryButton aloud={aloud} surface={surface} spoken={value} />
        <Button size="sm" variant="primary" type="submit" loading={save.isPending && Boolean(typed)} disabled={!typed || typed === current || typed === surface}>
          Lưu cho cả cuốn
        </Button>
        {current && (
          <Button size="sm" variant="ghost" type="button" disabled={save.isPending} onClick={() => store("")}>
            Đọc như chữ trong sách
          </Button>
        )}
      </div>
      {aloud.failed && <p role="status" className="text-xs text-danger text-pretty">{aloud.failed}</p>}
    </form>
  );
}

/** Hộp "Đọc từ này là…": `word` là chữ người nghe vừa giữ (đã bỏ dấu câu hai đầu), "" khi mở từ nút “Sửa cách đọc” mà chưa chọn chữ nào; null = đóng.
 *  `sentence`: câu chứa chữ ấy - có thì hiện từng chữ của câu để chọn: bấm một chữ, rồi bấm thêm một chữ liền kề để đọc cả CỤM (tối đa 6 chữ, như "Hạ Vy").
 *  `wordIndex`: thứ tự chữ vừa giữ trong câu (không có thì lấy chữ đầu tiên trùng `word`). */
export function WordReadingDialog({ bookId, word, sentence, wordIndex, onClose }: { bookId: string; word: string | null; sentence?: string; wordIndex?: number; onClose: () => void }) {
  const readings = useBookReadings(bookId, word !== null);
  const aloud = useReadAloudTry(bookId);
  const tokens = useMemo(() => (sentence ? sentenceTokens(sentence) : []), [sentence]);
  const [picked, setPicked] = useState<PhraseSelection | null>(null);
  // "Nối thành cụm": chữ bấm kế tiếp mở rộng cụm tới chữ ấy (không thì bấm chữ nào cũng chỉ chọn riêng chữ đó - bấm nhầm không làm thành cụm, bố cục không nhảy).
  const [joining, setJoining] = useState(false);
  const joinBox = useRef<HTMLDivElement>(null);
  const joinButton = useRef<HTMLButtonElement>(null);
  useBackLayer(word !== null && joining, () => setJoining(false), joinBox, joinButton);
  useEffect(() => {
    setJoining(false);
    const held = word ? wordCore(word) : "";
    const at = wordIndex !== undefined && tokens[wordIndex]?.core === held ? wordIndex : tokens.findIndex((token) => token.core === held);
    setPicked(held && at >= 0 ? { from: at, to: at } : null);
  }, [word, sentence, wordIndex, tokens]);
  const phrase = picked ? phraseKey(tokens, picked.from, picked.to) : null;
  const surface = phrase ?? (!tokens.length && word ? wordCore(word) : "");
  const chips = tokens.filter((token) => token.core).length;
  const single = Boolean(picked && picked.from === picked.to);
  return (
    <Dialog
      open={word !== null && (Boolean(surface) || chips > 0)}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title="Đọc từ này là"
      description={
        surface ? (
          <>
            Gõ cách đọc cho <span className="font-semibold text-fg">“{surface}”</span> - mọi chỗ có đúng {surface.includes(" ") ? "cụm" : "từ"} này (đúng chữ hoa, chữ
            thường) trong cuốn sẽ đọc như vậy. Chữ trong sách giữ nguyên.
          </>
        ) : (
          "Chọn từ máy đọc sai (thường là tên riêng), rồi gõ cách đọc đúng. Áp cho cả cuốn; chữ trong sách giữ nguyên."
        )
      }
    ><MotionRegion>
      {chips > 1 && (
        <div ref={joinBox} className="mb-3">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Các từ trong câu">
            {tokens.map((token, at) =>
              token.core ? (
                <button
                  key={at}
                  type="button"
                  aria-pressed={Boolean(picked && at >= picked.from && at <= picked.to)}
                  onClick={() => {
                    setPicked(pickWord(tokens, picked, at, joining));
                    setJoining(false);
                  }}
                  className={cn(
                    "touch-row inline-flex min-h-10 items-center px-2.5 text-sm",
                    picked && at >= picked.from && at <= picked.to ? "text-accent-text underline underline-offset-4" : "text-fg-2 hover:bg-hover",
                  )}
                >
                  {token.core}
                </button>
              ) : null,
            )}
          </div>
          {/* Hàng này luôn cao một dòng (nút hay chữ): chọn chữ khác không làm các chip phía trên xê dịch. */}
          <div className="mt-1.5 flex min-h-8 flex-wrap items-center gap-x-2 text-xs text-fg-2">
            {single && !joining ? (
              <>
                <span>Tên có nhiều chữ (vd “Hạ Vy”)?</span>
                <Button ref={joinButton} size="sm" variant="ghost" type="button" onClick={() => setJoining(true)}>
                  Nối thành cụm
                </Button>
              </>
            ) : joining ? (
              <>
                <span className="text-pretty">Bấm chữ cuối của cụm - tối đa {MAX_PHRASE_WORDS} chữ liền nhau, không có dấu câu ở giữa.</span>
                <Button size="sm" variant="ghost" type="button" onClick={() => setJoining(false)}>
                  Thôi
                </Button>
              </>
            ) : (
              <span>{picked ? "Bấm một chữ để chọn lại từ đầu." : "Bấm một chữ để chọn."}</span>
            )}
          </div>
        </div>
      )}
      {surface && <ReadingForm key={surface} bookId={bookId} surface={surface} current={readingFor(readings.data, surface)} aloud={aloud} onDone={onClose} />}
    </MotionRegion></Dialog>
  );
}

/** "Cách đọc tên" trong hộp "Sửa sách" (cuốn chỉ có chữ): các từ đã dạy giọng đọc, sửa / nghe thử / bỏ từng từ. */
export function BookReadingsSection({ bookId }: { bookId: string }) {
  const readings = useBookReadings(bookId);
  const aloud = useReadAloudTry(bookId);
  const save = useSaveReading(bookId);
  const [editing, setEditing] = useState<string | null>(null);
  const editBox = useRef<HTMLUListElement>(null);
  useBackLayer(editing !== null, () => setEditing(null), editBox);
  const list: BookReading[] = readings.data ?? [];
  // Thiết bị chỉ được nghe: xem danh sách được, sửa / bỏ thì làm ở máy tính (nút bấm vào chỉ ra 403).
  const { data: info } = useAppInfo();
  const listenOnly = Boolean(info?.listenOnly);
  // Không đọc được danh sách thì nói thẳng - đừng bảo "chưa có từ nào" khi chỉ là chưa lấy được.
  if (readings.isError && !readings.data) return <MotionRegion fadeThrough><InlineError message="Bạn hãy thử tải lại danh sách cách đọc." onRetry={() => void readings.refetch()} /></MotionRegion>;
  if (readings.isPending) return <MotionRegion fadeThrough><ContentSkeleton count={2} label="Đang tải cách đọc" /></MotionRegion>;
  if (!list.length && listenOnly) return <MotionRegion as="p" className="text-xs text-fg-2">Chưa có từ nào.</MotionRegion>;
  if (!list.length) {
    return <MotionRegion as="p" className="text-xs text-fg-2">Chưa có từ nào. Ở màn đọc, giữ (hay bấm chuột phải) vào một từ đọc sai rồi chọn cách đọc.</MotionRegion>;
  }
  return (
    <MotionRegion as="ul" elementRef={editBox} className="divide-y divide-line">
      {list.map((item) => (
        <li key={item.surface} className="py-2">
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 [overflow-wrap:anywhere] whitespace-normal text-sm">
              <span className="font-semibold">{item.surface}</span>
              <span className="text-fg-2"> đọc là </span>
              <span>“{item.spoken}”</span>
            </span>
            {aloud.available && (
              <IconButton
                size="sm"
                label={aloud.playing(item.surface, item.spoken) ? "Dừng nghe thử" : `Nghe thử ${item.surface}`}
                icon={aloud.playing(item.surface, item.spoken) ? Pause : Volume2}
                onClick={() => void aloud.play(item.surface, item.spoken)}
              />
            )}
            {!listenOnly && <IconButton size="sm" label={`Sửa cách đọc ${item.surface}`} icon={Pencil} onClick={() => setEditing(editing === item.surface ? null : item.surface)} />}
            {!listenOnly && (
              <IconButton
                size="sm"
                label={`Bỏ cách đọc ${item.surface}`}
                icon={Trash2}
                disabled={save.isPending}
                onClick={() =>
                  save.mutate(
                    { surface: item.surface, spoken: "" },
                    { onError: (error) => toast.error("Chưa bỏ được cách đọc", { description: (error as Error).message }) },
                  )
                }
              />
            )}
          </div>
          {editing === item.surface && (
            <div className="mt-2">
              <ReadingForm bookId={bookId} surface={item.surface} current={item.spoken} aloud={aloud} onDone={() => setEditing(null)} />
            </div>
          )}
        </li>
      ))}
      {aloud.failed && editing === null && <li className="px-3 py-2 text-xs text-danger">{aloud.failed}</li>}
      {listenOnly && (
        <li className="px-3 py-2">
          <OnComputerOnly verb="Sửa cách đọc" />
        </li>
      )}
    </MotionRegion>
  );
}
