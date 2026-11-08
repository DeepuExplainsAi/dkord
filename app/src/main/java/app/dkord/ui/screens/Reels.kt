@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package app.dkord.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.pager.VerticalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewModelScope
import androidx.media3.common.AudioAttributes
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import app.dkord.R
import app.dkord.core.Track
import app.dkord.data.net.Http
import app.dkord.data.shorts.*
import app.dkord.data.stream.ResolvedVideo
import app.dkord.data.stream.VideoResolver
import app.dkord.data.yt.MusicRepository
import app.dkord.data.yt.SearchFilter
import app.dkord.player.OpenRangeResolver
import app.dkord.ui.common.Actions
import app.dkord.ui.common.BrowseRow
import app.dkord.ui.common.koinVm
import app.dkord.ui.shorts.ShortsController
import coil3.compose.AsyncImage
import kotlinx.coroutines.CancellationException
import org.koin.compose.koinInject

internal class ReelsViewModel(source: ShortsSource) : ViewModel() {
    val controller = ShortsController(source, viewModelScope)
}

@Composable
fun ReelsScreen(onPlay: (List<Track>, Int) -> Unit, modifier: Modifier = Modifier) {
    val source: ShortsRepository = koinInject()
    val actions: Actions = koinInject()
    val vm = koinVm { ReelsViewModel(source) }
    val state by vm.controller.state.collectAsState()
    var query by rememberSaveable { mutableStateOf(state.query) }
    var songClip by remember { mutableStateOf<MusicClip?>(null) }
    var paused by remember { mutableStateOf(false) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    val pager = rememberPagerState { state.clips.size }
    fun search() { keyboard?.hide(); focus.clearFocus(); paused = true; vm.controller.search(query) }
    LaunchedEffect(vm) { vm.controller.initial() }
    LaunchedEffect(state.query, state.clips.firstOrNull()?.id) { if (state.clips.isNotEmpty()) pager.scrollToPage(0) }
    val currentId = state.clips.getOrNull(pager.settledPage)?.id
    LaunchedEffect(currentId) {
        if (currentId != null) { paused = false; actions.player.pause() }
    }
    // Appending a page must NOT resume the clip or pause a full song the user just chose.
    LaunchedEffect(pager.settledPage, state.clips.size) {
        if (state.clips.isNotEmpty() && pager.settledPage >= state.clips.size - 3) vm.controller.more()
    }
    Column(modifier.fillMaxSize().background(Color.Black)) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(query, { query = it.take(200) }, Modifier.weight(1f), singleLine = true,
                placeholder = { Text(stringResource(R.string.reels_query), maxLines = 1) },
                colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White,
                    focusedPlaceholderColor = Color.LightGray, unfocusedPlaceholderColor = Color.LightGray,
                    focusedBorderColor = Color.White, unfocusedBorderColor = Color.LightGray, cursorColor = Color.White),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { search() }))
            IconButton({ search() }, enabled = query.isNotBlank()) { Icon(Icons.Default.Search, stringResource(R.string.search_submit), tint = Color.White) }
        }
        if (state.fromCreators && state.clips.isNotEmpty()) Text(stringResource(R.string.reels_creator_discovery),
            Modifier.padding(horizontal = 16.dp, vertical = 4.dp), color = Color.LightGray, style = MaterialTheme.typography.labelSmall)
        Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
            if (state.clips.isNotEmpty()) VerticalPager(pager, Modifier.fillMaxSize()) { page ->
                val clip = state.clips[page]
                Box(Modifier.fillMaxSize()) {
                    AsyncImage(clip.thumbnail, null, Modifier.fillMaxSize())
                    if (page == pager.settledPage) ClipVideo(clip.id, paused || songClip != null, { paused = true })
                    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color.Transparent, Color.Transparent, Color.Black))))
                    IconButton({ paused = !paused }, Modifier.align(Alignment.TopEnd)) {
                        Icon(if (paused) Icons.Default.PlayArrow else Icons.Default.Pause,
                            stringResource(if (paused) R.string.play else R.string.pause), tint = Color.White)
                    }
                    Column(Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(20.dp)) {
                        Text(clip.title, color = Color.White, maxLines = 3, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleMedium)
                        Text(clip.creator, color = Color.LightGray, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Button({ paused = true; songClip = clip }) { Text(stringResource(R.string.reels_full_song)) }
                        if (page == state.clips.lastIndex && state.failed) TextButton(vm.controller::retry) { Text(stringResource(R.string.retry)) }
                        else if (page == state.clips.lastIndex && state.next != null && !state.loading) TextButton(vm.controller::more) { Text(stringResource(R.string.search_load_more)) }
                    }
                }
            } else Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                if (state.loading) CircularProgressIndicator()
                else {
                    Text(stringResource(if (state.failed) R.string.reels_failed else R.string.reels_empty), color = Color.White)
                    TextButton(if (state.next != null) vm.controller::more else vm.controller::retry) { Text(stringResource(R.string.retry)) }
                }
            }
            if (state.loading && state.clips.isNotEmpty()) CircularProgressIndicator(Modifier.align(Alignment.TopCenter).padding(12.dp).size(24.dp))
        }
    }
    songClip?.let { clip -> FullSongSheet(clip, { songClip = null }) { track ->
        paused = true; songClip = null; onPlay(listOf(track), 0)
    } }
}

@Composable
private fun ClipVideo(id: String, paused: Boolean, stopped: () -> Unit) {
    var video by remember(id) { mutableStateOf<ResolvedVideo?>(null) }
    var failed by remember(id) { mutableStateOf(false) }
    var retry by remember(id) { mutableIntStateOf(0) }
    LaunchedEffect(id, retry) {
        failed = false; video = null
        try { video = VideoResolver().resolve(id) }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { failed = true }
    }
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        val resolved = video
        when {
            failed -> Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(stringResource(R.string.video_failed), color = Color.White)
                TextButton({ retry++ }) { Text(stringResource(R.string.retry)) }
            }
            resolved == null -> CircularProgressIndicator()
            else -> ClipSurface(resolved, paused, stopped) { failed = true }
        }
    }
}

@Composable
private fun ClipSurface(video: ResolvedVideo, paused: Boolean, stopped: () -> Unit, failed: () -> Unit) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val player = remember(video) {
        val source = ResolvingDataSource.Factory(OkHttpDataSource.Factory(Http.client), OpenRangeResolver())
        ExoPlayer.Builder(context).setMediaSourceFactory(DefaultMediaSourceFactory(source)).build().apply {
            setAudioAttributes(AudioAttributes.DEFAULT, true)
            setHandleAudioBecomingNoisy(true)
            repeatMode = Player.REPEAT_MODE_ONE
            setMediaItem(MediaItem.fromUri(video.video.url)); prepare()
        }
    }
    LaunchedEffect(player, paused) { player.playWhenReady = !paused }
    DisposableEffect(player, lifecycle) {
        val listener = object : Player.Listener { override fun onPlayerError(error: PlaybackException) { failed() }
            override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
                if (!playWhenReady && reason == Player.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_BECOMING_NOISY) stopped()
            }
        }
        val observer = LifecycleEventObserver { _, event -> if (event == Lifecycle.Event.ON_STOP) { player.pause(); stopped() } }
        player.addListener(listener); lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer); player.removeListener(listener); player.release() }
    }
    AndroidView(factory = { PlayerView(it).apply { useController = false; resizeMode = AspectRatioFrameLayout.RESIZE_MODE_ZOOM; this.player = player } },
        update = { it.player = player }, modifier = Modifier.fillMaxSize())
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FullSongSheet(clip: MusicClip, dismiss: () -> Unit, choose: (Track) -> Unit) {
    val repo: MusicRepository = koinInject()
    var query by remember(clip.id) { mutableStateOf(fullSongQuery(clip)) }
    var submitted by remember(clip.id) { mutableStateOf(query) }
    var tracks by remember(clip.id) { mutableStateOf<List<Track>>(emptyList()) }
    var loading by remember(clip.id) { mutableStateOf(true) }
    var failed by remember(clip.id) { mutableStateOf(false) }
    var retry by remember(clip.id) { mutableIntStateOf(0) }
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    fun submit() { if (query.isNotBlank()) { submitted = query.trim(); keyboard?.hide(); focus.clearFocus() } }
    LaunchedEffect(clip.id, submitted, retry) {
        loading = true; failed = false; tracks = emptyList()
        try { tracks = repo.search(submitted, SearchFilter.SONGS).items.mapNotNull { it.track }.distinctBy { it.id } }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { failed = true }
        finally { loading = false }
    }
    ModalBottomSheet(onDismissRequest = dismiss) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
            Text(stringResource(R.string.reels_choose_song), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.reels_attribution_hint), style = MaterialTheme.typography.bodySmall)
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(query, { query = it.take(200) }, Modifier.weight(1f), singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), keyboardActions = KeyboardActions(onSearch = { submit() }))
                IconButton({ submit() }, enabled = query.isNotBlank()) { Icon(Icons.Default.Search, stringResource(R.string.search_submit)) }
            }
        }
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 420.dp)) {
            if (loading) item { Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
            if (failed) item { TextButton({ retry++ }) { Text(stringResource(R.string.retry)) } }
            if (!loading && !failed && tracks.isEmpty()) item { Text(stringResource(R.string.no_results), Modifier.padding(16.dp)) }
            items(tracks, key = { it.id }) { track -> ListItem(
                modifier = Modifier.clickable { choose(track) },
                headlineContent = { Text(track.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },
                supportingContent = { Text(track.artist, maxLines = 1) },
                leadingContent = { Icon(Icons.Default.PlayArrow, null) }) }
        }
        Spacer(Modifier.height(24.dp))
    }
}
