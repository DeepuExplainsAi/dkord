package app.dkord.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import app.dkord.R
import app.dkord.data.room.*

/** Inline/scrollable with the existing screen: no new dialog/IME owner or global theme changes. */
@Composable
internal fun RoomControlsPanel(
    access: RoomAccessState,
    creator: Boolean,
    onMode: (RoomControlMode) -> Unit,
    onMember: (String, Boolean) -> Unit,
) {
    Card(Modifier.fillMaxWidth().testTag("room-controls")) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.room_controls_title), style = MaterialTheme.typography.titleMedium)
            if (access.selfId.isNotEmpty()) SelectionContainer {
                Text(stringResource(R.string.room_controls_your_id, access.selfId.take(8)), style = MaterialTheme.typography.bodySmall)
            }
            if (creator && access.available) {
                Text(stringResource(R.string.room_controls_hint), style = MaterialTheme.typography.bodyMedium)
                listOf(RoomControlMode.HOST_ONLY to R.string.room_controls_host_only,
                    RoomControlMode.SELECTED to R.string.room_controls_selected,
                    RoomControlMode.EVERYONE to R.string.room_controls_everyone).forEach { (mode, title) ->
                    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("room-mode-${mode.name}")
                        .selectable(access.mode == mode, role = Role.RadioButton, onClick = { onMode(mode) }).padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(access.mode == mode, null)
                        Text(stringResource(title), Modifier.padding(start = 8.dp).weight(1f))
                    }
                }
                Text(stringResource(R.string.room_controls_members), style = MaterialTheme.typography.labelLarge)
                if (access.members.isEmpty()) Text(stringResource(R.string.room_controls_empty), style = MaterialTheme.typography.bodySmall)
                access.members.forEach { member ->
                    val checked = access.mode == RoomControlMode.EVERYONE || (access.mode == RoomControlMode.SELECTED && member.id in access.selected)
                    val enabled = access.mode != RoomControlMode.EVERYONE
                    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("room-member-${member.id}")
                        .toggleable(checked, enabled = enabled, role = Role.Checkbox, onValueChange = { onMember(member.id, it) }).padding(vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked, null, enabled = enabled)
                        Column(Modifier.padding(start = 8.dp).weight(1f)) {
                            Text(member.name)
                            Text(member.id.take(8), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            } else if (!access.ownerKnown) Text(stringResource(R.string.room_controls_pending))
            else if (!access.canControl) Text(stringResource(R.string.room_controls_listen_only))
            Text(stringResource(R.string.room_controls_consent), style = MaterialTheme.typography.bodySmall)
            access.error?.let {
                val message = when (it) {
                    RoomSharingError.NETWORK -> R.string.room_controls_network
                    RoomSharingError.RATE_LIMIT -> R.string.room_controls_rate_limit
                    RoomSharingError.LOCAL_AUDIO -> R.string.room_controls_local_audio
                    RoomSharingError.OWNER_OFFLINE -> R.string.room_controls_owner_offline
                }
                Text(stringResource(message), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Text(stringResource(R.string.room_controls_privacy), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
