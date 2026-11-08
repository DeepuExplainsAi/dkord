package app.dkord

import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performImeAction
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import app.dkord.ui.common.KeyboardAwareScaffold
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/** Real Android IME + actual production shell; no mock keyboard-height/source-string assertion. */
@OptIn(ExperimentalMaterial3Api::class)
class SearchKeyboardViewportTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    @Volatile private var ime = 0
    @Volatile private var height = 0
    @Volatile private var bottom = 0f
    @Volatile private var density = 1f

    @Test fun suggestions_reach_the_real_keyboard_without_a_second_black_ime_gap() = verify(1f)
    @Test fun larger_font_keeps_the_keyboard_viewport_and_restores_navigation_on_submit() = verify(1.3f)

    private fun verify(scale: Float) {
        rule.activityRule.scenario.onActivity {
            it.enableEdgeToEdge()
            it.window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        }
        rule.setContent {
            val systemDensity = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(systemDensity.density, scale)) {
                MaterialTheme {
                    val keyboard = LocalSoftwareKeyboardController.current
                    val focus = LocalFocusManager.current
                    var query by remember { mutableStateOf("") }
                    val imeNow = WindowInsets.ime.getBottom(LocalDensity.current)
                    val dp = LocalDensity.current.density
                    SideEffect { ime = imeNow; density = dp }
                    Box(Modifier.fillMaxSize().onGloballyPositioned { height = it.size.height }) {
                        KeyboardAwareScaffold(bottomBar = {
                            Box(Modifier.fillMaxWidth().height(80.dp).testTag("navigation")) { Text("Navigation") }
                        }) { outer ->
                            Scaffold(
                                Modifier.fillMaxSize().padding(outer).consumeWindowInsets(outer),
                                contentWindowInsets = WindowInsets(0, 0, 0, 0),
                                topBar = { TopAppBar(title = { Text("Dkord") }) },
                            ) { inner ->
                                Column(Modifier.fillMaxSize().padding(inner).consumeWindowInsets(inner)) {
                                    OutlinedTextField(query, { query = it }, Modifier.fillMaxWidth().testTag("query"),
                                        singleLine = true, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                                        keyboardActions = KeyboardActions(onSearch = { keyboard?.hide(); focus.clearFocus() }))
                                    LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("suggestions")
                                        .onGloballyPositioned { bottom = it.boundsInRoot().bottom }) {
                                        items((1..50).toList()) { Text("Suggestion $it", Modifier.fillMaxWidth().padding(16.dp)) }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        rule.onNodeWithTag("query").performClick().performTextInput("h")
        rule.waitUntil(15_000) { ime > 0 && height > 0 && bottom > 0 }
        rule.waitForIdle()
        rule.onNodeWithTag("navigation").assertDoesNotExist()
        assertTrue("Suggestions stopped at $bottom; keyboard top ${height - ime}; IME $ime",
            kotlin.math.abs(bottom - (height - ime)) <= 6 * density)
        rule.onNodeWithTag("suggestions").assertIsDisplayed()
        rule.onNodeWithTag("query").performImeAction()
        rule.waitUntil(15_000) { ime == 0 }
        rule.onNodeWithTag("navigation").assertIsDisplayed()
    }
}
