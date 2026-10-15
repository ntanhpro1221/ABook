import { useQuery } from "@tanstack/react-query";
import { Clapperboard, Laptop } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { ListenBook } from "@/listen/model";
import { Button, Dialog } from "@/shared/ui";
import { EbookLibrary, type StudioComputer } from "./plugins";

// "Mở Studio" của máy tính đã ghép trên điện thoại (StudioActivity.kt) - chẵn với nút cùng tên của máy tính (desktop/OtherComputers.tsx)
// và chip ở trang sách (desktop/App.tsx PeerStudioChipLink). Trang là của chính máy tính ấy; điện thoại chỉ chọn máy và trang.

/** Lời nói thẳng khi máy tính chỉ cho điện thoại nghe - cùng ý với trang "Chỉ nghe" của chính Studio (shared/peerStudio.ts listenOnlyLine), nhưng nói
 *  trước khi bấm, từ phía điện thoại. */
export function studioListenOnlyLine(name: string): string {
  return `Máy tính ${name} chỉ cho nghe - bật quyền sửa ở Cài đặt > Thiết bị trên máy tính`;
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
  if (usable.length === 0) return { none: studioListenOnlyLine(computers[0].name) };
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
    <ul className="divide-y divide-line rounded-xl border border-line">
      {computers.map((computer) => (
        <li key={computer.key}>
          <button type="button" onClick={() => onPick(computer)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
            <Laptop className="size-5 shrink-0 text-fg-2" aria-hidden />
            <span className="min-w-0 flex-1 truncate font-medium">{computer.name}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Máy tính mở Studio được lúc này. Hỏi lại khi máy tính chính đổi (`connection`) và sau mỗi lượt hỏi thư viện thiết bị ghép
 *  (`peer-libraries`): máy ghép thêm chỉ được biết là máy tính sau khi nó trả lời lần đầu (Peers.kt rememberKind). */
export function useStudioComputers(): StudioComputer[] {
  const connection = useQuery({ queryKey: ["connection"], queryFn: () => EbookLibrary.connection() });
  const peers = useQuery({ queryKey: ["peer-libraries"], queryFn: () => EbookLibrary.peerLibraries(), retry: 0 });
  const computers = useQuery({
    queryKey: ["studio-computers", connection.dataUpdatedAt, peers.dataUpdatedAt],
    queryFn: () => EbookLibrary.studioComputers(),
  });
  return computers.data?.computers ?? [];
}

/** Nút "Mở Studio" ở màn Tải sách: chỉ có khi có ít nhất một máy tính mở được Studio (máy tính chính hay máy ghép thêm); hỏi máy
 *  nào khi có hơn một. */
export function OpenStudioButton({ computers, className }: { computers: StudioComputer[]; className?: string }) {
  const [choices, setChoices] = useState<StudioComputer[]>([]);
  if (computers.length === 0) return null;
  // Mọi máy tính đã ghép chỉ cho nghe: nút mờ kèm lý do, không bấm ra một trang đóng.
  if (openable(computers).length === 0) {
    return (
      <>
        <Button variant="secondary" icon={Clapperboard} className={className} disabled>
          Mở Studio
        </Button>
        <p className="mt-1.5 text-pretty text-xs text-fg-2">{studioListenOnlyLine(computers[0].name)}</p>
      </>
    );
  }
  const pick = (computer: StudioComputer) => {
    setChoices([]);
    void EbookLibrary.openStudio({ computer: computer.key }).catch((error: Error) => toast.error(error.message));
  };
  return (
    <>
      <Button variant="secondary" icon={Clapperboard} className={className} onClick={() => void startStudio(setChoices)}>
        Mở Studio
      </Button>
      <Dialog open={choices.length > 0} onOpenChange={(open) => !open && setChoices([])} title="Mở Studio của máy nào?">
        <ComputerList computers={choices} onPick={pick} />
      </Dialog>
    </>
  );
}

/** Chip ở trang sách: cuốn đang làm ở máy tính đã ghép mở thẳng trong Studio của máy ấy. Cuốn không phải dự án Studio: không có gì. */
export function StudioChip({ book }: { book: ListenBook }) {
  if (!book.studio) return null;
  return (
    <button
      type="button"
      onClick={() => void EbookLibrary.openStudio({ book: book.id }).catch((error: Error) => toast.error(error.message))}
      className="font-semibold underline underline-offset-2"
    >
      Mở Studio
    </button>
  );
}
