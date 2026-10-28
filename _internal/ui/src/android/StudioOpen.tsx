import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Clapperboard, Laptop } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { MotionPresence } from "@/shared/MotionPresence";
import type { ListenBook } from "@/listen/model";
import { Button, Dialog } from "@/shared/ui";
import { EbookLibrary, type StudioComputer } from "./plugins";

// "Mở Studio" của máy tính đã ghép trên điện thoại (StudioActivity.kt) - chẵn với nút cùng tên của máy tính (desktop/OtherComputers.tsx)
// và chip ở trang sách (desktop/App.tsx PeerStudioChipLink). Trang là của chính máy tính ấy; điện thoại chỉ chọn máy và trang.

/** Lời nói thẳng khi máy tính chỉ cho điện thoại nghe - cùng ý với trang "Chỉ nghe" của chính Studio (shared/peerStudio.ts listenOnlyLine), nhưng nói
 *  trước khi bấm, từ phía điện thoại. Nhiều máy cùng chỉ cho nghe: nêu tên cả hai; hơn hai máy thì nói chung "các máy tính đã ghép". Đường tới công tắc
 *  viết thẳng trong câu, đúng tên mục và công tắc hiện có (desktop/PhoneSync.tsx - soát a68 lỗi 12), cùng câu DeviceText bên native. */
export function studioListenOnlyLine(names: string | string[]): string {
  const list = typeof names === "string" ? [names] : names;
  if (list.length > 2) return `Các máy tính đã ghép đều chỉ cho nghe - trên từng máy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”.`;
  if (list.length === 2) return `Máy tính ${list[0]} và ${list[1]} đều chỉ cho nghe - trên từng máy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”.`;
  return `Máy tính ${list[0] ?? ""} chỉ cho nghe - trên máy tính ấy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”.`;
}

/** Máy tính còn mở Studio được (không phải máy chỉ cho nghe). */
function openable(computers: StudioComputer[]): StudioComputer[] {
  return computers.filter((computer) => !computer.listenOnly);
}

/** Bấm "Mở Studio": không có máy tính nào -> lời báo; một máy -> mở luôn; nhiều máy -> hỏi chọn theo tên. Máy chỉ cho nghe không nằm trong lựa chọn;
 *  còn mỗi máy như vậy thì nói vì sao thay vì mở một trang đóng. */
export function studioChoice(computers: StudioComputer[]): { open: StudioComputer } | { choose: StudioComputer[] } | { none: string } {
  if (computers.length === 0) return { none: "Chưa ghép với máy tính nào" };
  const usable = openable(computers);
  if (usable.length === 0) return { none: studioListenOnlyLine(computers.map((computer) => computer.name)) };
  return usable.length === 1 ? { open: usable[0] } : { choose: usable };
}

/** Hỏi các máy tính rồi mở hay đưa danh sách cho `choose` (hộp chọn máy). Lỗi thành thông báo. */
export async function startStudio(choose: (computers: StudioComputer[]) => void): Promise<void> {
  try {
    const choice = studioChoice((await EbookLibrary.studioComputers()).computers);
    if ("none" in choice) toast.error(choice.none);
    else if ("choose" in choice) choose(choice.choose);
    else await EbookLibrary.openStudio({ computer: choice.open.key });
  } catch (error) {
    toast.error((error as Error).message);
  }
}

/** Các máy tính để chọn, mỗi máy một dòng có tên. */
export function ComputerList({ computers, onPick }: { computers: StudioComputer[]; onPick: (computer: StudioComputer) => void }) {
  return (
    <ul className="divide-y divide-line">
      {computers.map((computer) => (
        <li key={computer.key}>
          <button type="button" onClick={() => onPick(computer)} className="flex w-full items-center gap-3 py-3 text-left">
            <Laptop className="size-5 shrink-0 text-fg-2" aria-hidden />
            <span className="min-w-0 flex-1 [overflow-wrap:anywhere] whitespace-normal font-medium">{computer.name}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Máy tính mở Studio được lúc này. Hỏi lại khi máy tính chính đổi (`connection`) và sau mỗi lượt hỏi thư viện thiết bị ghép
 *  (`peer-libraries`): máy ghép thêm chỉ được biết là máy tính sau khi nó trả lời lần đầu (Peers.kt rememberKind). */
export function useStudioComputers(book?: string): StudioComputer[] {
  return useStudioComputersQuery(book).data?.computers ?? [];
}

export function useStudioComputersQuery(book?: string) {
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const peers = useQuery({ queryKey: ["peer-libraries"], queryFn: () => EbookLibrary.peerLibraries(), retry: 0 });
  // Khoá đứng yên, hỏi lại khi hai nguồn trên có lượt trả lời mới. Đưa lượt trả lời vào khoá thì mỗi lần mở tab là một khoá mới chưa có dữ
  // liệu - tab Studio nháy khung chờ dù danh sách đã có từ lần trước.
  const computers = useQuery({
    queryKey: ["studio-computers", book ?? ""],
    queryFn: () => EbookLibrary.studioComputers(book ? { book } : undefined),
    placeholderData: keepPreviousData,
  });
  const version = `${connection.dataUpdatedAt}:${peers.dataUpdatedAt}`;
  const seen = useRef(version);
  const { refetch } = computers;
  useEffect(() => {
    if (seen.current === version) return;
    seen.current = version;
    void refetch();
  }, [version, refetch]);
  return computers;
}

export async function openStudioComputer(computer: StudioComputer): Promise<void> {
  try { await EbookLibrary.openStudio({ computer: computer.key }); }
  catch (error) { toast.error((error as Error).message); }
}

/** Nút "Mở Studio" ở tab Studio: chỉ có khi có ít nhất một máy tính mở được Studio (máy tính chính hay máy ghép thêm); hỏi máy
 *  nào khi có hơn một. */
export function OpenStudioButton({ computers, className }: { computers: StudioComputer[]; className?: string }) {
  const [choices, setChoices] = useState<StudioComputer[]>([]);
  if (computers.length === 0) return null;
  // Mọi máy tính đã ghép chỉ cho nghe: nút mờ kèm lý do, không bấm ra một trang đóng.
  if (openable(computers).length === 0) {
    return (
      <>
        <Button variant="ghost" icon={Clapperboard} className={className} disabled>
          Mở Studio
        </Button>
        <p className="mt-1.5 text-pretty text-xs text-fg-2">{studioListenOnlyLine(computers.map((computer) => computer.name))}</p>
      </>
    );
  }
  const pick = (computer: StudioComputer) => {
    setChoices([]);
    void openStudioComputer(computer);
  };
  return (
    <>
      <Button variant="ghost" icon={Clapperboard} className={className} onClick={() => void startStudio(setChoices)}>
        Mở Studio
      </Button>
      <Dialog open={choices.length > 0} onOpenChange={(open) => !open && setChoices([])} title="Mở Studio của máy nào?">
        <ComputerList computers={choices} onPick={pick} />
      </Dialog>
    </>
  );
}

/** Chip ở trang sách: cuốn đang làm ở máy tính đã ghép mở thẳng trong Studio của máy ấy. Cuốn không phải dự án Studio: không có gì.
 *  `computers`: các máy tính đã ghép (máy GIỮ cuốn này mang `holdsBook`); chip đi tới máy giữ cuốn nên mờ kèm lý do khi CHÍNH máy ấy chỉ cho nghe -
 *  còn mở được ở máy khác cũng vậy. Chưa biết máy nào giữ cuốn thì mờ khi mọi máy chỉ cho nghe, như nút "Mở Studio" ở tab Studio. */
export function StudioChip({ book, computers = [] }: { book: ListenBook; computers?: StudioComputer[] }) {
  if (!book.studio) return null;
  const holder = computers.find((computer) => computer.holdsBook);
  const blocked = holder ? holder.listenOnly === true : computers.length > 0 && openable(computers).length === 0;
  const reason = blocked ? studioListenOnlyLine(holder ? [holder.name] : computers.map((computer) => computer.name)) : "";
  // Danh sách máy về muộn: cùng một nút đổi độ mờ (không thay nút này bằng nút khác), dòng lý do mở / khép tại chỗ.
  return (
    <>
      <button
        type="button"
        disabled={blocked}
        title={reason || undefined}
        onClick={() => void EbookLibrary.openStudio({ book: book.id }).catch((error: Error) => toast.error(error.message))}
        className={cn("touch-hit font-semibold transition-opacity duration-motion-fast", blocked ? "opacity-60" : "underline underline-offset-2")}
      >
        Mở Studio
      </button>
      <MotionPresence className="basis-full" open={blocked}>
        <span className="text-pretty font-normal text-fg-2">{reason}</span>
      </MotionPresence>
    </>
  );
}

/** `StudioChip` cho app: hỏi các máy tính đã ghép để biết có máy nào còn mở Studio được. */
export function StudioChipHost({ book }: { book: ListenBook }) {
  const computers = useStudioComputers(book.id);
  return <StudioChip book={book} computers={computers} />;
}
