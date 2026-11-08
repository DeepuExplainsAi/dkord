package app.dkord

import app.dkord.core.Chip
import app.dkord.core.Page
import app.dkord.ui.common.Load
import app.dkord.ui.home.HomePageController
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class HomePageControllerTest {
    private val sad = Chip("Hindi sad", "sad-page", null)
    private val party = Chip("English party", "party-page", null)
    private fun title(controller: HomePageController) = (controller.page.value as Load.Ok).value.title

    @Test fun initial_and_selected_home_requests_capture_the_actual_chip() = runTest {
        val chips = mutableListOf<Chip?>()
        val c = HomePageController({ chips += it; Page(title = it?.title ?: "Home") }, backgroundScope)
        c.load(); runCurrent()
        assertEquals("Home", title(c))
        c.select(sad); runCurrent()
        assertEquals(sad, c.chip.value)
        assertEquals("Hindi sad", title(c))
        assertEquals(listOf(null, sad), chips)
    }

    @Test fun an_old_uncancellable_home_page_cannot_replace_a_different_selected_context() = runTest {
        val c = HomePageController({ chip ->
            withContext(NonCancellable) { delay(if (chip == sad) 100 else 5) }
            Page(title = chip!!.title)
        }, backgroundScope)
        c.select(sad); runCurrent()
        c.select(party); runCurrent(); advanceTimeBy(5); runCurrent()
        assertEquals(party, c.chip.value)
        assertEquals("English party", title(c))
        advanceTimeBy(95); runCurrent()
        assertEquals("English party", title(c))
    }

    @Test fun switching_back_to_the_same_chip_still_rejects_its_previous_request_epoch() = runTest {
        var calls = 0
        val c = HomePageController({ chip ->
            val number = ++calls
            withContext(NonCancellable) { delay(if (number == 1) 100 else 5) }
            Page(title = "${chip!!.title}-$number")
        }, backgroundScope)
        c.select(sad); runCurrent()
        c.select(party); runCurrent()
        c.select(sad); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals(sad, c.chip.value)
        assertEquals("Hindi sad-3", title(c))
    }

    @Test fun refreshing_keeps_the_same_completed_page_context_until_the_new_page_is_ready() = runTest {
        var calls = 0
        val c = HomePageController({ chip -> val number = ++calls; if (number > 1) delay(100); Page(title = "${chip!!.title}-$number") }, backgroundScope)
        c.select(sad); runCurrent()
        c.load(refresh = true); runCurrent()
        assertTrue(c.refreshing.value)
        assertEquals("Hindi sad-1", title(c))
        advanceTimeBy(100); runCurrent()
        assertFalse(c.refreshing.value)
        assertEquals("Hindi sad-2", title(c))
    }

    @Test fun a_cancelled_failure_and_finally_cannot_replace_or_clear_a_newer_loading_state() = runTest {
        var calls = 0
        val c = HomePageController({
            val number = ++calls
            withContext(NonCancellable) { delay(if (number == 1) 50 else 100) }
            if (number == 1) throw IOException("old failure")
            Page(title = "New page")
        }, backgroundScope)
        c.load(refresh = true); runCurrent()
        c.load(refresh = true); runCurrent(); advanceTimeBy(50); runCurrent()
        assertTrue(c.refreshing.value)
        assertTrue(c.page.value is Load.Loading)
        advanceTimeBy(50); runCurrent()
        assertFalse(c.refreshing.value)
        assertEquals("New page", title(c))
    }

    @Test fun tapping_the_selected_chip_returns_to_home_without_inheriting_its_old_mood() = runTest {
        val c = HomePageController({ Page(title = it?.title ?: "Home") }, backgroundScope)
        c.select(sad); runCurrent()
        c.select(sad); runCurrent()
        assertNull(c.chip.value)
        assertEquals("Home", title(c))
    }
}
