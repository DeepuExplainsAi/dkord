package app.dkord.ui.common

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.core.content.FileProvider
import app.dkord.R
import app.dkord.core.Track
import app.dkord.core.isLocalAudioId
import app.dkord.core.trackShareText
import app.dkord.data.download.DownloadManager
import kotlinx.coroutines.*
import org.koin.core.context.GlobalContext
import java.io.File

private val shareScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

fun shareTrack(context: Context, track: Track) {
    if (!isLocalAudioId(track.id)) { sharePlainText(context, trackShareText(track)); return }
    val app = context.applicationContext
    shareScope.launch {
        try {
            val raw = withContext(Dispatchers.IO) { GlobalContext.get().get<DownloadManager>().localUri(track.id) }
                ?: throw java.io.FileNotFoundException()
            val stored = Uri.parse(raw)
            val uri = if (stored.scheme == "file") FileProvider.getUriForFile(app, app.packageName + ".files", File(requireNotNull(stored.path))) else stored
            require(uri.scheme == "content")
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "audio/mp4"; putExtra(Intent.EXTRA_STREAM, uri); putExtra(Intent.EXTRA_TITLE, track.title)
                putExtra(Intent.EXTRA_TEXT, trackShareText(track)); clipData = ClipData.newUri(app.contentResolver, track.title, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            app.startActivity(Intent.createChooser(send, app.getString(R.string.share)).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
            })
        } catch (e: CancellationException) { throw e }
        catch (_: Exception) { Toast.makeText(app, R.string.studio_file_unavailable, Toast.LENGTH_SHORT).show() }
    }
}

fun sharePlainText(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }
    try {
        context.startActivity(Intent.createChooser(send, context.getString(R.string.share)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        })
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, R.string.share_failed, Toast.LENGTH_SHORT).show()
    } catch (_: SecurityException) {
        Toast.makeText(context, R.string.share_failed, Toast.LENGTH_SHORT).show()
    }
}
