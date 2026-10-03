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

- `python -m pytest` toàn bộ, `npm run typecheck` và `npm test` (vitest, logic thuần của giao diện) của `ui/` đều qua; kiểm tra tay trên máy ảo Android (`docs/UI.md`).
- Không có gì bị cấm lọt vào gói: khoá ký (Android keystore, khoá updater), audio, dữ liệu cá nhân (`listening.json`,
  `devices.json`, `computers.json` - mã thiết bị máy tính khác cấp, `reviews.json`, tuỳ chọn), token, văn bản truyện (kho nghiên cứu ở repo riêng tư, clone vào `Corpus/`
  - thư mục này bị bỏ qua; một thông báo DMCA sẽ khoá cả repo công khai lẫn trang tải bản phát hành).

## Đóng gói và đăng

Từ 01-10 cả bốn bước dưới đây là một script (`scripts/release.py`, chạy bằng `runtime/.venv`, từ worktree có commit phát
hành); mỗi bước dừng ở chỗ đầu tiên không đúng:

```
python scripts/release.py bump X.Y.Z --commit   # 7 file + commit "Release X.Y.Z"; hash chất lượng phải giữ nguyên
python scripts/release.py build X.Y.Z           # bộ cài + APK; kiểm latest.json và chứng chỉ APK
python scripts/release.py publish X.Y.Z --commit <commit phát hành>
```

File phát hành nằm ở thư mục tạm của máy (`abook-release/X.Y.Z`, hay `--out`), không bao giờ trong repo. Các bước tay
tương ứng, để hiểu script làm gì:

1. Tag git `vX.Y.Z` trên commit phát hành, đẩy tag.
2. App máy tính: `scripts\build_windows_app.ps1` (không `-TauriConfig` - bản phát hành chỉ nhận cập nhật qua https) ra
   trong `shell\src-tauri\target\release\bundle\nsis\`: bộ cài `ABook_X.Y.Z_x64-setup.exe`, chữ ký `.sig` (khoá ở
   `%USERPROFILE%\.abook-keys`, không bao giờ commit) và `latest.json` (ghi chú lấy từ mục `[X.Y.Z]` của CHANGELOG -
   đổi tên mục trước khi dựng). App điện thoại: `npm run build:android` trong `ui\`, `npx cap sync android`, rồi
   `gradlew assembleRelease` trong `mobile\android\` - Gradle ký bằng `%USERPROFILE%\.abook-keys\android-release.properties`
   (thiếu file ấy thì APK không ký, không phát hành được). Mất khoá APK là người dùng phải gỡ app rồi cài lại: bản sao lưu
   của cả hai khoá nằm ở `keys/` trong repo riêng tư `ntanhpro1221/ABook-Private` (README ở đó chỉ cách khôi phục).
   Bộ cài chỉ-nghe KHÔNG mang từ điển phát âm và giọng nghe thử (`webui/studio_setup.py` > `STUDIO_ASSETS`: Studio tải gói
   ghim ở bước đầu tiên). Gói đổi (file trong `abook/assets/voice_previews` hay `cmudict.dict` đổi) thì: `python
   scripts/pack_studio_assets.py`, đăng gói lên nơi chứa, điền URL ghim theo commit + băm + cỡ vào `STUDIO_ASSETS`;
   `release.py build` từ chối khi URL còn `PIN_REVISION`. Script dựng cũng cắt Python nhúng (Pillow,
   thư viện chuẩn) rồi chạy `scripts/smoke_embedded_python.py` trên chính bản đã cắt - đừng bỏ qua khi nâng Python hay gói phụ.
3. `gh release create vX.Y.Z` (dùng `GH_TOKEN="$(gh auth token --user ntanhpro1221)"` cho riêng lệnh ấy) với ghi chú ở mục
   "Tài liệu bắt buộc" và đính kèm bộ cài, `.sig`, `latest.json`, APK, `LICENSE`, `THIRD_PARTY.md`. Các bản đã cài đọc
   `releases/latest/download/latest.json`: Release phải là bản "latest" (không đánh dấu pre-release) thì mới tự cập nhật.
