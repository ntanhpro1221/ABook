import { cn } from "@/shared/cn";
import { useLayoutEffect, useRef, useState } from "react";
import { coverColor, coverLabel, coverStyle, splitTitle, type CoverImage } from "@/shared/cover";
import { Vu } from "@/shared/ui";
import { MotionRegion } from "./MotionRegion";

// Bìa kiểu album sách nói, hoặc bìa dọc ở kệ. Bìa vẽ cao thêm theo chữ. Hoạ tiết là các vòng sóng âm lan ra từ góc - thứ duy nhất sách TXT
// "có" là giọng đọc, nên bìa vẽ giọng đọc.
//
// Bìa nhỏ (thanh phát, danh sách) không đủ chỗ cho tên: sách trong một bộ thì số tập là thứ phân biệt được các
// cuốn ("16", "18"), không phải hai chữ cái đầu giống hệt nhau của tên bộ.

export function BookCover({
  title,
  size = "md",
  playing = false,
  image,
  part,
  badge,
  label = true,
  portrait = false,
  className,
}: {
  title: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  playing?: boolean;
  /** Ảnh bìa thật; ảnh không tải được thì quay về bìa vẽ, không để ô trống. */
  image?: CoverImage | null;
  /** Thứ tự phần trong chuỗi "Làm tiếp cuốn này" - phần đổi tên vẫn ghi "Phần N" (cover.splitTitle). */
  part?: number | null;
  /** Nhãn tập khi tên sách không mang số ("Tập 1" của cuốn không số trong một bộ) - chỉ dùng khi tên và `part` không cho nhãn. */
  badge?: string;
  /** Bìa nhỏ: false = chỉ hoạ tiết, không chữ - thanh phát thu gọn đã ghi tên sách ngay cạnh, hai chữ cái đầu ("CP") trông như ảnh đại diện
   *  chứ không phải bìa (soát a66). */
  label?: boolean;
  /** Bìa dọc ở kệ; bìa vẽ vẫn cao thêm nếu tên cần nhiều dòng hơn. */
  portrait?: boolean;
  className?: string;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  // Bìa ảnh và bìa vẽ là hai cây khác nhau: một gốc MotionRegion cho cả hai, khoá theo ảnh đang hiện + tên. Đổi cuốn (thanh phát), ảnh lỗi rơi
  // về bìa vẽ, hay bìa vẽ đổi màu theo tên thì mờ chéo, không thay tức thì.
  const photo = image?.url && failed !== image.url ? image : null;
  const motionKey = [photo?.url ?? null, title, part ?? null, badge ?? null];
  const ratio = portrait ? "aspect-[2/3]" : "aspect-square";
  if (photo) {
    return (
      <MotionRegion
        motionKey={motionKey}
        className={cn("relative shrink-0 self-start overflow-hidden rounded-control shadow-card", ratio, className)}
        style={{ backgroundColor: coverColor(photo.color) || "var(--color-hover)" }}
        aria-hidden
      >
        <PhotoCover image={photo} playing={playing} onError={() => setFailed(photo.url)} />
      </MotionRegion>
    );
  }
  const style = coverStyle(title);
  const [main, titled] = splitTitle(title, part);
  const sub = titled || badge || "";
  const small = size === "xs" || size === "sm";
  // Chữ và lề của bìa vẽ co theo CHIỀU RỘNG bìa (đơn vị cqw của khung `@container` bên dưới), có sàn và trần theo cỡ: cùng cỡ "md" mà
  // ô 80 px (thẻ "Đang nghe dở") và ô 178 px (kệ sách) đều vừa chữ, không cắt tên giữa chừng hay đè nhãn tập (soát UX 05-10).
  const text = {
    xs: { fontSize: 0, padding: 4 },
    sm: { fontSize: 0, padding: 6 },
    md: { fontSize: "clamp(11px, 14cqw, 15px)", padding: "clamp(6px, 8cqw, 14px)" },
    lg: { fontSize: "clamp(11px, 14cqw, 19px)", padding: "clamp(6px, 9cqw, 16px)" },
    xl: { fontSize: "clamp(12px, 10cqw, 24px)", padding: "clamp(8px, 7cqw, 20px)" },
  }[size];
  const leading = { xs: "", sm: "", md: "leading-[1.15]", lg: "leading-[1.12]", xl: "leading-[1.1]" }[size];
  const rings = [0.28, 0.46, 0.64, 0.82, 1.0];
  return (
    <MotionRegion
      motionKey={motionKey}
      className={cn("@container relative shrink-0 self-start overflow-hidden rounded-control text-left shadow-card", small ? ratio : "grid grid-cols-[minmax(0,1fr)]", className)}
      style={{ background: `linear-gradient(155deg, ${style.from} 0%, ${style.to} 100%)`, height: small ? undefined : "auto" }}
      data-overlay="Chữ bìa trên hoạ tiết sóng"
      aria-hidden
    >
      <svg className="absolute inset-0 size-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        {rings.map((radius, index) => (
          <circle
            key={radius}
            cx={style.seed % 2 ? 100 : 0}
            cy={100}
            r={radius * 100}
            fill="none"
            stroke={style.ink}
            strokeOpacity={0.09 + index * 0.025}
            strokeWidth={0.6}
          />
        ))}
      </svg>
      {!small && <span className={cn("col-start-1 row-start-1 w-full", ratio)} />}
      <div className={cn("relative flex min-w-0 w-full flex-col justify-between gap-1", small ? "h-full" : "col-start-1 row-start-1")} style={{ padding: text.padding }}>
        {small ? (
          label && (
            <span
              className="m-auto font-bold leading-none tracking-tight"
              style={{ color: style.ink, fontSize: size === "xs" ? 12 : 17 }}
            >
              {titled || !badge ? coverLabel(title, part) : (badge.match(/\d+/)?.[0] ?? coverLabel(title, part))}
            </span>
          )
        ) : (
          <>
            {/* Bìa vẽ cao thêm theo tên sách, giữ cỡ chữ và chuyển động chung. */}
            <span
              className={cn("[overflow-wrap:anywhere] whitespace-normal font-bold tracking-tight text-cover-ink", leading)}
              style={{ fontSize: text.fontSize }}
            >
              {main}
            </span>
            {sub ? (
              <span
                className="shrink-0 self-start rounded-control px-1.5 py-0.5 font-semibold uppercase tracking-wider"
                style={{ color: style.ink, background: "rgb(0 0 0 / 0.28)", fontSize: "clamp(8px, 6cqw, 11px)" }}
              >
                {sub}
              </span>
            ) : (
              <span />
            )}
          </>
        )}
      </div>
      <MotionRegion as="span" className="absolute bottom-1.5 right-1.5" style={{ color: style.ink }}>
        {playing && <span className="grid place-items-center rounded-control bg-cover-overlay px-1 py-0.5"><Vu className="h-3" /></span>}
      </MotionRegion>
    </MotionRegion>
  );
}

/**
 * Lớp trong của bìa là ảnh thật (khung MotionRegion do BookCover dựng chung với bìa vẽ). Khung luôn vuông như bìa album; bìa sách thường dọc (2:3) nên không cắt mất tên ở trên - đặt trọn
 * ảnh ở giữa, hai bên là chính ảnh ấy phóng to và làm mờ, cách các app sách nói vẫn làm.
 */
function PhotoCover({
  image,
  playing,
  onError,
}: {
  image: CoverImage;
  playing: boolean;
  onError: () => void;
}) {
  const ratio = image.width && image.height ? image.width / image.height : 1;
  const square = Math.abs(ratio - 1) < 0.08;
  // Ảnh lười (loading=lazy) tải xong thì hiện dần trên nền màu chủ đạo, không bật ra đột ngột. Ảnh đã có sẵn (bộ đệm) thì hiện ngay từ khung
  // đầu: kiểm `complete` trước khi vẽ, nên không mờ lại những bìa đã thấy.
  const main = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState<string | null>(null);
  useLayoutEffect(() => {
    const element = main.current;
    if (element?.complete && element.naturalWidth > 0) setLoaded(image.url);
  }, [image.url]);
  const shown = loaded === image.url;
  return (
    <>
      {!square && (
        // Nền mờ cần một bản ảnh thứ hai (cùng địa chỉ nên trình duyệt chỉ tải một lần); lười như ảnh chính - kệ 160 bìa không tải cả 320 ảnh ngay lúc vẽ.
        <img src={image.url} width={image.width ?? 1} height={image.height ?? 1} alt="" draggable={false} loading="lazy" decoding="async" className={cn("absolute inset-0 size-full scale-125 object-cover blur-xl transition-opacity duration-motion-medium", shown ? "opacity-60" : "opacity-0")} />
      )}
      <img
        ref={main}
        src={image.url}
        width={image.width ?? 1}
        height={image.height ?? 1}
        alt=""
        draggable={false}
        loading="lazy"
        decoding="async"
        onLoad={() => setLoaded(image.url)}
        onError={onError}
        data-loaded={shown || undefined}
        className={cn("relative size-full transition-opacity duration-motion-medium", square ? "object-cover" : "object-contain", shown ? "opacity-100" : "opacity-0")}
      />
      <MotionRegion as="span" className="absolute bottom-1.5 right-1.5 text-cover-ink">
        {playing && <span className="grid place-items-center rounded-control bg-cover-overlay px-1 py-0.5"><Vu className="h-3" /></span>}
      </MotionRegion>
    </>
  );
}
