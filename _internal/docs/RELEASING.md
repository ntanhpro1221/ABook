# Phát hành một phiên bản

Chủ sách, 27-09: *"mỗi bản release ra phải viết readme, changelog các thứ"*. Một bản phát hành chưa đủ các mục dưới đây thì
chưa phải bản phát hành.

## Số phiên bản - một số cho cả hai nền tảng

App máy tính và app điện thoại phát hành CÙNG một số `major.minor.patch`, ghi ở bốn chỗ:

| chỗ | trường |
|---|---|
| `_internal/pyproject.toml` | `version` |
| `_internal/ui/package.json` | `version` |
| `_internal/mobile/package.json` | `version` |
| `_internal/mobile/android/app/build.gradle` | `versionName` (= số phiên bản) và `versionCode` (tăng 1 mỗi bản) |

`pyproject.toml` nằm trong `QUALITY_IMPLEMENTATION_FILES`: đổi `version` là đổi hash chất lượng, sách đang làm dở không
tiếp tục được. Chỉ đổi khi không có sách nào cần tiếp tục (AGENTS.md).

## Tài liệu bắt buộc

1. **`docs/CHANGELOG.md`**: đổi mục `[Chưa phát hành]` thành `[x.y.z] - ngày`, viết theo góc NGƯỜI DÙNG (họ thấy gì khác), có
   mục "Lưu ý khi nâng cấp" nếu có gì phải làm tay; mở lại một mục `[Chưa phát hành]` trống ở trên.
2. **`README.md`**: soát lại phần giới thiệu tính năng, cách cài, yêu cầu máy, cách dùng điện thoại - khớp với bản này.
3. **Giấy phép**: `_internal/LICENSE` (MIT) đi kèm mọi bản; `docs/THIRD_PARTY.md` liệt kê đúng các thành phần THẬT SỰ
   được đóng gói trong bản này (thư viện, font, model) cùng giấy phép của chúng - thêm cái mới, bỏ cái không còn dùng.
4. **Ghi chú phát hành** trên GitHub Release: dán nguyên mục CHANGELOG của phiên bản, cộng dòng yêu cầu hệ thống và cách
   cài/nâng cấp.

## Kiểm tra trước khi phát hành

- `python -m pytest` toàn bộ và `npx tsc --noEmit` của `ui/` đều qua; kiểm tra tay trên máy ảo Android (`docs/UI.md`).
- Không có gì bị cấm lọt vào gói: khoá ký (Android keystore, khoá updater), audio, dữ liệu cá nhân (`listening.json`,
  `devices.json`, `computers.json` - mã thiết bị máy tính khác cấp, `reviews.json`, tuỳ chọn), token, văn bản truyện (kho nghiên cứu ở repo riêng tư, clone vào `Corpus/`
  - thư mục này bị bỏ qua; một thông báo DMCA sẽ khoá cả repo công khai lẫn trang tải bản phát hành).

## Đóng gói và đăng

1. Tag git `vX.Y.Z` trên commit phát hành, đẩy tag.
2. App máy tính: `scripts\build_windows_app.ps1` (không `-TauriConfig` - bản phát hành chỉ nhận cập nhật qua https) ra
   trong `shell\src-tauri\target\release\bundle\nsis\`: bộ cài `ABook_X.Y.Z_x64-setup.exe`, chữ ký `.sig` (khoá ở
   `%USERPROFILE%\.abook-keys`, không bao giờ commit) và `latest.json` (ghi chú lấy từ mục `[X.Y.Z]` của CHANGELOG -
   đổi tên mục trước khi dựng). App điện thoại: APK đã ký.
3. `gh release create vX.Y.Z` (dùng `GH_TOKEN="$(gh auth token --user ntanhpro1221)"` cho riêng lệnh ấy) với ghi chú ở mục
   "Tài liệu bắt buộc" và đính kèm bộ cài, `.sig`, `latest.json`, APK, `LICENSE`, `THIRD_PARTY.md`. Các bản đã cài đọc
   `releases/latest/download/latest.json`: Release phải là bản "latest" (không đánh dấu pre-release) thì mới tự cập nhật.
