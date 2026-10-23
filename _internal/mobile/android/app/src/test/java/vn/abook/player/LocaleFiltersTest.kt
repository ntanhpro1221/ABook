package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Soát a107 F4: chữ Việt của app (strings.xml, kể cả chữ media3) không bị values-en-rGB / en-rAU / en-rIN của thư viện đè trên máy đặt các vùng ấy -
 * app chỉ giữ ngôn ngữ của mình. Gradle chạy test ở mobile/android/app.
 */
class LocaleFiltersTest {
    @Test fun theAppKeepsOnlyItsOwnLanguageFromTheLibraries() {
        val gradle = File("build.gradle").readText(Charsets.UTF_8)
        val filters = Regex("""localeFilters\s*\+=\s*\[([^\]]*)\]""").find(gradle)?.groupValues?.get(1)
        assertTrue("thiếu androidResources.localeFilters", filters != null)
        assertEquals(listOf("vi"), Regex("\"([A-Za-z-]+)\"").findAll(filters!!).map { it.groupValues[1] }.toList())
    }

    @Test fun theAppReallyHasNoOtherLanguage() {
        // Có thêm values-xx thì bộ lọc ở trên phải giữ ngôn ngữ ấy.
        val others = File("src/main/res").listFiles { file -> file.isDirectory && file.name.startsWith("values-") && file.name != "values-v24" }.orEmpty().map { it.name }
        assertEquals(emptyList<String>(), others.filter { Regex("values-[a-z]{2,3}(-r[A-Z]{2})?").matches(it) })
    }
}
