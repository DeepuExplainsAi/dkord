@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.dkord.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.dkord.R
import app.dkord.core.*
import app.dkord.player.PlayerUiState
import app.dkord.ui.common.Actions
import app.dkord.ui.common.Cover
import app.dkord.ui.common.TrackRow
import app.dkord.ui.common.formatTime
import app.dkord.ui.common.koinVm
import app.dkord.ui.listen.ListenAgainViewModel
import app.dkord.ui.listen.ListeningData
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.isActive
import org.koin.compose.koinInject
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

@Composable
fun ListenAgainScreen(
    onPlay: (List<Track>, Int) -> Unit,
    onMenu: (Track) -> Unit,
    onOpenPlayer: () -> Unit,
    onSearch: () -> Unit,
    onMessage: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val actions: Actions = koinInject()
    val vm = koinVm { ListenAgainViewModel(actions.library, actions.downloads) }
    val data by vm.state.collectAsState()
    val playback by actions.player.state.collectAsState()
    val error = stringResource(R.string.listen_action_failed)
    LaunchedEffect(vm, error) { vm.errors.collect { onMessage(error) } }
    ListenAgainContent(data, playback,
        onPlay = { onPlay(listOf(it), 0) },
        onPlayAll = { actions.player.setShuffle(false); onPlay(it, 0) },
        onMenu = onMenu,
        onResume = { actions.player.resume(); onOpenPlayer() },
        onOpenPlayer = onOpenPlayer, onSearch = onSearch,
        onRemove = vm::remove, onClear = vm::clear, onRetry = vm::retry, modifier = modifier)
}

/** No provider-discovery/playback side effects. Only explicit callbacks start audio or change history. */
@Composable
internal fun ListenAgainContent(
    data: ListeningData,
    playback: PlayerUiState,
    onPlay: (Track) -> Unit,
    onPlayAll: (List<Track>) -> Unit,
    onMenu: (Track) -> Unit,
    onResume: () -> Unit,
    onOpenPlayer: () -> Unit,
    onSearch: () -> Unit,
    onRemove: (String) -> Unit,
    onClear: () -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf(ListeningFilter.ALL) }
    var managing by rememberSaveable { mutableStateOf(false) }
    var clearing by rememberSaveable { mutableStateOf(false) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    fun finishTyping() { keyboard?.hide(); focus.clearFocus() }
    val visible = remember(data.entries, data.likedIds, data.downloadedIds, query, filter) {
        listeningHistory(data.entries, query, filter, data.likedIds, data.downloadedIds)
    }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (isActive) { now = System.currentTimeMillis(); delay(60_000) } }
    val locale = LocalContext.current.resources.configuration.locales[0]
    val zone = ZoneId.systemDefault()
    val clock = remember(locale, zone) { DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT).withLocale(locale).withZone(zone) }
    val groups = remember(visible, now, zone) { visible.groupBy { listeningDay(it.playedAtMs, now, zone) } }
    val canManage = data.entries.isNotEmpty() && !data.loading && !data.failed && !data.changing

    if (clearing) {
        val title = stringResource(R.string.listen_clear_title)
        val text = stringResource(R.string.listen_clear_message)
        val confirm = stringResource(R.string.listen_clear)
        val cancel = stringResource(R.string.cancel)
        val context = LocalContext.current
        val density = LocalDensity.current
        AlertDialog(onDismissRequest = { clearing = false },
            title = { CompositionLocalProvider(LocalContext provides context, LocalDensity provides density) { Text(title) } },
            text = { CompositionLocalProvider(LocalContext provides context, LocalDensity provides density) { Text(text) } },
            confirmButton = { CompositionLocalProvider(LocalContext provides context, LocalDensity provides density) {
                TextButton({ clearing = false; onClear() }, enabled = !data.changing, modifier = Modifier.testTag("listen-confirm-clear")) { Text(confirm) }
            } },
            dismissButton = { CompositionLocalProvider(LocalContext provides context, LocalDensity provides density) {
                TextButton({ clearing = false }) { Text(cancel) }
            } })
    }

    LazyColumn(modifier.fillMaxSize().testTag("listen-list"), contentPadding = PaddingValues(bottom = 24.dp)) {
        item("title") {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(stringResource(R.string.listen_title), style = MaterialTheme.typography.headlineSmall)
                Text(stringResource(R.string.listen_hint), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        playback.current?.let { track -> item("continue") {
            Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp).testTag("listen-continue").clickable(onClick = onOpenPlayer)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(stringResource(if (playback.isPlaying || playback.isBuffering) R.string.listen_now_playing else R.string.listen_continue), style = MaterialTheme.typography.labelLarge)
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Cover(track.thumbnail, 64.dp)
                        Column(Modifier.weight(1f)) {
                            Text(track.title, style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(track.artist, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        FilledIconButton(if (playback.isPlaying || playback.isBuffering) onOpenPlayer else onResume,
                            Modifier.testTag("listen-resume"), enabled = playback.connected) {
                            Icon(if (playback.isPlaying || playback.isBuffering) Icons.Default.History else Icons.Default.PlayArrow,
                                stringResource(if (playback.isPlaying || playback.isBuffering) R.string.listen_open_player else R.string.resume))
                        }
                    }
                    if (playback.durationMs > 0) {
                        LinearProgressIndicator(progress = { listeningProgress(playback.positionMs, playback.durationMs) }, modifier = Modifier.fillMaxWidth())
                        Text(stringResource(R.string.listen_position, formatTime(playback.positionMs), formatTime(playback.durationMs)), style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        } }
        item("history-header") {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Text(stringResource(R.string.recently_played), style = MaterialTheme.typography.titleLarge)
                FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (data.entries.isNotEmpty()) Text(pluralStringResource(R.plurals.n_songs, data.entries.size, data.entries.size), Modifier.padding(vertical = 12.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    TextButton({ finishTyping(); managing = !managing }, enabled = (managing || canManage) && !data.changing, modifier = Modifier.testTag("listen-manage")) {
                        Text(stringResource(if (managing) R.string.listen_done else R.string.listen_manage), maxLines = 1)
                    }
                    if (managing) TextButton({ finishTyping(); clearing = true }, enabled = canManage, modifier = Modifier.testTag("listen-clear-history")) {
                        Text(stringResource(R.string.listen_clear), maxLines = 1, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
        if (data.entries.isNotEmpty() || query.isNotBlank() || filter != ListeningFilter.ALL) {
            item("query") {
                OutlinedTextField(query, { query = it.take(200) }, Modifier.fillMaxWidth().padding(horizontal = 16.dp).testTag("listen-search"),
                    singleLine = true, label = { Text(stringResource(R.string.listen_search)) },
                    leadingIcon = { Icon(Icons.Default.Search, null) },
                    trailingIcon = { if (query.isNotEmpty()) IconButton({ query = "" }) { Icon(Icons.Default.Clear, stringResource(R.string.clear)) } },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), keyboardActions = KeyboardActions(onSearch = { finishTyping() }))
            }
            item("filters") {
                LazyRow(modifier = Modifier.testTag("listen-filters"), contentPadding = PaddingValues(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(ListeningFilter.entries, key = { it.name }) { value ->
                        val label = when (value) {
                            ListeningFilter.ALL -> R.string.release_all
                            ListeningFilter.LIKED -> R.string.listen_liked
                            ListeningFilter.DOWNLOADED -> R.string.listen_downloaded
                        }
                        FilterChip(filter == value, { finishTyping(); filter = value }, { Text(stringResource(label), maxLines = 1) },
                            modifier = Modifier.testTag("listen-filter-${value.name}"))
                    }
                }
            }
        }
        if (data.loading) item("loading") { Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
        if (data.failed) item("failed") {
            Column(Modifier.padding(16.dp)) {
                Text(stringResource(R.string.listen_load_failed), color = MaterialTheme.colorScheme.error)
                TextButton(onRetry) { Text(stringResource(R.string.retry)) }
            }
        }
        if (!data.loading && !data.failed && visible.isEmpty()) item("empty") {
            Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Default.History, null, Modifier.size(40.dp), tint = MaterialTheme.colorScheme.primary)
                Text(stringResource(if (data.entries.isEmpty()) R.string.no_recent else R.string.listen_no_match), style = MaterialTheme.typography.titleMedium)
                if (data.entries.isEmpty()) {
                    Text(stringResource(R.string.listen_empty_hint), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Button(onSearch) { Text(stringResource(R.string.search_submit)) }
                } else TextButton({ finishTyping(); query = ""; filter = ListeningFilter.ALL }) { Text(stringResource(R.string.listen_reset)) }
            }
        }
        if (visible.isNotEmpty()) item("play-all") {
            TextButton({ finishTyping(); onPlayAll(visible.map { it.track }) }, Modifier.padding(horizontal = 16.dp).testTag("listen-play-all")) {
                Icon(Icons.Default.PlayArrow, null)
                Text(stringResource(R.string.listen_play_all), Modifier.padding(start = 6.dp))
            }
        }
        groups.forEach { (day, entries) ->
            item("day-${day.name}") {
                val title = when (day) {
                    ListeningDay.TODAY -> R.string.listen_today
                    ListeningDay.YESTERDAY -> R.string.listen_yesterday
                    ListeningDay.EARLIER -> R.string.listen_earlier
                }
                Text(stringResource(title), Modifier.padding(horizontal = 16.dp, vertical = 12.dp), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            }
            items(entries, key = { "history-${it.track.id}" }) { entry ->
                val track = entry.track
                TrackRow(track, Modifier.testTag("listen-track-${track.id}"), playing = playback.current?.id == track.id,
                    onClick = { finishTyping(); onPlay(track) }, onMenu = { onMenu(track) },
                    supporting = listOf(track.artist, clock.format(Instant.ofEpochMilli(entry.playedAtMs))).filter { it.isNotBlank() }.joinToString(" · "),
                    trailing = if (managing) { {
                        IconButton({ onRemove(track.id) }, enabled = !data.changing) {
                            Icon(Icons.Default.DeleteOutline, stringResource(R.string.listen_remove, track.title))
                        }
                    } } else null)
            }
        }
    }
}
