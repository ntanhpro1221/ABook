package vn.abook.player

/** Media3 (ParsableByteArray) tự hỏi "đang chạy bài thử?" qua `Build.FINGERPRINT`, mà vỏ android.jar của bài thử JVM để null: đặt như
 *  Robolectric. Gọi trước khi chạy bộ tách của Media3 trên JVM (LiveClipsTest, ExactSeekMp3ExtractorTest). */
internal fun pretendMedia3IsUnderTest() {
    val unsafeClass = Class.forName("sun.misc.Unsafe")
    val unsafe = unsafeClass.getDeclaredField("theUnsafe").also { it.isAccessible = true }.get(null)
    val field = android.os.Build::class.java.getField("FINGERPRINT")
    val base = unsafeClass.getMethod("staticFieldBase", java.lang.reflect.Field::class.java).invoke(unsafe, field)
    val offset = unsafeClass.getMethod("staticFieldOffset", java.lang.reflect.Field::class.java).invoke(unsafe, field) as Long
    unsafeClass.getMethod("putObject", Any::class.java, Long::class.javaPrimitiveType, Any::class.java).invoke(unsafe, base, offset, "robolectric")
}
