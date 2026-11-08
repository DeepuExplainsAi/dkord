@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package app.dkord

import android.content.Context
import android.content.ContextWrapper
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.os.SystemClock
import androidx.media3.datasource.DataSpec
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.dkord.core.LOCAL_STUDIO_PREFIX
import app.dkord.data.stream.*
import app.dkord.data.studio.*
import app.dkord.player.StreamUriResolver
import app.dkord.player.trackUri
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin

@RunWith(AndroidJUnit4::class)
class StudioAudioExportTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun source(file: File, duration: Long) = StudioSource(studioId(), file.name, "", duration, "audio/wav").let { it.copy(fileName = "${it.id}.audio") }

    @Test fun different_sources_ranges_and_sample_rates_become_one_decodable_aac_file_in_selected_order() = runBlocking {
        val dir = File(context.cacheDir, "studio-render-${studioId()}").apply { mkdirs() }
        try {
            val a = File(dir, "a.wav"); val b = File(dir, "b.wav")
            writeWave(a, 44_100, 1, 2) { second -> if (second < 1) 220.0 else 880.0 }
            writeWave(b, 48_000, 2, 2) { 440.0 }
            val one = source(a, 2000); val two = source(b, 2000)
            val files = mapOf(one.id to a, two.id to b)
            val p = StudioProject(studioId(), "Test mix", listOf(one, two))
                .withClip(one.id, 1100, 1500).withClip(two.id, 200, 1000).withClip(one.id, 100, 400)
            val output = File(dir, "merged.m4a")
            val audio = withTimeout(60_000) { StudioAudioExporter(context).render(p, { requireNotNull(files[it.id]) }, output) }
            assertTrue(output.length() > 256)
            assertEquals("audio/mp4a-latm", audio.mime)
            assertTrue("Actual duration ${audio.durationMs}", abs(audio.durationMs - p.durationMs) <= 100)
            val decoded = decode(output)
            // Distinguishes actual ordered/range-clipped audio from silence, copied whole songs or a playlist.
            assertTone(decoded, 0.12, 0.28, 880.0)
            assertTone(decoded, 0.60, 0.90, 440.0)
            assertTone(decoded, 1.30, 1.40, 220.0)
        } finally { dir.deleteRecursively() }
    }

    @Test fun cancellation_after_transformer_starts_closes_codecs_and_deletes_partial_output() = runBlocking {
        val dir = File(context.cacheDir, "studio-cancel-${studioId()}").apply { mkdirs() }
        try {
            val input = File(dir, "long.wav"); writeWave(input, 44_100, 1, 60) { 440.0 }
            val s = source(input, 60_000)
            val p = StudioProject(studioId(), "Cancel", listOf(s)).withClip(s.id, 0, 60_000)
            val output = File(dir, "partial.m4a")
            val started = CompletableDeferred<Unit>()
            val job = launch { StudioAudioExporter(context).render(p, { input }, output) { started.complete(Unit) } }
            withTimeout(30_000) { started.await() }
            job.cancelAndJoin()
            assertTrue(job.isCancelled)
            assertFalse(output.exists())
        } finally { dir.deleteRecursively() }
    }

    @Test fun unavailable_generated_audio_never_falls_back_to_any_remote_stream_resolver() {
        var calls = 0
        val fake = object : StreamResolver {
            override val name = "must-not-run"
            override suspend fun resolve(videoId: String, quality: AudioQuality, preferM4a: Boolean): ResolvedStream {
                calls++; error("Generated audio must not leave the device")
            }
        }
        val resolver = StreamUriResolver(fake, { AudioQuality.HIGH })
        val spec = DataSpec.Builder().setUri(trackUri(LOCAL_STUDIO_PREFIX + studioId())).build()
        try { resolver.resolveDataSpec(spec); fail("Missing local file must fail") }
        catch (_: StreamError.Unavailable) { }
        assertEquals(0, calls)
    }

    @Test fun imported_sources_and_precise_projects_survive_reload_and_corrupt_metadata_is_not_overwritten() = runBlocking {
        val dir = File(context.cacheDir, "studio-store-${studioId()}").apply { mkdirs() }
        val isolated = object : ContextWrapper(context) { override fun getFilesDir(): File = dir }
        try {
            val input = File(dir, "original.wav"); writeWave(input, 44_100, 1, 2) { 330.0 }
            val first = StudioRepository(isolated)
            withTimeout(10_000) { first.state.first { !it.loading } }
            val id = first.create("Saved project")
            first.importAudio(id, android.net.Uri.fromFile(input), "My source")
            val p = first.state.value.projects.single()
            assertEquals(1, p.sources.size)
            first.change(id) { it.withClip(p.sources.single().id, 123, 1234, p.clips.single().id) }
            input.delete()
            val second = StudioRepository(isolated)
            val restored = withTimeout(10_000) { second.state.first { !it.loading } }
            assertFalse(restored.failed)
            assertEquals(first.state.value.projects, restored.projects)
            assertTrue(second.sourceFile(restored.projects.single().sources.single()).isFile)
            val catalog = File(second.root, "projects.json")
            catalog.writeText("not valid project JSON")
            val third = StudioRepository(isolated)
            assertTrue(withTimeout(10_000) { third.state.first { !it.loading } }.failed)
            try { third.create("Must not erase"); fail("Corrupt storage cannot be replaced") } catch (_: IllegalStateException) { }
            val imported = second.sourceFile(restored.projects.single().sources.single())
            third.finishRequest(studioId())
            assertTrue("Failed catalog recovery must never purge private audio", imported.exists())
            try { second.copyAudio(android.net.Uri.fromFile(imported), android.net.Uri.fromFile(imported)); fail("Cannot truncate a copy source") }
            catch (_: IllegalArgumentException) { }
            assertTrue(imported.length() > 44)
            assertEquals("not valid project JSON", catalog.readText())
        } finally { dir.deleteRecursively() }
    }

    private data class Decoded(val pcm: ByteArray, val rate: Int, val channels: Int)
    private fun decode(file: File): Decoded {
        val extractor = MediaExtractor()
        var decoder: MediaCodec? = null
        try {
            extractor.setDataSource(file.absolutePath)
            assertEquals(1, extractor.trackCount)
            val format = extractor.getTrackFormat(0)
            assertEquals("audio/mp4a-latm", format.getString(MediaFormat.KEY_MIME))
            extractor.selectTrack(0)
            format.setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_16BIT)
            val codec = MediaCodec.createDecoderByType(requireNotNull(format.getString(MediaFormat.KEY_MIME)))
            decoder = codec; codec.configure(format, null, null, 0); codec.start()
            val result = ByteArrayOutputStream(); val info = MediaCodec.BufferInfo()
            var inputEnded = false; var outputEnded = false
            var rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE); var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            val deadline = SystemClock.elapsedRealtime() + 15_000
            while (!outputEnded && SystemClock.elapsedRealtime() < deadline) {
                if (!inputEnded) {
                    val index = codec.dequeueInputBuffer(10_000)
                    if (index >= 0) {
                        val buffer = requireNotNull(codec.getInputBuffer(index)); buffer.clear()
                        val bytes = extractor.readSampleData(buffer, 0)
                        if (bytes < 0) { codec.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM); inputEnded = true }
                        else { codec.queueInputBuffer(index, 0, bytes, extractor.sampleTime, 0); extractor.advance() }
                    }
                }
                val index = codec.dequeueOutputBuffer(info, 10_000)
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    rate = codec.outputFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE); channels = codec.outputFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                } else if (index >= 0) {
                    if (info.size > 0) {
                        val buffer = requireNotNull(codec.getOutputBuffer(index)); buffer.position(info.offset); buffer.limit(info.offset + info.size)
                        result.write(ByteArray(info.size).also(buffer::get))
                    }
                    outputEnded = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    codec.releaseOutputBuffer(index, false)
                }
            }
            assertTrue("AAC decoder must reach end of stream", outputEnded)
            return Decoded(result.toByteArray(), rate, channels)
        } finally { runCatching { decoder?.stop() }; decoder?.release(); extractor.release() }
    }
    private fun assertTone(decoded: Decoded, from: Double, to: Double, expected: Double) {
        val samples = ByteBuffer.wrap(decoded.pcm).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        val first = (from * decoded.rate).toInt(); val last = (to * decoded.rate).toInt()
        assertTrue(last * decoded.channels < samples.limit())
        var crossings = 0
        for (frame in first + 1 until last) if (samples.get((frame - 1) * decoded.channels) <= 0 && samples.get(frame * decoded.channels) > 0) crossings++
        val actual = crossings * decoded.rate.toDouble() / (last - first)
        assertTrue("Expected $expected Hz, decoded $actual Hz", abs(actual - expected) < 25)
    }
    private fun writeWave(file: File, rate: Int, channels: Int, seconds: Int, frequency: (Double) -> Double) {
        val frames = rate * seconds; val bytes = frames * channels * 2
        file.outputStream().buffered().use { out ->
            fun int(n: Int) { repeat(4) { out.write(n ushr (8 * it) and 255) } }
            fun short(n: Int) { out.write(n and 255); out.write(n ushr 8 and 255) }
            out.write("RIFF".toByteArray()); int(bytes + 36); out.write("WAVEfmt ".toByteArray()); int(16)
            short(1); short(channels); int(rate); int(rate * channels * 2); short(channels * 2); short(16)
            out.write("data".toByteArray()); int(bytes)
            repeat(frames) { frame ->
                val t = frame.toDouble() / rate
                val value = (sin(2 * PI * frequency(t) * t) * 12_000).toInt()
                repeat(channels) { short(value) }
            }
        }
    }
}
