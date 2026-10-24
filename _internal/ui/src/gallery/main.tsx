// Lối vào của phòng trưng bày (gallery.html). Hai loại trang:
//  - mục lục / khung xem: `gallery.html#/` và `gallery.html#/phone/library-full?theme=dark` (src/gallery/Index.tsx);
//  - khung app: `gallery.html?frame=phone/library-full&theme=dark` - chính app trên dữ liệu giả, đúng khổ (src/gallery/frame.ts).
// Mã app chỉ nạp ở khung app (import động), sau khi thế giới giả đã cài.

const params = new URLSearchParams(window.location.search);
const frame = params.get("frame");
if (frame) void import("./frame").then(({ startFrame }) => startFrame(frame, params.get("theme") === "dark" ? "dark" : "light"));
else void import("./Index").then(({ startIndex }) => startIndex());
