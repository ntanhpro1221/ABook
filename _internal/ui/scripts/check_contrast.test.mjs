import { readdirSync, readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { checkContrast, over, oklch, ratio, readerTokens, rgba, themeTokens, tintWeight } from "./check_contrast.mjs";

it("tỉ lệ WCAG: độ chói tuyến tính, alpha ghép trước khi đo", () => {
  expect(ratio([0, 0, 0, 1], [255, 255, 255, 1])).toBe(21);
  expect(over([0, 0, 0, 0.5], [255, 255, 255, 1])).toEqual([127.5, 127.5, 127.5, 1]);
  expect(ratio([0, 0, 0, 0.5], [255, 255, 255, 1])).toBeCloseTo(3.9767, 3);
});

it("color-mix oklab: pha với trong suốt giữ nguyên màu, chỉ giảm alpha; hai màu đặc pha theo oklab", () => {
  const t = { a: "#e9a945" };
  const faint = rgba("color-mix(in oklab, var(--a) 26%, transparent)", t);
  expect(faint[3]).toBeCloseTo(0.26, 5);
  expect(faint.slice(0, 3).map(Math.round)).toEqual([233, 169, 69]);
  // Trắng + đen 50 % trong oklab là xám có độ sáng 0,5 (≈ #636363), không phải #808080 như pha trong sRGB.
  const grey = rgba("color-mix(in oklab, #ffffff 50%, #000000)", {});
  expect(grey.slice(0, 3).map(Math.round)).toEqual([99, 99, 99]);
  expect(oklch(0.5, 0, 0).slice(0, 3).map(Math.round)).toEqual([99, 99, 99]);
});

it("mọi cặp thực dùng đạt AA ở cả hai giao diện, ba mặt đọc và màn Đang nghe", () => {
  const rows = checkContrast();
  expect(new Set(rows.map((row) => row.theme))).toEqual(new Set(["light", "dark"]));
  for (const surface of ["auto", "paper", "ivory", "night"]) expect(rows.some((row) => row.label.startsWith(`đọc ${surface}:`))).toBe(true);
  expect(rows.filter((row) => !row.pass).map((row) => `${row.theme} ${row.label}`)).toEqual([]);
});

it.each(["light", "dark"])("mặt đọc theo mặt riêng chứ không theo giao diện của app (%s)", (theme) => {
  for (const [surface, bg, ink] of [["paper", "#fbfaf7", "#1b1a17"], ["ivory", "#f3ead8", "#3b2f1e"], ["night", "#121110", "#d9d3c8"]]) {
    const t = readerTokens(theme, surface);
    expect(rgba("var(--read-bg)", t)).toEqual(rgba(bg, t));
    expect(rgba("var(--text)", t)).toEqual(rgba(ink, t));
  }
  // Lớp tô câu đang đọc lấy màu nhấn của mặt đọc: Đêm trong app sáng vẫn dùng hổ phách sáng, không dùng hổ phách sẫm của app.
  expect(rgba("var(--read-along)", readerTokens(theme, "night")).slice(0, 3).map(Math.round)).toEqual([233, 169, 69]);
});

it("màu chủ đạo khớp DESIGN 5.1", () => {
  expect(themeTokens("light")).toMatchObject({ bg: "#f5f3ef", panel: "#ffffff", text: "#1a1814", accent: "#d4912b" });
  expect(themeTokens("dark")).toMatchObject({ bg: "#121110", panel: "#1b1a18", text: "#ece8e1", accent: "#e9a945" });
});

it("màn Đang nghe pha bìa với trần đã đo", () => {
  expect(tintWeight("light")).toBeLessThanOrEqual(8);
  expect(tintWeight("dark")).toBeLessThanOrEqual(12);
});

it("không có sắc thứ hai: token thông tin là xám ấm (kênh đỏ >= xanh dương, độ lệch nhỏ)", () => {
  for (const theme of ["light", "dark"]) {
    const t = themeTokens(theme);
    for (const name of ["info", "info-soft"]) {
      const [r, g, b] = rgba(`var(--${name})`, t);
      expect(r - b, `${theme} ${name}`).toBeGreaterThanOrEqual(0);
      expect(Math.max(r, g, b) - Math.min(r, g, b), `${theme} ${name}`).toBeLessThanOrEqual(24);
    }
  }
});

it("không thành phần nào vòng qua token: không màu thô trong className / style (trừ ảnh bìa)", () => {
  const root = new URL("../src/", import.meta.url);
  const files = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const next = new URL(entry.name + (entry.isDirectory() ? "/" : ""), dir);
      if (entry.isDirectory()) { if (entry.name !== "gallery" && entry.name !== "assets") walk(next); }
      else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) files.push(next);
    }
  };
  walk(root);
  // Ảnh bìa vẽ (cover.ts: bảng màu bìa, canvas) và ô vẽ bìa đã cắt (EditBook) là nghệ thuật, không phải vỏ app.
  const art = /\/(shared\/cover|listen\/EditBook)\.tsx?$/;
  const palette = /\b(?:text|bg|border|ring|fill|stroke|from|to|via|outline|divide|decoration|shadow)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)\b/;
  const literal = /#[\da-f]{6}\b|rgba?\((?!0, 0, 0, 0\))/i;
  const offenders = [];
  for (const file of files) {
    if (art.test(file.pathname)) continue;
    readFileSync(file, "utf8").split("\n").forEach((line, index) => {
      if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
      if (palette.test(line) || literal.test(line)) {
        // Tên sách và vệt nền nhãn tập trên bìa VẼ SẴN (BookCover) là nghệ thuật bìa trên nền gradient tối của bảng bìa.
        if (file.pathname.endsWith("/shared/BookCover.tsx") && /line-clamp-4|rgb\(0 0 0 \/ 0\.28\)/.test(line)) return;
        offenders.push(`${file.pathname.split("/src/")[1]}:${index + 1}`);
      }
    });
  }
  expect(offenders).toEqual([]);
});

it("màu Android (màn chờ, thanh trạng thái, thanh điều hướng) khớp --bg và mực ở cả hai giao diện", () => {
  const read = (dir) => {
    const xml = readFileSync(new URL(`../../mobile/android/app/src/main/res/${dir}/colors.xml`, import.meta.url), "utf8");
    return Object.fromEntries([...xml.matchAll(/<color name="(\w+)">(#[\da-f]{6})<\/color>/gi)].map(([, name, value]) => [name, value.toLowerCase()]));
  };
  const light = read("values"), dark = { ...light, ...read("values-night") };
  for (const [theme, android] of [["light", light], ["dark", dark]]) {
    const t = themeTokens(theme);
    expect(android, theme).toMatchObject({ app_bg: t.bg, app_text: t.text, app_text_secondary: t["text-2"], colorAccent: t.accent });
  }
  const styles = readFileSync(new URL("../../mobile/android/app/src/main/res/values/styles.xml", import.meta.url), "utf8");
  for (const item of ["windowSplashScreenBackground", "android:statusBarColor", "android:navigationBarColor", "android:windowBackground"]) {
    expect(styles, item).toContain(`<item name="${item}">@color/app_bg</item>`);
  }
});
