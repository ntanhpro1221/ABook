# Luật R8 cho bản phát hành (minifyEnabled + shrinkResources, app/build.gradle). Mỗi luật dưới đây có lý do; thêm luật mới thì
# ghi lý do ngay trên nó. Bản đã thu nhỏ KHÔNG đọc được stack trace nếu thiếu mapping.txt: docs/RELEASING.md bắt cất nó vào Corpus.

# Giữ số dòng + tên file nguồn cho stack trace (mapping.txt dịch ngược lại); chú thích/kiểu tổng quát cho phản chiếu bên dưới.
-keepattributes *Annotation*, Signature, InnerClasses, EnclosingMethod, SourceFile, LineNumberTable

# --- JNI -------------------------------------------------------------------------------------------------------------
# Hàm native bắt theo TÊN lớp + tên hàm (Java_vn_abook_player_vieneu_SeaG2pNative_nativeOpen...): đổi tên là UnsatisfiedLinkError.
# libabook_sea_g2p.so (sea-g2p, giọng VieNeu) nạp từ thư mục mô-đun lúc chạy, không nằm trong APK nên R8 không thấy nó gọi gì.
-keep class vn.abook.player.vieneu.SeaG2pNative { *; }
-keepclasseswithmembernames,includedescriptorclasses class * {
    native <methods>;
}

# ONNX Runtime (ai.onnxruntime, MIT, chép nguyên phần Java vào src/main/java; libonnxruntime4j_jni.so tải về lúc chạy): mã native
# gọi ngược Java theo tên (hàm khởi tạo OrtException/OnnxTensor/OnnxMap/OnnxSequence/OrtSession..., trường nativeHandle, hàm
# đăng ký). Gỡ hay đổi tên bất kỳ thành viên nào là JNI văng FindClass/GetMethodID. Bộ Java chỉ ~40 file nên giữ nguyên cả gói.
-keep class ai.onnxruntime.** { *; }
-keep interface ai.onnxruntime.** { *; }
-keep enum ai.onnxruntime.** { *; }

# --- WorkManager -----------------------------------------------------------------------------------------------------
# Worker được WorkManager dựng lại BẰNG TÊN LỚP đã lưu trong cơ sở dữ liệu của nó (StudioAlertWorker, PrepareWorker): tên bị
# R8 đổi khác giữa hai bản phát hành thì việc đã xếp hàng từ bản trước hỏng sau khi cập nhật. Giữ tên + hàm dựng.
-keepnames class * extends androidx.work.ListenableWorker
-keepclassmembers class * extends androidx.work.ListenableWorker {
    public <init>(android.content.Context, androidx.work.WorkerParameters);
}

# Không cần luật riêng: activity/service/receiver/provider khai trong manifest (AAPT tự giữ: NativeActivity,
# PlaybackService, CastService, PlayerWidget, FileProvider), Media3 (consumer rules), Tink (consumer rules; app chỉ gọi
# Ed25519Verify trong Signatures.kt, thử trên máy ảo ở bước kiểm danh mục nhạc), org.json (thủ công, không ánh xạ lớp theo tên trường).
