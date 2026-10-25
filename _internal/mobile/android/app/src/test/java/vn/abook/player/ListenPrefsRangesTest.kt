package vn.abook.player

import android.os.Handler
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Soát a102 B3: lõi Kotlin tự kiểm miền giá trị của tuỳ chọn nghe khi nhận `configure`, cùng một bảng với giao diện và Python
 * (tests/fixtures/settings/ranges.json - cả ba bên có test đọc file này). Giá trị ngoài miền về mặc định RIÊNG trường ấy, trường khác không bị ảnh hưởng.
 */
class ListenPrefsRangesTest {
    private val ranges: JSONObject = JSONObject(BookEditsFixtures.file("../settings/ranges.json").readText(Charsets.UTF_8))
    private val choices = ranges.getJSONObject("choices")
    private val booleans = ranges.getJSONObject("booleans")

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("listen-prefs-ranges"))
        reset()
    }

    @After fun cleanup() {
        reset()
        Handler.reset()
    }

    private fun reset() {
        Playback.headsetSkips = true
        Playback.configure(true)
        SleepTimer.extendMinutes = 10
        SleepTimer.fadeMs = 30_000L
        SleepTimer.shakeEnabled = true
        SleepTimer.shakeResets = false
        SleepTimer.shakeThresholdG = 2.2
        SleepTimer.safetyStopHours = 2.0
        SleepTimer.schedule = null
        Motion.flipEnabled = false
    }

    /** Điều lõi đang dùng cho tuỳ chọn `key`, đưa về cùng dạng với bảng chung (số -> Double, chữ -> String). */
    private fun observed(key: String): Any = when (key) {
        "sleepFadeSeconds" -> SleepTimer.fadeMs / 1000.0
        "sleepExtendMinutes" -> SleepTimer.extendMinutes.toDouble()
        "safetyStopHours" -> SleepTimer.safetyStopHours
        "shakeAction" -> if (SleepTimer.shakeResets) "reset" else "extend"
        "shakeSensitivity" -> when (SleepTimer.shakeThresholdG) { 1.6 -> "gentle"; 2.8 -> "firm"; 2.2 -> "normal"; else -> "?${SleepTimer.shakeThresholdG}" }
        else -> error(key)
    }

    /** Khoá WebView áp; native chỉ nhớ rồi trả lại ([ListenPrefs.stored]) - có test riêng, không có "điều lõi đang dùng". */
    private val rememberedOnly = setOf("theme", "readingSurface")

    private fun natively() = choices.keys().asSequence().filter { it !in rememberedOnly }.toList()

    private fun values(key: String): List<Any> = choices.getJSONObject(key).getJSONArray("values").let { array -> (0 until array.length()).map { array.get(it) } }

    private fun expected(value: Any): Any = if (value is Number) value.toDouble() else value

    private fun default(key: String): Any = expected(choices.getJSONObject(key).get("default"))

    private fun literal(value: Any) = if (value is String) JSONObject.quote(value) else value.toString()

    private fun push(key: String, literal: String) = ListenPrefs.apply(JSONObject("{\"$key\":$literal}"))

    @Test fun everyValueInTheSharedTableIsKept() {
        for (key in natively()) {
            for (value in values(key)) {
                val other = values(key).first { it != value }
                push(key, literal(other))
                push(key, literal(value))
                assertEquals("$key=$value", expected(value), observed(key))
            }
        }
    }

    @Test fun anyOtherValueFallsBackToThatFieldsOwnDefault() {
        val wrong = listOf("-1", "999", "\"x\"", "null", "7.5", "true", "[]", "{}", "\"30\"")
        for (key in natively()) {
            val away = values(key).first { expected(it) != default(key) }
            for (bad in wrong) {
                push(key, literal(away))
                assertNotEquals("$key phải rời mặc định trước khi thử", default(key), observed(key))
                push(key, bad)
                assertEquals("$key=$bad", default(key), observed(key))
            }
        }
    }

    @Test fun aWrongFieldDoesNotSpoilTheOthers() {
        val body = JSONObject()
        for (key in natively()) body.put(key, values(key).first { expected(it) != default(key) })
        body.put("sleepExtendMinutes", 999)
        body.put("shakeToExtend", "yes")
        body.put("schedule", JSONObject("""{"from":"22:00","to":"06:00","minutes":20}"""))
        ListenPrefs.apply(body)
        for (key in natively()) {
            if (key == "sleepExtendMinutes") assertEquals(default(key), observed(key))
            else assertEquals(key, expected(body.get(key)), observed(key))
        }
        assertTrue("công tắc sai kiểu về mặc định của nó", SleepTimer.shakeEnabled == booleans.getBoolean("shakeToExtend"))
        assertNull("lịch sai về không có lịch", SleepTimer.schedule)
    }

    @Test fun switchesTakeOnlyRealBooleans() {
        fun seen(key: String) = when (key) {
            "shakeToExtend" -> SleepTimer.shakeEnabled
            "flipToPause" -> Motion.flipEnabled
            "headsetSkips" -> Playback.headsetSkips
            "autoRewind" -> Playback::class.java.getDeclaredField("autoRewind").also { it.isAccessible = true }.getBoolean(Playback)
            // Tiếng chạm và rung do WebView áp: native chỉ nhớ rồi trả lại.
            "touchSounds", "haptics" -> ListenPrefs.stored().getBoolean(key)
            else -> error(key)
        }
        for (key in booleans.keys()) {
            val default = booleans.getBoolean(key)
            for (wanted in listOf(true, false)) {
                push(key, (!wanted).toString())
                push(key, wanted.toString())
                assertEquals("$key=$wanted", wanted, seen(key))
            }
            for (bad in listOf("\"true\"", "1", "0", "null", "\"\"", "[]")) {
                push(key, (!default).toString())
                push(key, bad)
                assertEquals("$key=$bad về mặc định", default, seen(key))
            }
        }
    }

    @Test fun theNightScheduleFollowsTheSharedClockAndMinutes() {
        val clock = Regex(ranges.getJSONObject("schedule").getString("clock"))
        val minutes = ranges.getJSONObject("schedule").getJSONArray("minutes").let { a -> (0 until a.length()).map { a.getInt(it) } }
        for (m in minutes) {
            push("schedule", """{"from":"22:00","to":"06:30","minutes":$m}""")
            assertEquals(Triple(22 * 60, 6 * 60 + 30, m), SleepTimer.schedule)
        }
        for (from in listOf("24:00", "6:00", "22:60", "ab", "22:00:00", "")) {
            assertTrue("$from nên bị bảng chung từ chối", !clock.matches(from))
            push("schedule", """{"from":"22:00","to":"06:30","minutes":30}""")
            push("schedule", """{"from":"$from","to":"06:30","minutes":30}""")
            assertNull("giờ $from", SleepTimer.schedule)
        }
        for (bad in listOf("""{"from":"22:00","to":"06:30","minutes":${minutes.max() + 1}}""", """{"from":"22:00","to":"06:30","minutes":-10}""", """{"from":"22:00","to":"06:30"}""",
            """{"from":"22:00","to":"06:30","minutes":"30"}""", """{"from":22,"to":"06:30","minutes":30}""", "[]", "\"22:00\"", "5")) {
            push("schedule", """{"from":"22:00","to":"06:30","minutes":30}""")
            push("schedule", bad)
            assertNull("lịch $bad", SleepTimer.schedule)
        }
        push("schedule", """{"from":"22:00","to":"06:30","minutes":30}""")
        ListenPrefs.apply(JSONObject("""{"autoRewind":true}"""))
        assertEquals("không nhắc tới lịch thì giữ nguyên", Triple(22 * 60, 6 * 60 + 30, 30), SleepTimer.schedule)
        push("schedule", "null")
        assertNull("null xoá lịch", SleepTimer.schedule)
    }

    @Test fun whatNativeRemembersAndHandsBackIsAlreadyInsideTheTable() {
        ListenPrefs.apply(JSONObject("""{"sleepExtendMinutes":999,"sleepFadeSeconds":15,"safetyStopHours":"x","shakeAction":"spin","shakeSensitivity":7,"shakeToExtend":"no",
            "schedule":{"from":"99:00","to":"06:00","minutes":30},"settingsStamp":"later"}"""))
        val stored = ListenPrefs.stored()
        for (key in natively()) assertEquals("$key đã nhớ", default(key), expected(stored.get(key)))
        assertEquals(booleans.getBoolean("shakeToExtend"), stored.getBoolean("shakeToExtend"))
        assertTrue("lịch sai nhớ là không có lịch", stored.isNull("schedule"))
        assertEquals("dấu giờ sai về 0", 0L, stored.getLong("settingsStamp"))
        ListenPrefs.apply(JSONObject("""{"sleepExtendMinutes":15,"settingsStamp":1700000000123}"""))
        assertEquals(1700000000123L, ListenPrefs.stored().getLong("settingsStamp"))
        assertEquals(15, ListenPrefs.stored().getInt("sleepExtendMinutes"))
    }

    @Test fun theSharedTableHasNoDuplicatesAndTheNativeDefaultsAreInIt() {
        for (key in natively()) {
            val list = values(key).map(::expected)
            assertEquals("$key không trùng giá trị", list.size, list.toSet().size)
            assertTrue("$key: mặc định phải nằm trong miền", default(key) in list)
        }
    }

    @Test fun theThemeIsRememberedAndHandedBackInsideItsTable() {
        val themes = values("theme")
        for (theme in themes) {
            ListenPrefs.apply(JSONObject("{\"theme\":${literal(theme)}}"))
            assertEquals("theme=$theme", theme, ListenPrefs.stored().getString("theme"))
        }
        for (bad in listOf("\"purple\"", "5", "null", "true", "[]")) {
            ListenPrefs.apply(JSONObject("{\"theme\":\"dark\"}"))
            ListenPrefs.apply(JSONObject("{\"theme\":$bad}"))
            assertEquals("theme=$bad", default("theme"), ListenPrefs.stored().getString("theme"))
        }
        ListenPrefs.apply(JSONObject("""{"theme":"dark"}"""))
        ListenPrefs.apply(JSONObject("""{"autoRewind":false}"""))
        assertEquals("lần đẩy không mang theme không làm mất theme đã nhớ", "dark", ListenPrefs.stored().getString("theme"))
    }

    @Test fun theReadingSurfaceAndTheTwoFeedbackSwitchesAreRememberedAndHandedBackInsideTheirTable() {
        val surfaces = values("readingSurface")
        for (surface in surfaces) {
            ListenPrefs.apply(JSONObject("{\"readingSurface\":${literal(surface)}}"))
            assertEquals("readingSurface=$surface", surface, ListenPrefs.stored().getString("readingSurface"))
        }
        for (bad in listOf("\"purple\"", "5", "null", "true", "[]")) {
            ListenPrefs.apply(JSONObject("{\"readingSurface\":\"night\"}"))
            ListenPrefs.apply(JSONObject("{\"readingSurface\":$bad}"))
            assertEquals("readingSurface=$bad", default("readingSurface"), ListenPrefs.stored().getString("readingSurface"))
        }
        for (key in listOf("touchSounds", "haptics")) {
            assertTrue("$key phải nằm trong bảng chung", booleans.has(key))
            for (wanted in listOf(true, false)) {
                ListenPrefs.apply(JSONObject("{\"$key\":$wanted}"))
                assertEquals("$key=$wanted", wanted, ListenPrefs.stored().getBoolean(key))
            }
            ListenPrefs.apply(JSONObject("{\"$key\":\"yes\"}"))
            assertEquals("$key sai kiểu về mặc định", booleans.getBoolean(key), ListenPrefs.stored().getBoolean(key))
        }
        ListenPrefs.apply(JSONObject("""{"readingSurface":"ivory","touchSounds":false,"haptics":false}"""))
        ListenPrefs.apply(JSONObject("""{"autoRewind":false}"""))
        val kept = ListenPrefs.stored()
        assertEquals("lần đẩy không mang ba khoá không làm mất chúng", Triple("ivory", false, false),
            Triple(kept.getString("readingSurface"), kept.getBoolean("touchSounds"), kept.getBoolean("haptics")))
    }
}
