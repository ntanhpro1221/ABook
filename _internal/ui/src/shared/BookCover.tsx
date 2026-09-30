import { cn } from "@/shared/cn";
import { useState } from "react";
import { coverLabel, coverStyle, splitTitle, type CoverImage } from "@/shared/cover";
import { Vu } from "@/shared/ui";

// Bìa vuông kiểu album sách nói. Hoạ tiết là các vòng sóng âm lan ra từ góc - thứ duy nhất sách TXT
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
  className,
}: {
  title: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  playing?: boolean;
  /** Ảnh bìa thật; ảnh không tải được thì quay về bìa vẽ, không để ô trống. */
  image?: CoverImage | null;
  /** Thứ tự phần trong chuỗi "Làm tiếp cuốn này" - phần đổi tên vẫn ghi "Phần N" (cover.splitTitle). */
  part?: number | null;
  className?: string;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  if (image?.url && failed !== image.url) {
    return <PhotoCover image={image} playing={playing} className={className} onError={() => setFailed(image.url)} />;
  }
  const style = coverStyle(title);
  const [main, sub] = splitTitle(title, part);
  const small = size === "xs" || size === "sm";
  const text = {
    xs: "",
    sm: "",
    md: "text-[15px] leading-[1.15]",
    lg: "text-[19px] leading-[1.12]",
    xl: "text-[24px] leading-[1.1]",
  }[size];
  const pad = { xs: "p-1", sm: "p-1.5", md: "p-3.5", lg: "p-4", xl: "p-5" }[size];
  const rings = [0.28, 0.46, 0.64, 0.82, 1.0];
  return (
    <div
      className={cn("relative aspect-square shrink-0 overflow-hidden rounded-lg text-left shadow-card", className)}
      style={{ background: `linear-gradient(155deg, ${style.from} 0%, ${style.to} 100%)` }}
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
      <div className={cn("relative flex h-full flex-col justify-between", pad)}>
        {small ? (
          <span
            className="m-auto font-bold leading-none tracking-tight"
            style={{ color: style.ink, fontSize: size === "xs" ? 12 : 17 }}
          >
            {coverLabel(title, part)}
          </span>
        ) : (
          <>
            <span className={cn("line-clamp-4 font-bold tracking-tight text-white", text)}>{main}</span>
            {sub ? (
              <span
                className="self-start rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider"
                style={{ color: style.ink, background: "rgb(0 0 0 / 0.28)" }}
              >
                {sub}
              </span>
            ) : (
              <span />
            )}
          </>
        )}
      </div>
      {playing && (
        <span className="absolute bottom-1.5 right-1.5 grid place-items-center rounded-md bg-black/45 px-1 py-0.5" style={{ color: style.ink }}>
          <Vu className="h-3" />
        </span>
      )}
    </div>
  );
}

/**
 * Bìa là ảnh thật. Khung luôn vuông như bìa album; bìa sách thường dọc (2:3) nên không cắt mất tên ở trên - đặt trọn
 * ảnh ở giữa, hai bên là chính ảnh ấy phóng to và làm mờ, cách các app sách nói vẫn làm.
 */
function PhotoCover({
  image,
  playing,
  className,
  onError,
}: {
  image: CoverImage;
  playing: boolean;
  className?: string;
  onError: () => void;
}) {
  const ratio = image.width && image.height ? image.width / image.height : 1;
  const square = Math.abs(ratio - 1) < 0.08;
  return (
    <div
      className={cn("relative aspect-square shrink-0 overflow-hidden rounded-lg shadow-card", className)}
      style={{ background: image.color || "var(--color-hover)" }}
      aria-hidden
    >
      {!square && (
        <img src={image.url} alt="" draggable={false} className="absolute inset-0 size-full scale-125 object-cover opacity-60 blur-xl" />
      )}
      <img
        src={image.url}
        alt=""
        draggable={false}
        decoding="async"
        onError={onError}
        className={cn("relative size-full", square ? "object-cover" : "object-contain")}
      />
      {playing && (
        <span className="absolute bottom-1.5 right-1.5 grid place-items-center rounded-md bg-black/45 px-1 py-0.5 text-white">
          <Vu className="h-3" />
        </span>
      )}
    </div>
  );
}
