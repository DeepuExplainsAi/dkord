@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package app.dkord.data.studio

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.audio.SonicAudioProcessor
import androidx.media3.transformer.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Actual decode -> millisecond clipping -> sequential PCM composition -> AAC in one MP4/M4A. */
internal class StudioAudioExporter(private val context: Context) {
    suspend fun render(project: StudioProject, sourceFile: (StudioSource) -> File, output: File, progress: (Int) -> Unit = {}): AudioProbe {
        var completed = false
        try {
            project.validate(requireClips = true)
            val sources = project.sources.associateBy { it.id }
            val edited = project.clips.map { clip ->
                val file = sourceFile(requireNotNull(sources[clip.sourceId]))
                val item = MediaItem.Builder().setUri(android.net.Uri.fromFile(file)).setClippingConfiguration(
                    MediaItem.ClippingConfiguration.Builder().setStartPositionMs(clip.startMs).setEndPositionMs(clip.endMs).build(),
                ).build()
                EditedMediaItem.Builder(item).setRemoveVideo(true)
                    .setEffects(Effects(listOf(SonicAudioProcessor().apply { setOutputSampleRateHz(44_100) }), emptyList())).build()
            }
            val composition = Composition.Builder(EditedMediaItemSequence.withAudioFrom(edited)).setTransmuxAudio(false).build()
            withContext(Dispatchers.Main.immediate) {
                check(!output.exists() || output.delete())
                val handler = Handler(Looper.getMainLooper())
                var transformer: Transformer? = null
                var poll: Runnable? = null
                try {
                    suspendCancellableCoroutine<Unit> { continuation ->
                        val listener = object : Transformer.Listener {
                            override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                                if (continuation.isActive) continuation.resume(Unit)
                            }
                            override fun onError(composition: Composition, exportResult: ExportResult, exportException: ExportException) {
                                if (continuation.isActive) continuation.resumeWithException(exportException)
                            }
                        }
                        val current = Transformer.Builder(context).setLooper(Looper.getMainLooper())
                            .setAudioMimeType(MimeTypes.AUDIO_AAC).addListener(listener).build()
                        transformer = current
                        poll = object : Runnable {
                            override fun run() {
                                if (!continuation.isActive) return
                                val holder = ProgressHolder()
                                if (current.getProgress(holder) == Transformer.PROGRESS_STATE_AVAILABLE) progress(holder.progress.coerceIn(0, 99))
                                handler.postDelayed(this, 400)
                            }
                        }
                        current.start(composition, output.absolutePath)
                        progress(-1)
                        handler.post(requireNotNull(poll))
                    }
                } finally {
                    poll?.let(handler::removeCallbacks)
                    // Runs on the same application looper, including cancellation; closes codecs before cleanup.
                    transformer?.cancel()
                }
            }
            val result = withContext(Dispatchers.IO) { probeAudio(output) }
            completed = true
            return result
        } finally {
            if (!completed) withContext(NonCancellable + Dispatchers.IO) { output.delete() }
        }
    }
}
