package app.dkord

import app.dkord.ui.Tab
import app.dkord.ui.restoredTab
import org.junit.Assert.*
import org.junit.Test

class ListenNavigationTest {
    @Test fun old_serialized_shorts_enum_is_migration_only_and_opens_listen() {
        assertEquals(Tab.LISTEN, restoredTab(Tab.REELS))
    }
    @Test fun old_stable_name_is_mapped_to_audio_not_a_clip_player() {
        assertEquals(Tab.LISTEN, restoredTab("REELS"))
    }
    @Test fun current_tab_names_and_enum_values_roundtrip() {
        for (tab in listOf(Tab.HOME, Tab.SEARCH, Tab.LISTEN, Tab.LIBRARY, Tab.DOWNLOADS)) {
            assertEquals(tab, restoredTab(tab)); assertEquals(tab, restoredTab(tab.name))
        }
    }
    @Test fun damaged_or_future_tab_state_falls_back_without_a_crash() {
        assertEquals(Tab.HOME, restoredTab("unknown")); assertEquals(Tab.HOME, restoredTab(42))
    }
}
