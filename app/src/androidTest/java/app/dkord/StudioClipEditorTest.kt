package app.dkord

import android.content.ContextWrapper
import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import app.dkord.data.studio.StudioRepository
import app.dkord.data.studio.StudioSource
import app.dkord.data.studio.studioId
import app.dkord.ui.studio.ClipEdit
import app.dkord.ui.studio.ClipEditor
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.util.Locale

class StudioClipEditorTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    @Test fun english_millisecond_range_remains_editable_with_real_keyboard() = checkEditor(Locale.ENGLISH, 1f)
    @Test fun hindi_larger_font_range_has_visible_save_action_and_scrollable_fields() = checkEditor(Locale.forLanguageTag("hi"), 1.3f)
    private fun checkEditor(locale: Locale, fontScale: Float) {
        val ctx = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply { setLocale(locale) })
        val dir = File(rule.activity.cacheDir, "studio-editor-test-${studioId()}").apply { mkdirs() }
        val isolated = object : ContextWrapper(rule.activity) { override fun getFilesDir(): File = dir }
        val repo = StudioRepository(isolated)
        val id = studioId()
        val source = StudioSource(id, "PCM", "$id.audio", 2000, "audio/wav")
        var saved: Pair<Long, Long>? = null
        try {
            rule.setContent {
                val density = LocalDensity.current
                CompositionLocalProvider(LocalContext provides ctx, LocalDensity provides Density(density.density, fontScale)) {
                    MaterialTheme { ClipEditor(ClipEdit(source), repo, {}) { start, end -> saved = start to end } }
                }
            }
            rule.onNodeWithTag("studio-start").performScrollTo().performTextClearance()
            rule.onNodeWithTag("studio-start").performTextInput("0.123")
            rule.onNodeWithTag("studio-end").performScrollTo().performTextClearance()
            rule.onNodeWithTag("studio-end").performTextInput("1.234")
            val saveLabel = ctx.getString(R.string.save)
            val save = rule.onNodeWithText(saveLabel)
            try {
                save.assertExists().assertIsDisplayed().assertIsEnabled()
                // The separate dialog Window must really inherit the requested larger font.
                val height = save.fetchSemanticsNode().boundsInRoot.height
                val minTextHeight = 20f * rule.activity.resources.displayMetrics.density * fontScale * 0.85f
                org.junit.Assert.assertTrue("Owner font scale $fontScale must reach dialog text; height=$height expected>=$minTextHeight", height >= minTextHeight)
                save.performClick()
            } catch (e: AssertionError) {
                val matches = rule.onAllNodesWithText(saveLabel).fetchSemanticsNodes().map { it.boundsInRoot }
                val actual = rule.onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsProperties.Text)).fetchSemanticsNodes()
                    .flatMap { it.config[SemanticsProperties.Text].map { text -> text.text } }.joinToString(" | ").take(320)
                throw AssertionError("Expected Save=$saveLabel font=$fontScale matches=$matches; actual labels=$actual; ${e.message?.lineSequence()?.firstOrNull()}", e)
            }
            rule.runOnIdle { assertEquals(123L to 1234L, saved) }
        } finally { dir.deleteRecursively() }
    }
}
