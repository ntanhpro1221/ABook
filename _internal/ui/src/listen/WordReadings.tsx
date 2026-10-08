import { Pause, Pencil, Trash2, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button, Dialog, IconButton } from "@/shared/ui";
import { cleanSpoken, readingFor, sentenceWords, useBookReadings, useReadAloudTry, useSaveReading, wordCore, type BookReading, type ReadAloudTry } from "./readings";
import { cn } from "@/shared/cn";

// "Đọc từ này là…" (giữ / bấm chuột phải vào một chữ ở màn đọc của cuốn chỉ có chữ) và danh sách "Cách đọc tên" của hộp "Sửa sách": dạy
// giọng đọc một từ cho cả cuốn. Chỉ giọng đọc đổi, chữ của sách giữ nguyên (listen/readings.ts).

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
  const store = (spoken: string) =>
    save.mutate(
      { surface, spoken },
      {
        onSuccess: () => {
          toast.success(spoken ? `“${surface}” sẽ đọc là “${cleanSpoken(spoken)}”` : `“${surface}” đọc lại như chữ trong sách`, {
            description: "Áp cho cả cuốn; đoạn đã đọc sẵn đổi từ lần nghe sau.",
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
        className="h-10 w-full rounded-lg border border-line bg-bg px-3 text-sm outline-none focus:border-accent"
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
 *  `sentence`: câu chứa chữ ấy - có thì hiện các từ của câu để chọn / đổi từ muốn sửa (đường “Sửa cách đọc” ở menu câu). */
export function WordReadingDialog({ bookId, word, sentence, onClose }: { bookId: string; word: string | null; sentence?: string; onClose: () => void }) {
  const readings = useBookReadings(bookId, word !== null);
  const aloud = useReadAloudTry(bookId);
  const [picked, setPicked] = useState<string | null>(null);
  useEffect(() => setPicked(null), [word, sentence]);
  const surface = picked ?? (word ? wordCore(word) : "");
  const words = sentence ? sentenceWords(sentence) : [];
  return (
    <Dialog
      open={word !== null && (Boolean(surface) || words.length > 0)}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title="Đọc từ này là…"
      description={
        surface ? (
          <>
            Gõ cách đọc cho <span className="font-semibold text-fg">“{surface}”</span> - mọi chỗ có đúng từ này (đúng chữ hoa, chữ thường) trong cuốn
            sẽ đọc như vậy. Chữ trong sách giữ nguyên.
          </>
        ) : (
          "Chọn từ máy đọc sai (thường là tên riêng), rồi gõ cách đọc đúng. Áp cho cả cuốn; chữ trong sách giữ nguyên."
        )
      }
    >
      {words.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Các từ trong câu">
          {words.map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={surface === item}
              onClick={() => setPicked(item)}
              className={cn(
                "inline-flex h-8 items-center rounded-full border px-2.5 text-sm pointer-coarse:h-10",
                surface === item ? "border-accent bg-accent-soft text-accent-text" : "border-line hover:bg-hover",
              )}
            >
              {item}
            </button>
          ))}
        </div>
      )}
      {surface && <ReadingForm key={surface} bookId={bookId} surface={surface} current={readingFor(readings.data, surface)} aloud={aloud} onDone={onClose} />}
    </Dialog>
  );
}

/** "Cách đọc tên" trong hộp "Sửa sách" (cuốn chỉ có chữ): các từ đã dạy giọng đọc, sửa / nghe thử / bỏ từng từ. */
export function BookReadingsSection({ bookId }: { bookId: string }) {
  const readings = useBookReadings(bookId);
  const aloud = useReadAloudTry(bookId);
  const save = useSaveReading(bookId);
  const [editing, setEditing] = useState<string | null>(null);
  const list: BookReading[] = readings.data ?? [];
  if (!list.length) {
    return <p className="text-xs text-fg-2">Chưa có từ nào. Ở màn đọc, giữ (hay bấm chuột phải) vào một từ đọc sai rồi chọn cách đọc.</p>;
  }
  return (
    <ul className="divide-y divide-line rounded-lg border border-line">
      {list.map((item) => (
        <li key={item.surface} className="px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-sm">
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
            <IconButton size="sm" label={`Sửa cách đọc ${item.surface}`} icon={Pencil} onClick={() => setEditing(editing === item.surface ? null : item.surface)} />
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
          </div>
          {editing === item.surface && (
            <div className="mt-2">
              <ReadingForm bookId={bookId} surface={item.surface} current={item.spoken} aloud={aloud} onDone={() => setEditing(null)} />
            </div>
          )}
        </li>
      ))}
      {aloud.failed && editing === null && <li className="px-3 py-2 text-xs text-danger">{aloud.failed}</li>}
    </ul>
  );
}
