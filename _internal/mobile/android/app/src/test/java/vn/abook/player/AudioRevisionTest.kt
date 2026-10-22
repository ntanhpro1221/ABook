package vn.abook.player

import java.nio.file.Files
import org.junit.Assert.*
import org.junit.Test

class AudioRevisionTest {
    @Test fun order_preserves_desktop_microseconds_and_compares_timezones() {
        val old = org.json.JSONObject().put("a", "old")
        val new = org.json.JSONObject().put("a", "new")
        assertEquals("updated", AudioRevision.importState(old, new, "2026-10-22T01:00:00.000001Z", "2026-10-22T01:00:00.000002Z"))
        assertEquals("conflict", AudioRevision.importState(old, new, "2026-10-22T08:00:00.123456+07:00", "2026-10-22T01:00:00.123456Z"))
        assertEquals("conflict", AudioRevision.importState(old, new, "2026-10-22T01:00:00.000Z", "2026-10-22T01:00:00Z"))
    }

    @Test fun shared_import_cases() {
        val cases = org.json.JSONArray(java.io.File("../../../tests/fixtures/audio_revisions.json").readText(Charsets.UTF_8))
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            assertEquals(case.getString("name"), case.getString("status"), AudioRevision.importState(
                case.getJSONObject("local"), case.getJSONObject("incoming"), case.getString("localAt"), case.getString("incomingAt")))
        }
    }
    @Test fun equal_size_audio_is_only_reused_when_its_digest_matches() {
        val file = Files.createTempFile("revision", ".mp3").toFile()
        file.writeText("old")
        val first = AudioRevision.sha256(file)
        assertTrue(AudioRevision.matches(file, 3, first))
        file.writeText("new")
        assertFalse(AudioRevision.matches(file, 3, first))
        assertTrue(AudioRevision.matches(file, 3, AudioRevision.sha256(file)))
    }

    @Test fun retake_space_counts_the_resumable_part_but_never_reuses_old_equal_size_audio() {
        val folder = Files.createTempDirectory("revision-space").toFile()
        val target = java.io.File(folder, "chapter.mp3").apply { writeText("old-audio") }
        val newer = java.io.File(folder, "new.mp3").apply { writeText("new-audio") }
        val digest = AudioRevision.sha256(newer)
        val partial = java.io.File(target.path + ".part").apply { writeText("new") }
        PartResume.stamp(partial, "\"new-tag\"")
        assertEquals(6L, DownloadSpace.stillNeeded(9, target, digest))
        assertEquals(0L, DownloadSpace.stillNeeded(9, target, AudioRevision.sha256(target)))
    }
}
