package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class MotionScanTest {
    private fun flagged(code: String) = MotionScan.scan("t.kt", code).isNotEmpty()

    @Test
    fun `source of the native ui has no alpha-only transitions`() {
        val dir = File("src/main/java/vn/abook/player/ui")
        assertTrue("không thấy ${dir.absolutePath}", dir.isDirectory)
        val files = dir.walkTopDown().filter { it.extension == "kt" }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 8)
        val findings = files.flatMap { MotionScan.scan(it.name, it.readText()) }
        assertEquals(findings.joinToString("\n") { "${it.file}:${it.line} ${it.why}" }, emptyList<MotionScan.Finding>(), findings)
        val unguarded = MotionScan.unguardedReducedCalls(files.associate { it.path to it.readText() })
        assertEquals(unguarded.joinToString("\n"), emptyList<MotionScan.Finding>(), unguarded)
    }

    @Test
    fun `lone fade is caught`() {
        assertTrue(flagged("val enter = fadeIn()"))
        assertTrue(flagged("AnimatedVisibility(v, enter = fadeIn(tween(120)), exit = fadeOut(tween(90))) { }"))
        assertTrue(flagged("val t = fadeIn() togetherWith fadeOut()"))
        assertTrue(flagged("Crossfade(target) { }"))
        assertTrue(flagged("AnimatedContent(state) { }"))
    }

    @Test
    fun `fade combined with geometry in one expression passes`() {
        assertEquals(emptyList<MotionScan.Finding>(), MotionScan.scan("t.kt", "val a = fadeIn() + slideInHorizontally { it }"))
        assertEquals(emptyList<MotionScan.Finding>(), MotionScan.scan("t.kt", "val a = slideInVertically { it } + fadeIn()"))
        assertEquals(
            emptyList<MotionScan.Finding>(),
            MotionScan.scan("t.kt", "exit = fadeOut(tween(90)) +\n    shrinkVertically(tween(90)),"),
        )
        assertEquals(
            emptyList<MotionScan.Finding>(),
            MotionScan.scan("t.kt", "AnimatedContent(s, transitionSpec = { slideInVertically { it } togetherWith slideOutVertically { -it } }) { }"),
        )
    }

    @Test
    fun `alpha animated alone is caught`() {
        assertTrue(flagged("Modifier.alpha(progress)"))
        assertTrue(flagged("Modifier.graphicsLayer { alpha = state.value }"))
        assertTrue(flagged("val fade by animateFloatAsState(1f)"))
        assertEquals(emptyList<MotionScan.Finding>(), MotionScan.scan("t.kt", "Modifier.alpha(0.5f)"))
        assertEquals(
            emptyList<MotionScan.Finding>(),
            MotionScan.scan("t.kt", "Modifier.graphicsLayer { alpha = a.value; translationY = (1f - a.value) * 40f }"),
        )
    }

    @Test
    fun `comments are ignored`() {
        assertEquals(emptyList<MotionScan.Finding>(), MotionScan.scan("t.kt", "// không dùng fadeIn() hay Crossfade(\n/* fadeOut() */ val x = 1"))
    }

    @Test
    fun `reduced fade requires the fixed clock and guarded callers`() {
        val helper = "fun ShortFade() { withContext(FadeDurationScale) { alpha.animateTo(0f, tween(MotionMs.REDUCED_FADE_MS)) }; Modifier.graphicsLayer { alpha = state.value } }"
        assertTrue(MotionScan.scan("helper.kt", helper).isEmpty())
        assertTrue(MotionScan.scan("helper.kt", helper.replace("withContext(FadeDurationScale)", "launch")).isNotEmpty())
        assertTrue(MotionScan.unguardedReducedCalls(mapOf("helper.kt" to helper, "host.kt" to "if (rememberReducedMotion()) { ShortFade() }")).isEmpty())
        assertEquals(1, MotionScan.unguardedReducedCalls(mapOf("helper.kt" to helper, "host.kt" to "ShortFade()")).size)
        assertEquals(1, MotionScan.unguardedReducedCalls(mapOf("helper.kt" to helper, "host.kt" to "if (!rememberReducedMotion()) { ShortFade() }")).size)
        // A surface that selects normal/reduced motion internally is not a reduced-only helper.
        val surface = "fun Surface() { val reduced = rememberReducedMotion(); if (reduced) { withContext(FadeDurationScale) { alpha.animateTo(1f, tween(MotionMs.REDUCED_FADE_MS)) } } else normalMotion() }"
        assertTrue(MotionScan.reducedFadeScopes(surface).isEmpty())
        assertTrue(MotionScan.unguardedReducedCalls(mapOf("surface.kt" to surface, "host.kt" to "Surface()")).isEmpty())
    }

    @Test
    fun `skeleton clock exemption does not hide an unrelated alpha`() {
        val pulse = "val opacity by transition.animateFloat(initialValue = 1f, targetValue = MotionMs.SKELETON_LOW, animationSpec = infiniteRepeatable(tween(MotionMs.SKELETON_PERIOD_MS / 2), RepeatMode.Reverse)); graphicsLayer { alpha = opacity }"
        assertTrue(MotionScan.scan("pulse.kt", pulse).isEmpty())
        assertTrue(MotionScan.scan("pulse.kt", pulse.replace("alpha = opacity", "alpha = unrelated")).isNotEmpty())
    }

    @Test
    fun `finding carries the right line`() {
        val findings = MotionScan.scan("t.kt", "val a = 1\nval b = 2\nval c = fadeIn()\n")
        assertEquals(3, findings.single().line)
    }
}
