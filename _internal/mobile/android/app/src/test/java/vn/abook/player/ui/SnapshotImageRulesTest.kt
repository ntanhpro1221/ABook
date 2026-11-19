package vn.abook.player.ui

import org.junit.Assert.*
import org.junit.Test
import java.io.File

/** New snapshots inherit image idling, and new image producers must publish inside a tracked scope. */
class SnapshotImageRulesTest {
    private val primitive = Regex("""\b(?:LaunchedEffect|produceState)(?:<[^\n{}]+>)?\s*\(""")
    private val imageWork = Regex("""\b(?:BitmapFactory|ImageBitmap|Bitmap|ArtImages|thumbnail)\b|\bcovers\.load\s*\(|\b(?:image|bitmap|artwork|avatar)(?:\.value)?\s*=|\b(?:load|fetch|decode)\w*(?:Image|Cover|Bitmap|Avatar|Artwork)\w*\s*\(""")

    // Strip comments/strings so their braces and sample code cannot affect scope matching.
    private fun code(source: String) = Regex("""/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"""")
        .replace(source) { " ".repeat(it.value.length) }

    private fun end(text: String, start: Int, open: Char, close: Char): Int {
        var depth = 0
        for (index in start until text.length) {
            if (text[index] == open) depth++
            if (text[index] == close && --depth == 0) return index
        }
        error("Unbalanced $open in Kotlin source")
    }

    internal fun untracked(source: String): List<String> {
        val clean = code(source)
        return primitive.findAll(clean).mapNotNull { match ->
            val argumentsEnd = end(clean, match.range.last, '(', ')')
            val bodyStart = clean.indexOf('{', argumentsEnd + 1)
            if (bodyStart < 0) return@mapNotNull null
            val bodyEnd = end(clean, bodyStart, '{', '}')
            var producer = clean.substring(match.range.first, bodyEnd + 1)
            // Exclude only a tracked request's scope, so another untracked decode
            // cannot hide beside it in a long-lived prefetch collector.
            while (true) {
                val tracked = Regex("""\bImageWork\.track\s*\{""").find(producer) ?: break
                val trackedEnd = end(producer, tracked.range.last, '{', '}')
                producer = producer.replaceRange(tracked.range.first, trackedEnd + 1,
                    " ".repeat(trackedEnd + 1 - tracked.range.first))
            }
            if (imageWork.containsMatchIn(producer)) {
                "line ${source.take(match.range.first).count { it == '\n' } + 1}: use produceImageState/ImageLaunchedEffect for image publication"
            } else null
        }.toList()
    }

    internal fun bypassesImageRule(source: String): Boolean = "captureRoboImage" in source &&
        (Regex("""import\s+androidx\.compose\.ui\.test\.junit4(?:\.v2)?\.(?:createAndroidComposeRule|createComposeRule|createEmptyComposeRule|\*)""").containsMatchIn(source) ||
            Regex("""androidx\.compose\.ui\.test\.junit4(?:\.v2)?\.create\w*ComposeRule|\bAndroidComposeTestRule\s*\(""").containsMatchIn(code(source)))

    @Test fun everySnapshotUsesTheImageAwareComposeRule() {
        val tests = File("src/test/java")
        assertTrue(tests.isDirectory)
        val offenders = tests.walkTopDown().filter { it.extension == "kt" && it.name != "SnapshotImageRulesTest.kt" }
            .filter { bypassesImageRule(it.readText()) }.map { it.relativeTo(tests).path }.toList()
        assertTrue("Snapshots bypass image idling: $offenders", offenders.isEmpty())
    }

    @Test fun everyImageProducerPublishesInsideTheTrackedScope() {
        val main = File("src/main/java/vn/abook/player/ui")
        assertTrue(main.isDirectory)
        val offenders = main.walkTopDown().filter { it.extension == "kt" && it.name != "ImageWork.kt" }
            .flatMap { file -> untracked(file.readText()).map { "${file.relativeTo(main).path}: $it" } }.toList()
        assertTrue("Untracked asynchronous artwork: $offenders", offenders.isEmpty())
    }

    @Test fun detectsNewMusicBookAvatarAndSearchProducersAndRuleBypasses() {
        for (load in listOf("value = covers.load(key, path, w, h)", "value = ArtImages.generated(seed)",
            "image = BitmapFactory.decodeFile(path)", "value = thumbnail(url)", "bitmap = CoverCrop.load(context, uri, width)")) {
            assertEquals(load, 1, untracked("LaunchedEffect(key) { $load }").size)
            assertEquals(load, 0, untracked("ImageLaunchedEffect(key) { $load }").size)
        }
        assertEquals(1, untracked("val image by produceState<ImageBitmap?>(null, key) { value = load() }").size)
        assertEquals(0, untracked("val image by produceImageState<ImageBitmap?>(null, key) { value = load() }").size)
        assertEquals(0, untracked("LaunchedEffect(key) { ImageWork.track { image = load() } }").size)
        assertEquals(1, untracked("LaunchedEffect(key) { ImageWork.track { image = load() }; bitmap = load() }").size)
        assertEquals(1, untracked("LaunchedEffect(key) { value = fetchBookCover(id) }").size)
        assertEquals(0, untracked("// LaunchedEffect(key) { image = load() }").size)
        val capture = "node.capture" + "RoboImage(path)"
        assertTrue(bypassesImageRule("import androidx.compose.ui.test.junit4.createAndroidComposeRule\n$capture"))
        assertTrue(bypassesImageRule("import androidx.compose.ui.test.junit4.v2.createComposeRule\n$capture"))
        assertTrue(bypassesImageRule("import androidx.compose.ui.test.junit4.*\n$capture"))
        assertTrue(bypassesImageRule("val rule = AndroidComposeTestRule(activity)\n$capture"))
        assertFalse(bypassesImageRule("import vn.abook.player.ui.createAndroidComposeRule\n$capture"))
    }
}
