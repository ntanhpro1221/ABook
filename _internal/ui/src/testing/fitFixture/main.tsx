// Trang đo thật trên Chromium cho chữ tự đo (OneLineFit / FitBox) trong nút và bìa dùng chung: scripts/one_line_fit_browser.test.mjs dựng trang này
// bằng vite (cùng Tailwind, cùng phông app) rồi đo hình học. "#rows=N": danh sách N hàng file như màn Dự án mới (content-visibility, hai OneLineFit
// mỗi hàng) để đo thời gian gắn (soát leftfix T6).
import { BookOpen, Play } from "lucide-react";
import { StrictMode, useEffect, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BookCover } from "@/shared/BookCover";
import { OneLineFit } from "@/shared/OneLineFit";
import { Button } from "@/shared/ui";
import "./fixture.css";

const LONG_CHAPTER = "Nghe tiếp · Chương 1287: Trên đỉnh núi tuyết, người thiếu niên mang thanh kiếm gãy gặp lại cố nhân sau mười năm xa cách";
const SLIGHTLY_LONG = "Nghe tiếp · Chương 12: Gặp lại cố nhân ở bến";
const LONG_TITLE = "Chuyển sinh thành kiếm sĩ hạng bét nhưng được hệ thống ban cho kỹ năng vô hạn ở dị giới đầy rẫy quái vật và những âm mưu cung đình";

function Buttons() {
  return (
    <div style={{ width: 320, padding: 16 }} className="flex flex-col gap-3">
      {/* Nút chính của trang sách (BookScreen): đúng lớp của nơi gọi. */}
      <Button data-case="primary-long" variant="primary" size="lg" icon={Play} className="h-auto min-w-0 max-w-full py-2 max-sm:w-full">
        <OneLineFit className="min-w-0 text-left">{LONG_CHAPTER}</OneLineFit>
      </Button>
      {/* Nút chung KHÔNG có lớp nới của nơi gọi: tự cao thêm khi chữ xuống dòng. */}
      <Button data-case="plain-long" size="md" icon={BookOpen}>
        <OneLineFit className="text-left">{LONG_CHAPTER}</OneLineFit>
      </Button>
      <Button data-case="plain-slight" size="md" icon={BookOpen}>
        <OneLineFit className="text-left">{SLIGHTLY_LONG}</OneLineFit>
      </Button>
      <Button data-case="plain-short" size="md" icon={BookOpen}>
        <OneLineFit className="text-left">{"Nghe tiếp"}</OneLineFit>
      </Button>
    </div>
  );
}

function Covers() {
  return (
    <div className="flex items-start gap-4 p-4">
      <div data-case="cover-md"><BookCover title={LONG_TITLE} size="md" className="w-20" /></div>
      <div data-case="cover-lg"><BookCover title={LONG_TITLE} size="lg" className="w-[120px]" /></div>
      <div data-case="cover-xl"><BookCover title={LONG_TITLE} size="xl" className="w-[178px]" /></div>
      <div data-case="cover-short"><BookCover title={"Mưa"} size="md" className="w-20" /></div>
    </div>
  );
}

function Rows({ count }: { count: number }) {
  const rows = Array.from({ length: count }, (_, i) => i);
  return (
    <div data-rows style={{ width: 360 }}>
      {rows.map((i) => (
        <div key={i} data-row={i} className="grid grid-cols-[auto_minmax(0,1fr)_90px] items-center gap-2 px-3 py-2 [contain-intrinsic-size:auto_48px] [content-visibility:auto]">
          <span className="text-xs">{i + 1}</span>
          <div className="min-w-0">
            <OneLineFit className="text-sm font-medium">{`Chương ${i + 1}: ${i % 3 ? "Gặp lại cố nhân" : "Trên đỉnh núi tuyết người thiếu niên mang thanh kiếm gãy"}`}</OneLineFit>
            <OneLineFit className="text-xs">{`chuong-${String(i + 1).padStart(4, "0")}-tren-dinh-nui-tuyet.txt`}</OneLineFit>
          </div>
          <span className="text-xs">1.234 chữ</span>
        </div>
      ))}
    </div>
  );
}

const rows = /rows=(\d+)/.exec(location.hash)?.[1];
const started = performance.now();

/** Thời gian từ lúc gắn tới khung vẽ đầu sau lần commit (mọi lần đo chữ - đồng bộ trong layout effect hay theo lô trong vi tác vụ - chạy trước đó). */
function Timed({ children }: { children: ReactNode }) {
  useEffect(() => {
    requestAnimationFrame(() => {
      (window as unknown as { __mountMs: number }).__mountMs ??= performance.now() - started;
      void document.fonts.ready.then(() => requestAnimationFrame(() => requestAnimationFrame(() => { (window as unknown as { __ready: boolean }).__ready = true; })));
    });
  }, []);
  return children;
}
const host = document.getElementById("root")!;
createRoot(host).render(
  <StrictMode>
    <Timed>{rows ? <Rows count={Number(rows)} /> : <><Buttons /><Covers /></>}</Timed>
  </StrictMode>,
);
