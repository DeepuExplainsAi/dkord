package app.dkord.data.download

import android.content.Context
import android.util.AtomicFile
import app.dkord.core.Track
import java.io.File
import java.util.UUID
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/** A tiny saved-state token, not an unbounded song list in Activity Bundle state. No audio, cookies or stream URLs. */
internal class DownloadSelectionStorage(context: Context) {
    private val dir = File(context.filesDir, "download-selections").apply { mkdirs() }
    private val json = Json { ignoreUnknownKeys = true }
    private fun file(token: String): AtomicFile {
        require(UUID.fromString(token).toString() == token)
        return AtomicFile(File(dir, "$token.json"))
    }
    fun save(tracks: List<Track>): String {
        require(tracks.isNotEmpty())
        val token = UUID.randomUUID().toString()
        val target = file(token)
        val stream = target.startWrite()
        try { stream.write(json.encodeToString(tracks).encodeToByteArray()); target.finishWrite(stream) }
        catch (e: Exception) { target.failWrite(stream); throw e }
        // Expired abandoned picker metadata, never library files or a freshly active request.
        dir.listFiles()?.filter { it.lastModified() < System.currentTimeMillis() - 7 * 24 * 60 * 60 * 1000L }
            ?.forEach(File::delete)
        return token
    }
    fun take(token: String): List<Track> {
        val target = file(token)
        return try { json.decodeFromString<List<Track>>(target.readFully().decodeToString()) }
        finally { target.delete() }
    }
}
