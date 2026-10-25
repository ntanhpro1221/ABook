# Soát chuyển động 139: chỗ hiện / ẩn / đổi chữ còn CỨNG trong `_internal/ui/src`

Cơ sở: `origin/dev/next139` (c34445b). Chỉ đọc mã, chưa chạy app; mọi mục suy ra từ mã và luật phạm vi của `MotionRegion`.
Luật: `_internal/docs/DESIGN.md` nguyên tắc 6 ("không gì hiện/ẩn/đổi cỡ cứng") và mục 5.2 ("đổi nội dung tại chỗ = mờ qua";
"danh sách: thêm/xoá hàng mở/khép tại chỗ"; "không nảy, không vượt đích").

## 0. Cách đọc báo cáo: `MotionRegion` thật sự thấy gì

Nhiều chỗ trông như "đã nằm trong MotionRegion" nhưng thật ra không được che. Lý do (`shared/MotionRegion.tsx`):

- Vùng chỉ phản ứng khi `contentSignature(children)` đổi. Đây là chữ ký của **cây phần tử React truyền làm children ở hàm render chứa vùng**,
  gồm cả props của các phần tử đó.
- Không vào chữ ký:
  - State hay query nội bộ của component con: con tự `useQuery` rồi `return null` thì vùng cha không biết.
  - Prop boolean, function, `style`, `value`.
  - Chữ số: mọi chữ số thành `#`, nên `0 → N` không đổi chữ ký.
  - Vùng `MotionRegion` con lồng bên trong.
- Có `motionKey` thì vùng **chỉ** mờ khi khoá đổi. Vì vậy `App.tsx:596` (`motionKey="ready"`) và `ReaderScreen` (`motionKey="floating"`)
  không che gì bên trong.
- `MotionPresence` chỉ làm chuyển động khi `open` đổi. Đổi nội dung lúc vẫn mở thì phải có `MotionRegion` bên trong.
- `.motion-appear`, `.motion-reveal`, `.icon-pop` và `LoadingCrossfade` chỉ có chiều **vào**. Phần tử bị gỡ thì biến mất cứng, và chiều
  cao quanh nó nhảy.

Ký hiệu đề xuất:
- **MP** = `MotionPresence open={…}`
- **MR** = `MotionRegion` (kèm `motionKey` nếu có ghi)
- **AR** = `AnimatedRows` / `useListPresence`
- **LC** = `LoadingCrossfade`
- **Collapse** = `Collapse` / `Fold`

Mức gặp:
- **CAO**: màn chính, gần như mỗi lần dùng.
- **VỪA**: luồng thường nhưng không mỗi ngày.
- **THẤP**: hiếm, chẩn đoán, trường hợp biên.

---

## 1. Mức CAO

### 1.1 Mũi tên cuộn và mặt nạ mép của hàng tab: hiện/ẩn cứng
- **Ở đâu:** `_internal/ui/src/shared/ui.tsx:467`, `:474` (`{edges.left && <button…>}`, `{edges.right && …}`); mặt nạ `maskImage` ở `:449-454`.
- **Tái hiện:** trang sách hoặc trang dự án trên màn hẹp có hàng tab tràn. Cuộn ngang vài px: mũi tên trái và mép mờ bật ra tức thì.
  Cuộn về đầu thì chúng mất cứng.
- **Đề xuất:** **MP** cho từng mũi tên, hoặc luôn dựng nút và đổi `opacity` bằng token `--motion-fast`. Mặt nạ thì cho chuyển cùng.
- **Ghi chú:** vì nằm trong `TabsList`, lỗi xuất hiện ở mọi hàng tab của app.

### 1.2 Nút phát/dừng lớn: icon cũ biến mất cứng, icon mới nảy vào
- **Ở đâu:** `_internal/ui/src/listen/PlayerViews.tsx:279-289` (`Transport large`, dùng ở màn "Đang nghe" và thanh phát máy tính).
- **Cơ chế:** `Loader2` / `Pause` / `Play` đổi bằng `key` cộng `.icon-pop`. `.icon-pop` (`styles.css:1335`) chỉ có chiều vào, và đường cong
  `cubic-bezier(0.2, 0, 0, 1.3)` vượt đích, trái với "không nảy, không vượt đích". Spinner đệm cũng không có `.icon-pop`, nên vào/ra
  cứng hoàn toàn.
- **Tái hiện:** bấm phát/dừng, hoặc phát khi còn đang đệm.
- **Đề xuất:** **MR** `as="span" className="inline-grid place-items-center"` bọc glyph, đúng như bản gọn ở `PlayerViews.tsx:1703`
  (bản này đã mờ chéo đúng). Khi đó bỏ `key` và `icon-pop`.

### 1.3 Chân chương tab Kịch bản: "Duyệt N câu" đổi thành dòng chữ, đổi cứng
- **Ở đâu:** `_internal/ui/src/studio/ScriptTab.tsx:1524-1541` (`ChapterFooter`). Các chỗ đổi cứng:
  - nhánh `castReady && open.length > 0 ? <div><Button/><p/></div> : <span>…</span>`;
  - đuôi `, trừ ${doubtful} câu máy còn nghi` (`:1530`);
  - chữ ở `:1537-1539`.
- **Vì sao không được che:** footer nằm trong `MotionRegion` ở `:1713`, nhưng vùng đó có `motionKey=[filter, who, chapterId, Boolean(data), data?.castReady]`.
  Footer cũng không nằm trong vùng con ở `:1435`.
- **Tái hiện:** tab Kịch bản, bấm "Duyệt N câu", hoặc gán người cho câu chưa quyết cuối cùng của chương. Nút và chú thích mất cứng,
  chiều cao nhảy.
- **Đề xuất:** **MR** (không `motionKey`) bọc thân `ChapterFooter`.

### 1.4 Danh sách chương ở bước Nguồn khi tạo sách: hàng không khép tại chỗ
- **Ở đâu:** `_internal/ui/src/studio/NewProjectScreen.tsx:675-714` (nút xoá `:702-710`, xử lý xoá `:1919-1929`).
- **Hiện trạng:** chưa đến mức cứng, vì `MotionRegion` ở `:356` mờ qua **cả bước** "Nguồn truyện". Nhưng hàng bị bỏ không khép tại chỗ.
  Thanh cuộn của khung 340 px cũng bị chụp và mờ cùng.
- **Tái hiện:** "Tạo sách nói", đã chọn nguồn. Bấm thùng rác "Bỏ chương này", rồi "Hoàn tác". Hoặc chọn chip "20 chương đầu".
- **Đề xuất:** **AR** theo `file.path`.

---

## 2. Mức VỪA

### Nghe (Listen)

**`CaughtUpNotice`: khối cuối sách đổi chữ, đổi nút, đổi cao cứng**
- **Ở đâu:** `_internal/ui/src/listen/PlayerViews.tsx:2265` (nội dung từ `:2235`).
- **Cơ chế:** khối là `MotionPresence` bọc thẳng `content()`, không có `MotionRegion` bên trong (khác `FadingNotice` / `PlayerAlert`).
- **Tái hiện:** nghe tới cuối cuốn.
  - Dòng "Đã nghe hết sách" đổi thành "Đã nghe hết cuốn này" khi `useNextVolume` về muộn.
  - Cụm `AfterTheEnd` (`others.length > 0`) bật ra cứng khi thư viện về.
  - `caughtUp` đổi sang `finished` cũng là đổi cứng.
- **Đề xuất:** `<MotionPresence><MotionRegion>{content()}</MotionRegion></MotionPresence>`.

**Mức nhạc nền: dấu ✓ và nền chọn nhảy cứng khi menu còn mở**
- **Ở đâu:** `_internal/ui/src/listen/PlayerViews.tsx:505-508` (`LevelButtons`). Dấu ✓ đổi `invisible` ↔ hiện; nền `bg-accent-soft` đổi
  không có `transition-colors`.
- **Tái hiện:** menu Nhạc nền, chọn mức khác. Menu không đóng nên thấy rõ.
- **Đề xuất:** `transition-colors` và `transition-opacity` theo token, như `ChapterPanel` đã làm. Nếu mắt vẫn thấy đổi chữ thì **MR**.

**Gợi ý ghi công trên trang sách: ba trạng thái đổi cứng**
- **Ở đâu:** `_internal/ui/src/listen/ReadingSuggestions.tsx:171`, `:173`, `:180`, `:183`, `:186` (`BookSuggestions`).
- **Cơ chế:** ba trạng thái `null` / link "Xem lại gợi ý" / thẻ đổi cứng; h2 `· N chưa áp` và nút "Bỏ qua gợi ý" cũng vậy. Tất cả theo
  query và state nội bộ, nên vùng cha không thấy.
- **Tái hiện:** mở trang sách chỉ-có-chữ có gợi ý. Thẻ bật ra cứng khi query về. Bấm "Bỏ qua gợi ý" thì thẻ co lại thành link.
- **Đề xuất:** **MR** `motionKey` kiểu `none|quiet|card`, và **MP** cho nút `pending > 0`.

**Hộp "Sửa câu này": khối việc chờ biến mất cứng khi bấm "Bỏ"**
- **Ở đâu:** `_internal/ui/src/listen/LineWishes.tsx:446-489` (khối "Đang chờ máy làm sách", các `<li>`, câu chốt `:486`).
- **Tái hiện:** trang đọc, "Sửa câu này" ở một câu đã có việc chờ, bấm "Bỏ". Hộp không đóng, nên hàng và khối mất cứng và hộp co lại.
- **Đề xuất:** **MR** bọc nội dung `view === "menu"`, và **AR** cho `items`.

**Hộp "Sửa cách đọc một từ": panel sửa và các dòng phụ hiện/ẩn cứng**
- **Ở đâu:** `_internal/ui/src/listen/LineWishes.tsx:213-251` (`WordView`). Panel `word && <div data-name-editor>`; dòng `pending &&`
  (`:217-232`) và `reach?.surface === word &&` (`:234-238`).
- **Tái hiện:** trong hộp, chạm một chip từ, rồi chạm lại.
- **Đề xuất:** **MP** `open={Boolean(word)}`, bên trong **MR** `motionKey={word}`.

**Màn đọc: đổi cỡ chữ / giãn dòng làm cả chương reflow tức thì**
- **Ở đâu:** `_internal/ui/src/listen/ReaderScreen.tsx:393` (`style={{ fontSize, lineHeight }}`). Prop `style` nằm ngoài chữ ký.
- **Tái hiện:** màn đọc, biểu tượng "Cỡ chữ và giãn dòng", chọn mức khác.
- **Đề xuất:** **MR** `motionKey={[prefs.size, prefs.leading]}` quanh `<article>`. Cần đo chi phí chụp ảnh với chương dài.

**Màn đọc: nút "Nghe từ đây" bật cứng trong thanh nổi**
- **Ở đâu:** `_internal/ui/src/listen/ReaderScreen.tsx:325-330` (`{canListen && <Button>}`).
- **Cơ chế:** vùng `motionKey="floating"` không bao giờ mờ lại.
- **Tái hiện:** mở chương chỉ-có-chữ khi giọng máy chưa sẵn. Nút bật ra, đẩy các nút khác. **Cần kiểm** xem `canListen` có thật sự đổi
  sau khi thanh đã hiện không.
- **Đề xuất:** **MR** `motionKey={canListen}` bên trong thanh.

**Cài đặt › Phím tắt: danh sách đổi cứng khi bật/tắt "Phím tắt chữ"**
- **Ở đâu:** `_internal/ui/src/listen/Shortcuts.tsx:41`, `:43`, `:47-54`. Hậu tố "(đang tắt)", `line-through` và đoạn `<p>` cuối đổi theo
  `letters` (state nội bộ).
- **Tái hiện:** bật/tắt công tắc "Phím tắt chữ"; danh sách ngay dưới đổi cứng.
- **Đề xuất:** **MR** `motionKey={letters}` bọc `<dl>` và `<p>`.

### Studio

**Ô đếm kết quả tìm trong chương hiện/ẩn và đổi chữ cứng**
- **Ở đâu:** `_internal/ui/src/studio/ScriptTab.tsx:1756-1760` (`find.text.trim() && <span>`, đổi "k/n" ↔ "Không có").
- **Tái hiện:** gõ hoặc xoá trong ô "Tìm chữ trong chương…".
- **Đề xuất:** **MP** `open={Boolean(find.text.trim())}`, bên trong **MR** `motionKey={found ? "n" : "none"}`. Số đổi thì vẫn để không mờ.

**Hàng chip người nói thêm/bớt cứng**
- **Ở đâu:** `_internal/ui/src/studio/ScriptTab.tsx:1775-1804`. Chip `people` và chip "Chưa rõ" (`unnamed > 0`).
- **Cơ chế:** `motionKey` của vùng chỉ có `Boolean(data)`.
- **Tái hiện:** gán một câu cho người chưa có trong chú giải. Chip mới bật ra, hàng có thể xuống dòng.
- **Đề xuất:** **AR** cho chip.

**Lọc theo người nói: hàng rời danh sách không khép tại chỗ**
- **Ở đâu:** `_internal/ui/src/studio/ScriptTab.tsx:1460-1512`.
- **Hiện trạng:** khi lọc theo chip người nói, gán câu sang người khác làm hàng rời danh sách. Vùng `:1435` mờ qua cả danh sách mỗi lần,
  nên đây là mờ thừa chứ không cứng. **Cần kiểm** trên màn thật.
- **Đề xuất:** **AR** theo `stableId`.

**Dòng "Phần 2/3 · …" hiện cứng sau khi query về**
- **Ở đâu:** `_internal/ui/src/studio/ProjectScreen.tsx:834-838` (dùng ở `:1395`, `PartLinks`). Component tự `useParts` rồi `return null`.
- **Tái hiện:** mở dự án thuộc truyện nhiều phần; dòng hiện ra đẩy hàng nút và tab xuống.
- **Đề xuất:** **MP** `open={parts.length >= 2 && Boolean(here)}`.

**Thẻ quyết định ở "Duyệt trước khi thu" biến mất cứng**
- **Ở đâu:** `_internal/ui/src/studio/WorkInbox.tsx:1145` (`WorkCards`: `items.map(<Card/>)`), dùng ở `PrecastReview.tsx:260`, `:272`, `:289`.
- **Cơ chế:** `Card` đã sẵn `exiting` và `as="div"` cho `AnimatedRows` (hộp chính `:1293` dùng đúng), nhưng ở đây không dùng.
- **Tái hiện:** bấm một lựa chọn trên thẻ ở bước Nhân vật / Tên / Ai nói.
- **Đề xuất:** **AR** như `WorkInboxBody`.
- **Ghi chú:** cao nhất nhóm Studio phần phụ, vì mỗi quyết định là một lần gặp.

**Lọc cách đọc tên: hàng hiện/ẩn cứng, cả section mờ mỗi phím**
- **Ở đâu:** `_internal/ui/src/studio/NameReadings.tsx:154`, `:157` (`found.slice(0, limit).map`, hàng `addable`).
- **Tái hiện:** tab Nhân vật › Cách đọc tên, gõ vào ô tìm. Hàng hiện/ẩn cứng; cả section (`:113`) mờ lại sau mỗi phím.
- **Đề xuất:** **AR**, hoặc **MR** `motionKey` theo danh sách kết quả như `MergePeople.tsx:105`.

**Nhạc của tôi: xoá hay nhập bài làm hàng mất/hiện cứng**
- **Ở đâu:** `_internal/ui/src/studio/MusicTab.tsx:379` (`MyMusic` `tracks.map`, xoá ở `:395`).
- **Tái hiện:** Nhạc nền › Nhạc của tôi › Xoá, hoặc nhập bài mới.
- **Đề xuất:** **AR**.

**Chia thành nhiều phần: thêm/bỏ chỗ cắt làm cả khung mờ**
- **Ở đâu:** `_internal/ui/src/studio/VolumeSplit.tsx:140` (`parts.map`; thêm/xoá ở `:171-176`). Thêm hay bỏ chỗ cắt thì cả khung `:127` mờ.
- **Tái hiện:** thêm sách, bật "Chia thành nhiều phần", thêm hoặc bỏ chỗ cắt.
- **Đề xuất:** **AR** theo `part.start`.

### Máy tính / Android

**Đường dẫn thư viện đổi chữ cứng**
- **Ở đâu:** `_internal/ui/src/desktop/SettingsScreen.tsx:439`, `:441`.
- **Tái hiện:** Cài đặt › Nâng cao › "Đổi thư mục".
- **Đề xuất:** **MR** `as="span" motionKey={libraryRoot}`.

**Máy đã ghép: hàng không mở/khép tại chỗ**
- **Ở đâu:** `_internal/ui/src/desktop/OtherComputers.tsx:164` (`data.computers.map`).
- **Hiện trạng:** chỉ có mờ cả khối, hàng không mở/khép tại chỗ. `PhoneSync.tsx:261` đã dùng `useListPresence` cho cùng loại danh sách.
- **Tái hiện:** ghép hoặc "Thôi ghép" một máy.
- **Đề xuất:** **AR**. Danh sách "Tìm máy trong mạng" (`:246`) thì tuỳ.

**Hộp xuất M4B trên điện thoại: chữ ước tính và các khối phụ đổi cứng**
- **Ở đâu:** `_internal/ui/src/android/ExportAudiobook.tsx:171-188` (`AudiobookPhoneForm`). Các chỗ đổi cứng:
  - "Đang tính độ dài…" → số liệu (`:172`);
  - `resumeText`, `chapters` (`:174-175`);
  - khối nhạc nền (`:177-183`);
  - `rereadText`/`hint` (`:180-181`);
  - `notice` (`:184`).
- **Hiện trạng:** hai form anh em (`M4bMusicForm`, `Mp3MusicForm`) đã bọc `MotionRegion`; form này thì không.
- **Tái hiện:** menu sách, "Xuất sách nói (M4B)…". Hộp nhảy cao khi ước tính về.
- **Đề xuất:** **MR** bọc thân form, và **MP** cho khối nhạc.

### Thành phần dùng chung (ảnh hưởng nhiều nơi gọi)

**`LoadingCrossfade` chỉ có vào**
- **Ở đâu:** `_internal/ui/src/shared/MotionPresence.tsx:27-28`.
- **Cơ chế:** khi `loading` đổi false→true (khoá truy vấn đổi: lọc, đổi tab), `{!loading && …}` gỡ nội dung thật ngay. Khung chờ mờ dần lên
  trên chỗ trống.
- **Đề xuất:** để nội dung cũ (inert) mờ ra dưới khung chờ, cùng cách `MotionPresence` giữ `last.current`.

**`InlineError` / `LoadError` / `EmptyState` chỉ có `motion-reveal`**
- **Ở đâu:** `_internal/ui/src/shared/ui.tsx:836-845`, `:895`, `:878-886`.
- **Cơ chế:** nơi gọi `{error && <InlineError/>}` thì ra cứng. `EmptyState` đổi `title` / `action` cũng cứng.
- **Đề xuất:** cho thành phần tự bọc **MP** / **MR**, thay vì trông vào từng nơi gọi.

---

## 3. Mức THẤP

**Nghe**

| Ở đâu | Phần tử / tái hiện | Đề xuất |
|---|---|---|
| `listen/ReadingSuggestions.tsx:203`, `:211` | Nút bóng đèn trong menu "…" của trình phát hiện cứng khi query xong; trong hộp gợi ý, "Bỏ qua gợi ý" mất cứng khi tích hết dòng | **MP** |
| `listen/ReaderScreen.tsx:348`, `:363` | Ô chọn cỡ chữ / giãn dòng đổi nền và đậm nhạt không `transition-colors` (Thư viện `LibraryScreen.tsx:532` đã có) | `transition-colors duration-motion-fast` |
| `listen/LibraryScreen.tsx:573-579` | Khung "sắp có" (`upcomingRows.length > 0 &&`, lề `mt-6`) gắn/gỡ cứng dù hàng bên trong có `useListPresence`; lề 24 px nhảy khi hàng cuối khép | Luôn dựng khung (lề vào hàng) hoặc **MP** |
| `listen/BookScreen.tsx:570-593` | Tab Lịch sử: nhóm ngày / lượt nghe mới thêm cứng (vùng `:599` có `motionKey` chỉ "list" / "empty") | **AR** |
| `listen/BookScreen.tsx:485-492` | "Hiện chương sau · N người": hàng mới chỉ được mờ cả tab, không mở tại chỗ (cần kiểm) | **AR** |
| `listen/BookScreen.tsx:627-628` | Hộp "Chuyển hồ sơ": "Đang mở thư viện…" → `<select>` / "Thư viện chưa có…" đổi cứng | **MR** `motionKey` 3 trạng thái |
| `listen/ProjectFileItems.tsx:219-223` | Hộp "Việc của xưởng": khung chờ / lỗi / đổi Segmented `work` / `casting` / `names` đổi cứng | **MR** `fadeThrough motionKey={[tab, isLoading, Boolean(error)]}` |
| `listen/EditBook.tsx:686` | Hộp "Lưu thành": `{folder ?? "Mặc định: …"}` đổi cứng sau "Chọn thư mục…" | **MR** `motionKey={folder}` |
| `listen/PlaylistChoice.tsx:178-193` | Submenu "Nhạc nền": hàng thật hiện cứng khi query về; dấu ✓ và `font-semibold` đổi cứng | **MR** quanh danh sách, `transition-opacity` cho dấu ✓ |
| `listen/PlayerViews.tsx:1637` | `MenuSlot` `[&:not(:has(button))]:hidden`: dòng "Thiết bị phát" / "Gợi ý đọc" bật tắt khi nút con mount muộn (menu thường đang đóng) | **Collapse** / **MR** |
| `listen/PlayerViews.tsx:1209` | `VolumeControl` đổi 3 bố cục khi qua mốc 1280 px; icon `VolumeX` / `Volume1` / `Volume2` đổi cứng (khác component nhưng không props chuỗi). Cần kiểm | **MR** `motionKey` theo mức loa |
| `listen/PlayerViews.tsx:761-762` | Ngược lại: chữ "Thử" ↔ "Dừng" làm cả `MotionRegion` menu giọng (`:712`) mờ lại mỗi lần nghe thử (mờ thừa, cần kiểm) | `motionKey` cố định ở `:712`, **MR** riêng cho nhãn |

**Studio**

| Ở đâu | Phần tử / tái hiện | Đề xuất |
|---|---|---|
| `studio/NewProjectScreen.tsx:1981` | `{!draft.seed && <TemplateBar/>}` trong "Tuỳ chọn": bấm "Bỏ nối tiếp" / "Hoàn tác" thì thanh mẫu hiện/mất cứng | **MP** `open={!draft.seed}` |
| `studio/ScriptTab.tsx:1732`, `:1717-1721` | Điện thoại: `chapterExtras` ("N chỗ nghi", "N đã quyết"); ghi chú "Thu xong chương…" mất cứng khi có audio đầu tiên | **MR** |
| `studio/ProjectScreen.tsx:1099-1167` | Tab Nhật ký: mỗi mục log mới làm cả bảng (kể cả khung đang cuộn) mờ và tween (mờ thừa) | `motionKey={[mode, isLoading, !groups.length]}` và **AR** cho mục mới |
| `studio/MusicTab.tsx:680` | "Bài đã bỏ" › "Dùng lại": dòng mất cứng | **AR** |
| `studio/PhoneEdits.tsx:156`, `:170`, `:191`, `:200` | Hộp "Yêu cầu thiết bị": Áp dụng / Bỏ qua / Khôi phục làm hàng mất cứng | **AR** |
| `studio/WorkInbox.tsx:1316`, `:1329`, `:1339` | Mục "Đã quyết" / "Để sau" / "Làm lại": Hoàn tác làm thẻ mất cứng | **AR** |
| `studio/sharedReadings.tsx:81` | Cài đặt › Studio › Cách đọc chung: lọc / xoá hàng | **AR** |
| `studio/ExportBook.tsx:529` | "Bản xuất đã cũ" (poll 5 s): hàng mất cứng khi xuất lại xong | **AR** |
| `studio/ProjectsScreen.tsx:147`, `:111` | Nhãn `needs` hiện khi `pendingChanges` / `redo` `0 → N` (số không vào chữ ký); hàng hỏng ↔ thường sau "Thử lại" | **MR** `motionKey` quanh ô tiến độ `:142` |
| `studio/PrecastReview.tsx:106` | Thẻ công tắc "Duyệt trước khi thu" mất khi `recordedChapters` `0 → N` (cần kiểm, `freeNote` đổi cùng có thể đã che) | **MP** |
| `studio/AnalysisModelPicker.tsx:83` | `<details open={Boolean(value)}>` đổi bằng prop (chọn mẫu ở TemplateBar), không qua click nên `installDetailsMotion` không bắt; boolean cũng ngoài chữ ký | **Collapse** / **Fold** |

**Máy tính**

| Ở đâu | Phần tử / tái hiện | Đề xuất |
|---|---|---|
| `desktop/PhoneSync.tsx:272-281` | Khung chờ / lỗi và nội dung có gốc khác loại, nên React gỡ cả cây: khung chờ mất cứng | Một gốc chung hoặc **LC** |
| `desktop/PhoneDiagnostics.tsx:29` | `if (loading && !report) return <ContentSkeleton/>` → `MotionRegion`: cắt cứng | **LC** |
| `desktop/BookTemplates.tsx:65` | Cài đặt › Studio › Sách mới: "Xoá" / "Hoàn tác" một mẫu chỉ mờ cả vùng `:56` | **AR** |
| `desktop/PhoneSync.tsx:190`, `:229`, `:244` | `PairingContent`: khung (`border-accent`, `p-5`, nền) đổi `className` tức thì giữa "Mã ghép" / "Mã bị khoá" / nút trơn (cần kiểm ảnh chụp có giữ khung cũ không) | **MR** `motionKey` theo pha |
| `desktop/SettingsScreen.tsx:449` | Khối "Cập nhật" hiện khi `info.update` về trong lúc đang mở trang, nếu bản đóng gói không có `canCheckUpdate` (cần kiểm) | **MP** |

**Android**

| Ở đâu | Phần tử / tái hiện | Đề xuất |
|---|---|---|
| `android/DevicesScreen.tsx:894` | "Dung lượng trên máy": nhãn "Đang tải" ↔ "Phần đã tải…" đổi cứng | **MR** `motionKey={busy}` |
| `android/DevicesScreen.tsx:885` | `{rows.length > 0 && <ul className="mt-3">}`: lề nhảy khi hàng cuối khép / hàng đầu vào | Luôn dựng `ul` hoặc **MP** |
| `android/DevicesScreen.tsx:826`, `:835` | `DeviceNameRow` `return null` tới khi có tên rồi hiện cứng; đổi tên thì chữ thay cứng | **MP** và **MR** |
| `android/OldSaves.tsx:478` (gọi ở `android/SettingsScreen.tsx:297`) | "Bản lưu cũ": xoá một dòng thì dòng mất cứng | **AR** |
| `android/SettingsScreen.tsx:343` | `{version ?? "…"}` đổi cứng | **MR** |
| `android/App.tsx:209` | Menu "Xoá khỏi điện thoại…": dòng phụ "Chiếm …" bật ra sau khi menu đã mở | **MR** `as="span" motionKey={bytes !== undefined}` |
| `android/App.tsx:347` | `<SettingsScreen key={synced}/>` dựng lại cả màn khi đồng bộ cài đặt xong (vài giây đầu; cần kiểm) | Bỏ `key`, để dữ liệu chảy qua vùng sẵn có |
| `android/StudioOpen.tsx:123-146` | `StudioChip`: nút thường ↔ nút xám kèm dòng lý do khi danh sách máy về | **MR** `as="span"` |

**Dùng chung**

| Ở đâu | Phần tử / tái hiện | Đề xuất |
|---|---|---|
| `shared/ui.tsx:800`, `:803` | `Sheet`: `description` / `footer` bật tắt cứng nếu đổi lúc đang mở (lúc đóng thì ổn nhờ `lastContent`) | **MP** cho footer |
| `shared/ui.tsx:252-259` | `Progress`: đổi `indeterminate` thì thay phần tử thanh; đổi `tone` thì màu nhảy (`.motion-progress` chỉ chuyển `transform`) | **MR** `motionKey={[indeterminate, tone]}` và `transition-colors` |
| `shared/ui.tsx:184`, `:199` | `Tooltip`: `label` rỗng ↔ có đổi cấu trúc cây; nhãn đổi lúc đang mở thì chữ thay cứng | **MR** quanh `{label}` |
| `shared/ThirdPartyList.tsx:52-54` | "Thành phần sử dụng": "Đang mở danh sách…" → danh sách / lỗi đổi cứng | **LC** hoặc **MR** `motionKey` pha |
| `shared/OnComputerOnly.tsx:20`, `shared/MissingLibrary.tsx:21`, `:24-30` | "máy tính" → tên máy, tiêu đề và `action` đổi khi `useAppInfo()` về | **MR** |
| `shared/UnpairDialog.tsx:24-45` | Dòng chữ, `copy?.send` và nhãn nút đổi khi `reachable` đổi lúc hộp mở | **MR** bọc thân hộp |
| `shared/DiagnosticsView.tsx:13-51` | Các khối điều kiện và `LogBox` `<pre>` ↔ `<p>`: bản Android được `Diagnostics.tsx:70` che; bản máy tính phụ thuộc mục `PhoneDiagnostics` ở trên | Như `PhoneDiagnostics` |

---

## 4. Mẫu lặp: sửa theo mẫu sẽ dọn được nhiều mục một lúc

1. **Con tự lấy dữ liệu rồi `return null` hoặc đổi nhánh.** Ví dụ: `PartLinks`, `BookSuggestions`, `SuggestionsButton`, `DeviceNameRow`,
   `ShortcutList`, `StudioChip`. Vùng tổ tiên không bao giờ thấy những thay đổi này. Quy tắc nên ghi vào DESIGN.md: *component tự gọi
   hook dữ liệu thì tự mang `MotionPresence` / `MotionRegion` của mình*.
2. **Thành phần "chỉ có vào".** Gồm `.motion-appear`, `.motion-reveal`, `.icon-pop`, `LoadingCrossfade`, `InlineError`, `EmptyState`.
   Mỗi nơi gọi phải nhớ tự lo phần ra, và chỗ nào quên thì ra cứng. Sửa ngay trong thành phần dùng chung (mục 2, nhóm "Thành phần dùng
   chung") thì gỡ được cả loạt. Riêng `.icon-pop` còn vượt đích (1.3), trái với mục 5.2.
3. **`motionKey` hẹp làm khối anh em bị bỏ sót.** Ví dụ: `ScriptTab` (5 khoá cố định), `ReaderScreen` (`"floating"`), `BookScreen`
   Lịch sử. Cái gì đứng ngoài các khoá ấy cần vùng riêng.
4. **Danh sách đổi khi đang dùng mà chỉ nhờ mờ cả vùng.** Ví dụ: `WorkCards`, `OtherComputers`, `BookTemplates`, `VolumeSplit`,
   `MyMusic`, `PhoneEdits`, `sharedReadings`, `OldSaves`, chương nguồn. Theo 5.2, các danh sách này cần `useListPresence`.
   Ngược lại, một số vùng lớn không `motionKey` (`ProjectScreen:1550`, `NameReadings:113`, `ProjectScreen` Nhật ký, menu giọng
   `PlayerViews:712`) lại mờ **thừa** mỗi lần dữ liệu hàng đổi. Nên thu vùng lại và dùng `useListPresence` cho hàng.
5. **Nội dung đổi bên trong Dialog / Sheet.** Ví dụ: `LineWishes`, `ProjectViewsDialog`, `SaveAsDialog`, `MoveTarget`, `UnpairDialog`,
   `AudiobookPhoneForm`. `Dialog` chỉ lo lúc mở/đóng và tiêu đề; thân hộp cần **MR** riêng như `AddBook` / `EditBook` / `FindInBook`
   đã làm.

## 5. Đã soát, đúng (không báo)

- **Trình phát:** các menu Tốc độ / Nhạc nền / Giọng đọc / Hẹn giờ, `PrepareAhead`, `FadingNotice`, `PlayerAlert`, `ChapterPanel`,
  `BookmarkList`, `ReadAlong`, thanh phát gọn.
- **Shell máy tính:** `MotionPresence`, `AnimatedRows`, `MotionRegion` có `motionKey`.
- **Thành phần dùng chung:** `Button` / `IconButton` / `StatusPill` / `TabLabel` / `ActionButton` (tự mờ nhãn), `Dialog` / `Sheet`
  (giữ `lastContent`), `Collapse` / `Fold`, `ActionMenu`, `OfflineStrip`.
- **Nghe:** `ReadAlongText`, `SentenceMenu`, `AddBook`.
- **Studio:** `ExportBook` (trừ mục trên), `ReviewQueue`, `ApplyChanges`, `ChapterList` của `ProjectScreen`.
- **Android:** phần lớn `DevicesScreen`, hai form xuất nhạc.
- **Gallery:** công cụ dev, bỏ qua.
