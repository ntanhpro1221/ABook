package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ExportHistoryTest {
    @Test fun selected_mp3_chapters_keep_their_original_numbers() {
        val root = Files.createTempDirectory("export-selection").toFile()
        BookEditsFixtures.useStoreRoot(root)
        val id = "f-selection"
        val folder = File(root, "books/$id")
        File(folder, "chapters").mkdirs()
        val chapters = JSONArray()
        for (number in 1..2) {
            File(folder, "chapters/$number.mp3").writeText("audio-$number")
            chapters.put(JSONObject().put("id", number).put("index", number).put("available", true)
                .put("file", "chapters/$number.mp3").put("fullTitle", "Chương $number"))
        }
        File(folder, "book.json").writeText(JSONObject().put("id", id).put("title", "Sách").put("chaptersTotal", 2).put("chapters", chapters).toString())
        val plan = Mp3Export.plan(id, chapterIds = listOf(2))
        assertEquals(2, plan.numbered)
        assertEquals(listOf(2), plan.chapters.map { it.id })
        assertEquals(2, plan.chapters.single().number)
    }

    @Test fun history_survives_retake_and_keeps_old_export_warning() {
        val folder = Files.createTempDirectory("export-history").toFile()
        File(folder, "chapters").mkdirs()
        val audio = File(folder, "chapters/1.mp3").apply { writeText("old") }
        File(folder, "book.json").writeText(JSONObject().put("chapters", JSONArray().put(JSONObject()
            .put("id", 1).put("available", true).put("file", "chapters/1.mp3"))).toString())
        ExportHistory.remember(folder, "m4b", "book.m4b", ExportHistory.snapshot(folder))
        assertEquals(0, ExportHistory.view(folder).getJSONObject(0).getJSONArray("changed").length())
        audio.writeText("new")
        assertEquals(1, ExportHistory.view(folder).getJSONObject(0).getJSONArray("changed").getInt(0))
        ExportHistory.remember(folder, "m4b", "new.m4b", ExportHistory.snapshot(folder))
        assertEquals(2, ExportHistory.view(folder).length())
        assertEquals(0, ExportHistory.view(folder).getJSONObject(1).getJSONArray("changed").length())
    }
}
