package app.dkord.ui.common

import android.net.Uri
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.dkord.R
import app.dkord.core.Track
import app.dkord.data.download.DownloadSelectionStorage
import app.dkord.data.db.DownloadLocation
import app.dkord.data.download.DownloadStorage
import app.dkord.data.settings.SettingsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.koin.compose.koinInject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun DownloadDestinationChoices(onSelect: (DownloadLocation) -> Unit, onDismiss: () -> Unit) {
    val ownerContext = LocalContext.current
    val ownerDensity = LocalDensity.current
    BasicAlertDialog(onDismissRequest = onDismiss) {
        // This is a separate Window: inherit actual app locale and accessibility scale explicitly.
        CompositionLocalProvider(LocalContext provides ownerContext, LocalDensity provides ownerDensity) {
            Surface(Modifier.fillMaxWidth().heightIn(max = 600.dp), shape = MaterialTheme.shapes.extraLarge) {
                Column(Modifier.padding(24.dp)) {
                    Text(stringResource(R.string.download_destination), style = MaterialTheme.typography.headlineSmall)
                    Spacer(Modifier.height(16.dp))
                    Column(Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({ onSelect(DownloadLocation.APP) }, Modifier.fillMaxWidth().testTag("download-in-dkord")) {
                            Column(Modifier.fillMaxWidth()) {
                                Text(stringResource(R.string.download_in_dkord))
                                Text(stringResource(R.string.download_in_dkord_hint), style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        OutlinedButton({ onSelect(DownloadLocation.DEVICE) }, Modifier.fillMaxWidth().testTag("download-to-device")) {
                            Column(Modifier.fillMaxWidth()) {
                                Text(stringResource(R.string.download_to_device))
                                Text(stringResource(R.string.download_to_device_hint), style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        Text(stringResource(R.string.download_existing_copies), style = MaterialTheme.typography.bodySmall)
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onDismiss) { Text(stringResource(R.string.cancel)) }
                    }
                }
            }
        }
    }
}

/** Root host is not disposed when a row menu/player closes; picker requests retain their own batch. */
@Composable
internal fun DownloadDestinationHost(actions: Actions, message: (String) -> Unit) {
    val request by actions.downloadRequest.collectAsState()
    val settings: SettingsRepository = koinInject()
    val storage: DownloadStorage = koinInject()
    val selections: DownloadSelectionStorage = koinInject()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var pickerToken by rememberSaveable { mutableStateOf<String?>(null) }
    fun enqueue(tracks: List<Track>, location: DownloadLocation, tree: String? = null) {
        actions.scope.launch {
            try {
                actions.downloads.enqueue(tracks, location, tree)
                withContext(Dispatchers.Main) { message(context.getString(R.string.download_started)) }
            } catch (_: Exception) {
                withContext(Dispatchers.Main) { message(context.getString(R.string.download_destination_failed)) }
            }
        }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { tree: Uri? ->
        val token = pickerToken
        pickerToken = null
        if (token != null) scope.launch {
            try {
                val tracks = withContext(Dispatchers.IO) { selections.take(token) }
                if (tree != null) {
                    storage.keepAccess(tree)
                    settings.saveDownloadTree(tree.toString())
                    enqueue(tracks, DownloadLocation.DEVICE, tree.toString())
                }
            } catch (e: kotlinx.coroutines.CancellationException) { throw e }
            catch (_: Exception) { message(context.getString(R.string.download_destination_failed)) }
        }
    }

    request?.let { pending -> DownloadDestinationChoices(onSelect = { location ->
        actions.dismissDownload(pending.id)
        if (location == DownloadLocation.DEVICE && Build.VERSION.SDK_INT < 29 && settings.settings.value.downloadTree == null) {
            scope.launch {
                try {
                    pickerToken = withContext(Dispatchers.IO) { selections.save(pending.tracks) }
                    picker.launch(null)
                } catch (e: kotlinx.coroutines.CancellationException) { throw e }
                catch (_: Exception) { message(context.getString(R.string.download_destination_failed)) }
            }
        } else enqueue(pending.tracks, location, settings.settings.value.downloadTree)
    }, onDismiss = { actions.dismissDownload(pending.id) }) }
}
