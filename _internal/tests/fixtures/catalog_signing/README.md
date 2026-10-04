# Fixture ký danh mục nhạc nền

**Khoá ở đây CHỈ DÙNG CHO TEST.** `public_key.hex` / `test_private_seed.hex` là một cặp khoá Ed25519 sinh riêng cho bài kiểm này, không
liên quan khoá ký thật của ABook (khoá cấu hình từ xa, nằm ngoài repo). Hạt bí mật để công khai có chủ ý: test dựng danh mục tại chỗ
rồi ký lại bằng nó. App thật không bao giờ tin khoá này - `MusicCatalog` / `RemoteConfig` chỉ nhận nó khi test truyền `public_key=` rõ ràng.

Sinh bằng `python -m tests.catalog_signing` (chạy từ `_internal`, venv runtime có `cryptography`); Ed25519 tất định nên chạy lại ra đúng byte cũ.
Test Python (`tests/test_music_catalog_signing.py`) và test Kotlin (`CatalogSigningTest`) cùng đọc thư mục này.

- `good/` - danh mục đầy đủ (`revision` r1, `issued` 2026-10-04): `manifest.json`, `manifest.json.sig`, `tracks/`, `cells/`.
- Các thư mục khác chỉ mang file KHÁC `good/`: test chép `good/` rồi phủ thư mục ca lên trên.
  - `newer/` mục lục ký đúng, `issued` mới hơn (r2); `older/` ký đúng nhưng `issued` cũ hơn (r0) - app không được quay về.
  - `bad_signature/` mục lục của `good/` với chữ ký lật một bit.
  - `tampered_manifest/` mục lục sửa một byte (`revision` r1 -> r9), chữ ký cũ.
  - `tampered_part/` mục lục nguyên vẹn nhưng `tracks/c4.json` bị tráo link (`x` -> `y`): sha256 lệch.
  - `unlisted_part/` mục lục ký đúng nhưng `files` không liệt kê `tracks/c4.json` (r3).
- `cases.json` - `revision` / `issued` của từng ca và các link mất khi mảnh bị loại.
