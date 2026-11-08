package app.dkord.ui.studio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import app.dkord.R
import app.dkord.core.Track
import app.dkord.data.search.MusicSearchSource
import app.dkord.data.yt.MusicRepository
import org.koin.compose.koinInject

@Composable
internal fun StudioSongPicker(onSelect: (Track) -> Unit, onDismiss: () -> Unit) {
    val music: MusicRepository = koinInject()
    val scope = rememberCoroutineScope()
    val controller = remember(music, scope) { StudioSongSearch(MusicSearchSource(music), scope) }
    StudioSongPickerContent(controller, onSelect, onDismiss)
}

@Composable
internal fun StudioSongPickerContent(controller: StudioSongSearch, onSelect: (Track) -> Unit, onDismiss: () -> Unit) {
    val ownerContext = LocalContext.current
    val ownerDensity = LocalDensity.current
    val result by controller.state.collectAsState()
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        CompositionLocalProvider(LocalContext provides ownerContext, LocalDensity provides ownerDensity) {
            val keyboard = LocalSoftwareKeyboardController.current
            val focus = LocalFocusManager.current
            fun submit() { keyboard?.hide(); focus.clearFocus(); controller.search() }
            Surface(Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp), shape = MaterialTheme.shapes.large) {
                Column(Modifier.fillMaxSize().padding(16.dp)) {
                    Text(stringResource(R.string.studio_online_search), style = MaterialTheme.typography.titleLarge)
                    Text(stringResource(R.string.studio_online_hint), style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    OutlinedTextField(result.query, controller::typed, Modifier.fillMaxWidth().testTag("studio-song-query"),
                        singleLine = true, label = { Text(stringResource(R.string.search_submit)) },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { submit() }))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton({ submit() }, enabled = result.query.isNotBlank() && !result.loading) { Text(stringResource(R.string.search_submit)) }
                        TextButton(onDismiss) { Text(stringResource(R.string.close)) }
                    }
                    if (result.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                    if (result.failed) TextButton(controller::search) { Text(stringResource(R.string.retry)) }
                    LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("studio-song-results")) {
                        if (result.submitted && !result.loading && !result.failed && result.tracks.isEmpty()) item {
                            Text(stringResource(R.string.studio_search_empty))
                        }
                        items(result.tracks, key = { it.id }) { track ->
                            ListItem(modifier = Modifier.clickable { onSelect(track) }.testTag("studio-song-${track.id}"),
                                headlineContent = { Text(track.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },
                                supportingContent = { Text(track.artist, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                                trailingContent = { TextButton({ onSelect(track) }) { Text(stringResource(R.string.studio_source_add)) } })
                        }
                        if (result.hasMore) item {
                            TextButton(controller::more, enabled = !result.more, modifier = Modifier.fillMaxWidth()) {
                                Text(stringResource(if (result.moreFailed) R.string.retry else R.string.more))
                            }
                        }
                    }
                }
            }
        }
    }
}
