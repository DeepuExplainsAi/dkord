package app.dkord.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import app.dkord.R
import app.dkord.ui.common.SectionTitle

/** Copy is local-only. This component cannot launch a browser or upload a report. */
@Composable
internal fun PlaybackDiagnosticsItem(onCopy: () -> Unit) {
    ListItem(
        modifier = Modifier.testTag("copy-playback-diagnostics").clickable(onClick = onCopy),
        colors = ListItemDefaults.colors(containerColor = Color.Transparent),
        headlineContent = { Text(stringResource(R.string.report_broken)) },
        supportingContent = { Text(stringResource(R.string.report_broken_hint)) },
    )
}

/** Professional product copy only. Legal/source notices stay in the distributed LICENSE. */
@Composable
internal fun AboutSection() {
    SectionTitle(stringResource(R.string.about))
    ListItem(
        modifier = Modifier.testTag("about-dkord"),
        colors = ListItemDefaults.colors(containerColor = Color.Transparent),
        headlineContent = { Text("dKORD") },
        supportingContent = { Text(stringResource(R.string.about_text)) },
    )
}
