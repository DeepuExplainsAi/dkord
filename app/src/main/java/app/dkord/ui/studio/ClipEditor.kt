@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package app.dkord.ui.studio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.media3.common.AudioAttributes
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import app.dkord.R
import app.dkord.data.studio.*
import app.dkord.ui.common.Actions
import org.koin.compose.koinInject

internal data class ClipEdit(val source: StudioSource, val clip: StudioClip? = null)

@Composable
internal fun ClipEditor(edit: ClipEdit, repo: StudioRepository, dismiss: () -> Unit, save: (Long, Long) -> Unit) {
    val clip = edit.clip
    var startText by remember(edit) { mutableStateOf(studioTime(clip?.startMs ?: 0)) }
    var endText by remember(edit) { mutableStateOf(studioTime(clip?.endMs ?: edit.source.durationMs)) }
    var durationText by remember(edit) { mutableStateOf(studioTime(clip?.durationMs ?: edit.source.durationMs)) }
    var byDuration by remember(edit) { mutableStateOf(false) }
    var preview by remember(edit) { mutableStateOf(false) }
    var failed by remember(edit) { mutableStateOf(false) }
    val start = parseStudioTime(startText)
    val length = parseStudioTime(durationText)
    val end = if (byDuration) runCatching { Math.addExact(requireNotNull(start), requireNotNull(length)) }.getOrNull() else parseStudioTime(endText)
    val valid = start != null && end != null && start >= 0 && end > start && end <= edit.source.durationMs
    AlertDialog(onDismissRequest = dismiss,
        title = { Text(stringResource(R.string.studio_edit_clip)) },
        text = {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(edit.source.title)
                Text(stringResource(R.string.studio_time_hint, studioTime(edit.source.durationMs)))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(!byDuration, { if (valid) endText = studioTime(requireNotNull(end)); byDuration = false; preview = false }, { Text(stringResource(R.string.studio_end)) })
                    FilterChip(byDuration, { if (valid) durationText = studioTime(requireNotNull(end) - requireNotNull(start)); byDuration = true; preview = false }, { Text(stringResource(R.string.studio_duration)) })
                }
                OutlinedTextField(startText, { startText = it; preview = false }, Modifier.fillMaxWidth().testTag("studio-start"), singleLine = true,
                    label = { Text(stringResource(R.string.studio_start)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text))
                if (byDuration) OutlinedTextField(durationText, { durationText = it; preview = false }, Modifier.fillMaxWidth().testTag("studio-duration"), singleLine = true,
                    label = { Text(stringResource(R.string.studio_duration)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text))
                else OutlinedTextField(endText, { endText = it; preview = false }, Modifier.fillMaxWidth().testTag("studio-end"), singleLine = true,
                    label = { Text(stringResource(R.string.studio_end)) }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text))
                if (valid) Text(stringResource(R.string.studio_clip_times, studioTime(requireNotNull(start)), studioTime(requireNotNull(end)), studioTime(requireNotNull(end) - requireNotNull(start))))
                else Text(stringResource(R.string.studio_invalid_range), color = MaterialTheme.colorScheme.error)
                TextButton({ preview = !preview; failed = false }, enabled = valid) {
                    Text(stringResource(if (preview) R.string.studio_stop_preview else R.string.studio_preview))
                }
                if (failed) Text(stringResource(R.string.studio_preview_failed), color = MaterialTheme.colorScheme.error)
                if (preview && valid) {
                    val item = runCatching { clippedItem(repo.sourceFile(edit.source), requireNotNull(start), requireNotNull(end)) }.getOrNull()
                    if (item != null) AudioPreview(listOf(item), { preview = false }) { failed = true; preview = false }
                    else Text(stringResource(R.string.studio_file_unavailable), color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = { TextButton({ if (valid) save(requireNotNull(start), requireNotNull(end)) }, enabled = valid) { Text(stringResource(R.string.save)) } },
        dismissButton = { TextButton(dismiss) { Text(stringResource(R.string.cancel)) } })
}

internal fun clippedItem(file: java.io.File, start: Long, end: Long): MediaItem = MediaItem.Builder()
    .setUri(android.net.Uri.fromFile(file)).setClippingConfiguration(
        MediaItem.ClippingConfiguration.Builder().setStartPositionMs(start).setEndPositionMs(end).build()).build()

@Composable
internal fun ArrangementPreview(project: StudioProject, repo: StudioRepository, dismiss: () -> Unit) {
    val items = remember(project) { runCatching {
        project.validate(requireClips = true)
        project.clips.map { clip -> clippedItem(repo.sourceFile(project.sources.first { it.id == clip.sourceId }), clip.startMs, clip.endMs) }
    }.getOrNull() }
    var failed by remember(project) { mutableStateOf(false) }
    AlertDialog(onDismissRequest = dismiss, title = { Text(stringResource(R.string.studio_preview)) },
        text = {
            Column {
                Text(project.name)
                Text(stringResource(R.string.studio_total, studioTime(project.durationMs)))
                if (items != null && !failed) AudioPreview(items, dismiss) { failed = true }
                else Text(stringResource(R.string.studio_preview_failed), color = MaterialTheme.colorScheme.error)
            }
        }, confirmButton = { TextButton(dismiss) { Text(stringResource(R.string.studio_stop_preview)) } })
}

/** Preview uses the same local files/ranges/order; never an online placeholder or background audio leak. */
@Composable
private fun AudioPreview(items: List<MediaItem>, ended: () -> Unit, failed: () -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val actions: Actions = koinInject()
    val player = remember(items) { ExoPlayer.Builder(context).build().apply {
        setAudioAttributes(AudioAttributes.DEFAULT, true); setHandleAudioBecomingNoisy(true)
        setMediaItems(items); prepare()
    } }
    LaunchedEffect(player) { actions.player.pause(); player.play() }
    DisposableEffect(player, lifecycle) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) { if (state == Player.STATE_ENDED) ended() }
            override fun onPlayerError(error: PlaybackException) { failed() }
        }
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_STOP) { player.pause(); ended() } }
        player.addListener(listener); lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer); player.removeListener(listener); player.release() }
    }
}
