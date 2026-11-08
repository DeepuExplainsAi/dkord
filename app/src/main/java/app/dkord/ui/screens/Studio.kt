@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.dkord.ui.screens

import androidx.compose.material.icons.automirrored.filled.ArrowBack

import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.work.WorkInfo
import app.dkord.R
import app.dkord.core.Track
import app.dkord.data.db.DownloadState
import app.dkord.data.db.toTrack
import app.dkord.data.download.DownloadManager
import app.dkord.data.download.DownloadStorage
import app.dkord.data.studio.*
import app.dkord.ui.common.TextInputDialog
import app.dkord.ui.common.koinVm
import app.dkord.ui.common.shareTrack
import app.dkord.ui.studio.*
import kotlinx.coroutines.flow.flowOf
import org.koin.compose.koinInject
import java.util.UUID

@Composable
internal fun StudioScreen(initialTrack: Track?, onPlay: (List<Track>, Int) -> Unit, onMenu: (Track) -> Unit, onMessage: (String) -> Unit, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo: StudioRepository = koinInject()
    val downloads: DownloadManager = koinInject()
    val online: StudioOnlineImporter = koinInject()
    val vm = koinVm { StudioViewModel(repo, downloads, online) }
    val library by repo.state.collectAsState()
    val busy by vm.busy.collectAsState()
    val importing by vm.importing.collectAsState()
    val preparation by vm.preparation.collectAsState()
    val entries by remember { downloads.downloads() }.collectAsState(emptyList())
    val context = LocalContext.current
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    val project = library.projects.firstOrNull { it.id == selected }
    var create by rememberSaveable { mutableStateOf(false) }
    var rename by rememberSaveable { mutableStateOf(false) }
    var deleting by rememberSaveable { mutableStateOf(false) }
    var downloadedPicker by rememberSaveable { mutableStateOf(false) }
    var onlinePicker by rememberSaveable { mutableStateOf(false) }
    var edit by remember { mutableStateOf<ClipEdit?>(null) }
    var preview by remember { mutableStateOf(false) }
    var importProject by rememberSaveable { mutableStateOf<String?>(null) }
    var copyTrack by rememberSaveable { mutableStateOf<String?>(null) }
    val pickAudio = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        val id = importProject
        if (id != null && uris.isNotEmpty()) vm.importAudio(id, uris)
    }
    val saveCopy = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/mp4")) { uri ->
        val track = copyTrack
        if (uri != null && track != null) vm.copyOutput(track, uri)
    }
    val requestId = project?.lastRequestId
    val work by remember(requestId) {
        requestId?.let { repo.work.getWorkInfoByIdFlow(UUID.fromString(it)) } ?: flowOf<WorkInfo?>(null)
    }.collectAsState(null)
    val activeWork by remember { repo.work.getWorkInfosByTagFlow(StudioRepository.WORK_TAG) }.collectAsState(emptyList())
    val exporting = activeWork.any { !it.state.isFinished }
    LaunchedEffect(vm, context) { vm.messages.collect { onMessage(context.getString(it)) } }
    BackHandler(selected != null) { selected = null; edit = null; preview = false }

    if (create) TextInputDialog(stringResource(R.string.studio_new), "", stringResource(R.string.create), { create = false }) {
        create = false; vm.create(it) { id -> selected = id }
    }
    if (rename && project != null) TextInputDialog(stringResource(R.string.rename), project.name, stringResource(R.string.save), { rename = false }) { text ->
        rename = false; vm.change(project.id) { it.copy(name = text.trim().take(160)) }
    }
    if (deleting && project != null) AlertDialog(onDismissRequest = { deleting = false },
        title = { Text(stringResource(R.string.studio_delete)) }, text = { Text(stringResource(R.string.studio_delete_hint)) },
        confirmButton = { TextButton({ deleting = false; vm.delete(project.id) { selected = null } }) { Text(stringResource(R.string.delete)) } },
        dismissButton = { TextButton({ deleting = false }) { Text(stringResource(R.string.cancel)) } })
    edit?.let { item -> if (project != null) ClipEditor(item, repo, { edit = null }) { start, end ->
        edit = null
        vm.change(project.id) { it.withClip(item.source.id, start, end, item.clip?.id ?: studioId()) }
    } }
    if (onlinePicker && project != null) StudioSongPicker(onSelect = { track ->
        onlinePicker = false; vm.useTrack(project.id, track)
    }, onDismiss = { onlinePicker = false })
    if (preview && project != null) ArrangementPreview(project, repo) { preview = false }
    if (downloadedPicker && project != null) ModalBottomSheet(onDismissRequest = { downloadedPicker = false }) {
        Text(stringResource(R.string.studio_downloads), Modifier.padding(16.dp), style = MaterialTheme.typography.titleLarge)
        val done = entries.filter { it.download.state == DownloadState.DONE }
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 440.dp)) {
            if (done.isEmpty()) item { Text(stringResource(R.string.studio_no_downloads), Modifier.padding(16.dp)) }
            items(done, key = { it.track.id }) { entry -> ListItem(
                modifier = Modifier.clickable { downloadedPicker = false; vm.importDownload(project.id, entry.track.toTrack()) },
                headlineContent = { Text(entry.track.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },
                supportingContent = { Text(entry.track.artist, maxLines = 1) }) }
        }
        Spacer(Modifier.height(24.dp))
    }

    Column(modifier.fillMaxSize()) {
        TopAppBar(title = { Text(stringResource(R.string.studio_title), maxLines = 1, overflow = TextOverflow.Ellipsis) }, navigationIcon = {
            IconButton({ if (selected != null) selected = null else onBack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) }
        })
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (library.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            else if (library.failed) item {
                Text(stringResource(R.string.studio_read_failed))
                TextButton(repo::reload) { Text(stringResource(R.string.retry)) }
            } else if (project == null) {
                item {
                    Text(stringResource(R.string.studio_intro))
                    Button({ create = true }, enabled = !busy) { Text(stringResource(R.string.studio_new)) }
                    if (initialTrack != null) Text(stringResource(R.string.studio_choose_project, initialTrack.title))
                }
                items(library.projects, key = { it.id }) { saved -> OutlinedCard(Modifier.fillMaxWidth().clickable { selected = saved.id }) {
                    Column(Modifier.padding(16.dp)) {
                        Text(saved.name, style = MaterialTheme.typography.titleMedium)
                        Text(stringResource(R.string.studio_total, studioTime(saved.durationMs)))
                    }
                } }
            } else {
                item {
                    TextButton({ selected = null }) { Text(stringResource(R.string.studio_projects)) }
                    Text(project.name, style = MaterialTheme.typography.headlineSmall)
                    Text(stringResource(R.string.studio_total, studioTime(project.durationMs)))
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton({ rename = true }, enabled = !busy) { Text(stringResource(R.string.rename)) }
                        TextButton({ deleting = true }, enabled = !busy) { Text(stringResource(R.string.delete)) }
                    }
                    Text(stringResource(R.string.studio_sources_hint), style = MaterialTheme.typography.bodySmall)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({ importProject = project.id; pickAudio.launch(arrayOf("audio/*")) }, enabled = !busy) { Text(stringResource(R.string.studio_device_audio)) }
                        OutlinedButton({ downloadedPicker = true }, enabled = !busy) { Text(stringResource(R.string.studio_downloads)) }
                        OutlinedButton({ onlinePicker = true }, enabled = !busy) { Text(stringResource(R.string.studio_online_search)) }
                    }
                }
                if (initialTrack != null) item {
                    val status = entries.firstOrNull { it.track.id == initialTrack.id }?.download?.state
                    OutlinedCard {
                        Column(Modifier.padding(12.dp)) {
                            Text(initialTrack.title, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Button({ vm.useTrack(project.id, initialTrack) }, enabled = !busy) {
                                Text(stringResource(if (status == DownloadState.DONE) R.string.studio_add_source else R.string.studio_use_online))
                            }
                        }
                    }
                }
                if (importing) item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(24.dp)); Text(stringResource(if (preparation != null) R.string.studio_preparing_online else R.string.studio_importing), Modifier.weight(1f).padding(8.dp))
                        TextButton(vm::cancelImport) { Text(stringResource(R.string.cancel)) }
                    }
                }
                preparation?.fraction?.let { fraction -> item {
                    LinearProgressIndicator(progress = { fraction }, modifier = Modifier.fillMaxWidth())
                } }
                item { Text(stringResource(R.string.studio_sources), style = MaterialTheme.typography.titleMedium) }
                items(project.sources, key = { "source-${it.id}" }) { source ->
                    OutlinedCard(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp)) {
                            Text(source.title, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(studioTime(source.durationMs), style = MaterialTheme.typography.bodySmall)
                            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                TextButton({ edit = ClipEdit(source) }, enabled = !busy) { Text(stringResource(R.string.studio_add_clip)) }
                                TextButton({ vm.change(project.id) { p -> p.copy(sources = p.sources.filterNot { it.id == source.id }, clips = p.clips.filterNot { it.sourceId == source.id }) } }, enabled = !busy) {
                                    Text(stringResource(R.string.remove))
                                }
                            }
                        }
                    }
                }
                item { Text(stringResource(R.string.studio_clips), style = MaterialTheme.typography.titleMedium) }
                if (project.clips.isEmpty()) item { Text(stringResource(R.string.studio_no_clips)) }
                items(project.clips, key = { "clip-${it.id}" }) { clip ->
                    val source = project.sources.first { it.id == clip.sourceId }
                    val index = project.clips.indexOf(clip)
                    ElevatedCard(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp)) {
                            Text(stringResource(R.string.studio_clip_title, index + 1, source.title), maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(stringResource(R.string.studio_clip_times, studioTime(clip.startMs), studioTime(clip.endMs), studioTime(clip.durationMs)), style = MaterialTheme.typography.bodySmall)
                            FlowRow(verticalArrangement = Arrangement.Center) {
                                TextButton({ edit = ClipEdit(source, clip) }, enabled = !busy) { Text(stringResource(R.string.studio_edit_clip)) }
                                IconButton({ vm.change(project.id) { it.moveClip(clip.id, -1) } }, enabled = !busy && index > 0) { Icon(Icons.Default.ArrowUpward, stringResource(R.string.move_up)) }
                                IconButton({ vm.change(project.id) { it.moveClip(clip.id, 1) } }, enabled = !busy && index < project.clips.lastIndex) { Icon(Icons.Default.ArrowDownward, stringResource(R.string.move_down)) }
                                IconButton({ vm.change(project.id) { it.copy(clips = it.clips.filterNot { c -> c.id == clip.id }) } }, enabled = !busy) { Icon(Icons.Default.Close, stringResource(R.string.remove)) }
                            }
                        }
                    }
                }
                item {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({ preview = true }, enabled = project.clips.isNotEmpty() && !busy) { Text(stringResource(R.string.studio_preview)) }
                        Button({ vm.export(project.id) }, enabled = project.clips.isNotEmpty() && !busy && !exporting) { Text(stringResource(R.string.studio_merge)) }
                    }
                    if (work != null) {
                        val info = requireNotNull(work)
                        when (info.state) {
                            WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED -> {
                                Text(stringResource(R.string.studio_exporting))
                                val fraction = info.progress.getInt("progress", -1)
                                if (fraction >= 0) {
                                    LinearProgressIndicator(progress = { fraction / 100f }, modifier = Modifier.fillMaxWidth())
                                    Text(stringResource(R.string.studio_progress, fraction))
                                } else LinearProgressIndicator(Modifier.fillMaxWidth())
                                TextButton({ requestId?.let(repo::cancelExport) }) { Text(stringResource(R.string.cancel)) }
                                Text(stringResource(R.string.studio_snapshot_hint), style = MaterialTheme.typography.bodySmall)
                            }
                            WorkInfo.State.FAILED -> Text(stringResource(R.string.studio_export_failed), color = MaterialTheme.colorScheme.error)
                            WorkInfo.State.CANCELLED -> Text(stringResource(R.string.studio_cancelled))
                            WorkInfo.State.SUCCEEDED -> Text(stringResource(R.string.studio_saved))
                        }
                    }
                    if (exporting && work?.state?.isFinished != false) Text(stringResource(R.string.studio_other_export))
                }
                project.lastExport?.let { output -> item {
                    OutlinedCard(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp)) {
                            Text(output.title, style = MaterialTheme.typography.titleMedium)
                            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                TextButton({ onPlay(listOf(output), 0) }) { Text(stringResource(R.string.play)) }
                                TextButton({ copyTrack = output.id; saveCopy.launch(DownloadStorage.safeName("", output.title, "m4a")) }, enabled = !busy) { Text(stringResource(R.string.studio_save_copy)) }
                                TextButton({ shareTrack(context, output) }) { Text(stringResource(R.string.share)) }
                                IconButton({ onMenu(output) }) { Icon(Icons.Default.MoreVert, stringResource(R.string.more)) }
                            }
                        }
                    }
                } }
            }
        }

    }
}
