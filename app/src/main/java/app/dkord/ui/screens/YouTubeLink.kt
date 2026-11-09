package app.dkord.ui.screens

import android.content.ClipboardManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.dkord.R
import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track
import app.dkord.data.links.YouTubeLinkProblem
import app.dkord.data.links.YouTubeLinkSource
import app.dkord.ui.common.BrowseRow
import app.dkord.ui.common.koinVm
import app.dkord.ui.links.YouTubeLinkController
import org.koin.compose.koinInject

class YouTubeLinkViewModel(source: YouTubeLinkSource) : ViewModel() {
    val controller = YouTubeLinkController(source, viewModelScope)
}

@Composable
fun YouTubeLinkScreen(onBack: () -> Unit, onPlay: (List<Track>, Int) -> Unit, onMenu: (Track) -> Unit, onMessage: (String) -> Unit) {
    val source: YouTubeLinkSource = koinInject()
    val vm = koinVm { YouTubeLinkViewModel(source) }
    YouTubeLinkPage(vm.controller, onBack, onPlay, onMenu, onMessage)
}

/** A labelled, separate action; a URL is never treated as an ordinary saved search. */
@Composable
internal fun YouTubeLinkEntry(onClick: () -> Unit, modifier: Modifier = Modifier) {
    OutlinedButton(onClick, modifier.testTag("open-youtube-link")) {
        Icon(Icons.Default.Link, null, Modifier.padding(end = 8.dp).size(20.dp))
        Text(stringResource(R.string.youtube_link_open))
    }
}

/** Production page, independently exercised with an offline source on real Android. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun YouTubeLinkPage(
    controller: YouTubeLinkController,
    onBack: () -> Unit,
    onPlay: (List<Track>, Int) -> Unit,
    onMenu: (Track) -> Unit,
    onMessage: (String) -> Unit = {},
) {
    val state by controller.state.collectAsState()
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    DisposableEffect(controller) { onDispose { controller.cancel() } }
    fun resolve() {
        keyboard?.hide(); focus.clearFocus()
        controller.open()
    }
    fun paste() {
        // Read plain text only, and only after a deliberate tap. Never coerce/fetch clipboard URIs.
        val text = try { context.getSystemService(ClipboardManager::class.java)?.primaryClip?.let { clip ->
            if (clip.itemCount > 0) clip.getItemAt(0).text?.toString() else null
        } } catch (_: SecurityException) { null }
        if (text.isNullOrBlank()) onMessage(context.getString(R.string.youtube_link_clipboard_empty))
        else controller.typed(text)
    }
    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = { TopAppBar(
            title = { Text(stringResource(R.string.youtube_link_open), maxLines = 1, overflow = TextOverflow.Ellipsis) },
            navigationIcon = { IconButton(onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } },
        ) },
    ) { pad ->
        LazyColumn(Modifier.fillMaxSize().padding(pad).consumeWindowInsets(pad).testTag("youtube-link-page"),
            contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item("hint") { Text(stringResource(R.string.youtube_link_hint), color = MaterialTheme.colorScheme.onSurfaceVariant) }
            item("input") { OutlinedTextField(
                value = state.input, onValueChange = controller::typed,
                modifier = Modifier.fillMaxWidth().testTag("youtube-link-input"),
                label = { Text(stringResource(R.string.youtube_link_label)) },
                placeholder = { Text("https://youtu.be/…") },
                supportingText = { Text(stringResource(R.string.youtube_link_formats)) },
                trailingIcon = { if (state.input.isNotEmpty()) IconButton({ controller.typed("") }) {
                    Icon(Icons.Default.Clear, stringResource(R.string.clear))
                } },
                singleLine = true,
                isError = state.problem == YouTubeLinkProblem.INVALID_LINK || state.problem == YouTubeLinkProblem.PLAYLIST_ONLY,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, autoCorrectEnabled = false, imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { resolve() }),
            ) }
            item("actions") { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton({ paste() }, Modifier.weight(1f).testTag("youtube-link-paste")) {
                    Icon(Icons.Default.ContentPaste, null, Modifier.padding(end = 8.dp).size(18.dp))
                    Text(stringResource(R.string.youtube_link_paste))
                }
                Button({ resolve() }, Modifier.weight(1f).testTag("youtube-link-resolve"), enabled = state.input.isNotBlank() && !state.loading) {
                    Text(stringResource(R.string.youtube_link_show))
                }
            } }
            if (state.loading) item("loading") { Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator(Modifier.size(24.dp))
                Text(stringResource(R.string.youtube_link_loading), Modifier.weight(1f))
                TextButton(controller::cancel, Modifier.testTag("youtube-link-cancel")) { Text(stringResource(R.string.cancel)) }
            } }
            state.problem?.let { problem -> item("error") { Column(Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite }) {
                Text(stringResource(linkProblemText(problem)), Modifier.testTag("youtube-link-error"), color = MaterialTheme.colorScheme.error)
                if (problem !in setOf(YouTubeLinkProblem.INVALID_LINK, YouTubeLinkProblem.PLAYLIST_ONLY)) {
                    TextButton({ resolve() }) { Text(stringResource(R.string.retry)) }
                }
            } } }
            state.track?.let { track -> item("preview") { Card(Modifier.fillMaxWidth().testTag("youtube-link-preview")) {
                Column(Modifier.padding(vertical = 8.dp)) {
                    Text(stringResource(R.string.youtube_link_preview), Modifier.padding(horizontal = 16.dp, vertical = 8.dp), style = MaterialTheme.typography.titleMedium)
                    BrowseRow(BrowseItem(ItemKind.SONG, track.id, track.title, track.artist, track.thumbnail, track = track),
                        onClick = { onPlay(listOf(track), 0) }, onMenu = { onMenu(track) })
                    state.canonicalUrl?.let { url -> SelectionContainer { Text(url,
                        Modifier.padding(horizontal = 16.dp, vertical = 8.dp), style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant) } }
                    Button({ onPlay(listOf(track), 0) }, Modifier.padding(horizontal = 16.dp, vertical = 8.dp).testTag("youtube-link-play")) {
                        Icon(Icons.Default.PlayArrow, null, Modifier.padding(end = 8.dp))
                        Text(stringResource(R.string.play))
                    }
                }
            } } }
        }
    }
}

private fun linkProblemText(problem: YouTubeLinkProblem): Int = when (problem) {
    YouTubeLinkProblem.INVALID_LINK -> R.string.youtube_link_invalid
    YouTubeLinkProblem.PLAYLIST_ONLY -> R.string.youtube_link_playlist_only
    YouTubeLinkProblem.NETWORK -> R.string.err_network
    YouTubeLinkProblem.PRIVATE -> R.string.err_private
    YouTubeLinkProblem.AGE_RESTRICTED -> R.string.err_age_restricted
    YouTubeLinkProblem.GEO -> R.string.err_geo
    YouTubeLinkProblem.BOT_CHECK -> R.string.err_bot_check
    YouTubeLinkProblem.NO_AUDIO -> R.string.err_no_audio
    YouTubeLinkProblem.UNAVAILABLE -> R.string.err_unavailable
}
