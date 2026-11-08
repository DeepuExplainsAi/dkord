"""Fast source/resource/release contracts; Android behavior is tested by the Kotlin suite in Actions.

These checks intentionally need only Python's standard library. They do NOT execute Android,
render Compose, or prove a two-device room session works.
"""
from collections import Counter
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "app/src/main"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def strings(folder):
    return {item.attrib["name"]: "".join(item.itertext())
            for item in ET.parse(MAIN / "res" / folder / "strings.xml").getroot()}


class AppContractsTest(unittest.TestCase):
    def test_all_xml_resources_and_manifest_are_well_formed(self):
        for path in [MAIN / "AndroidManifest.xml", *(MAIN / "res").rglob("*.xml")]:
            with self.subTest(file=str(path.relative_to(ROOT))):
                ET.parse(path)

    def test_resource_names_are_unique_in_each_language(self):
        for folder in ("values", "values-hi"):
            counts = Counter(item.attrib["name"] for item in ET.parse(MAIN / "res" / folder / "strings.xml").getroot())
            self.assertFalse({key: count for key, count in counts.items() if count != 1}, folder)

    def test_hindi_has_every_english_key_with_matching_format_arguments(self):
        english, hindi = strings("values"), strings("values-hi")
        self.assertEqual(english.keys(), hindi.keys())
        for key, value in english.items():
            with self.subTest(key=key):
                self.assertEqual(sorted(re.findall(r"%(?:\d+\$)?[sd]", value)),
                                 sorted(re.findall(r"%(?:\d+\$)?[sd]", hindi[key])))

    def test_default_interface_resources_are_english(self):
        for key, value in strings("values").items():
            self.assertIsNone(re.search(r"[\u0900-\u097f]", value), key)

    def test_all_app_string_references_resolve(self):
        english = strings("values")
        for path in (MAIN / "java").rglob("*.kt"):
            for key in re.findall(r"(?<!android\.)\bR\.string\.(\w+)", path.read_text()):
                self.assertIn(key, english, f"{path.relative_to(ROOT)}: {key}")

    def test_language_picker_matches_only_real_translations(self):
        config = ET.parse(MAIN / "res/xml/locales_config.xml").getroot()
        configured = [locale.attrib[ANDROID + "name"] for locale in config]
        policy = read("app/src/main/java/app/dkord/data/settings/AppLanguage.kt")
        supported = re.findall(r'\b[A-Z_]+\("([a-z]+)"\)', policy)
        self.assertEqual(["en", "hi"], configured)
        self.assertEqual(configured, supported)
        self.assertEqual({"values-hi"}, {p.name for p in (MAIN / "res").glob("values-*") if (p / "strings.xml").exists()})

    def test_english_default_is_applied_globally_with_matching_activity_theme(self):
        application = read("app/src/main/java/app/dkord/DkordApp.kt")
        activity = read("app/src/main/java/app/dkord/MainActivity.kt")
        settings = read("app/src/main/java/app/dkord/ui/screens/Settings.kt")
        themes = read("app/src/main/res/values/themes.xml")
        self.assertIn("AppLanguages.initialize(this)", application)
        self.assertIn("AppLanguages.deviceLocale(this)", application)
        self.assertIn(".systemLocales[0]", read("app/src/main/java/app/dkord/data/settings/AppLanguages.kt"))
        self.assertIn("class MainActivity : AppCompatActivity()", activity)
        self.assertIn("AppLanguages.initialize(newBase)", activity)
        self.assertIn("Theme.AppCompat.DayNight.NoActionBar", themes)
        self.assertIn("AppLanguages.select(ctx, it)", settings)

    def test_room_has_ordered_practical_steps_not_the_removed_technical_paragraph(self):
        ui = read("app/src/main/java/app/dkord/ui/screens/ListenTogether.kt")
        steps = ["room_step_create", "room_step_share", "room_step_join", "room_step_sync"]
        self.assertEqual(sorted(steps, key=ui.index), steps)
        for key in steps:
            self.assertIn(key, strings("values"))
            self.assertIn(key, strings("values-hi"))
        for removed in ("room_privacy_note", "room_anyone_can_join", "room_local_audio", "room_stays_connected"):
            self.assertNotIn(removed, ui)
            self.assertNotIn(removed, strings("values"))
        self.assertIn("ClipData.newPlainText", ui)

    def test_home_update_is_inline_and_only_on_home(self):
        update = read("app/src/main/java/app/dkord/ui/common/AppUpdate.kt")
        app = read("app/src/main/java/app/dkord/ui/App.kt")
        self.assertNotIn("AlertDialog", update)
        self.assertNotIn("HomeUpdatePrompt", app)
        self.assertIn("HomeUpdateNotice(visible = tab == Tab.HOME", app)
        self.assertEqual(1, app.count("ObserveAppUpdates()"))
        self.assertIn("updater::later", update)

    def test_updater_uses_latest_stable_endpoint_not_version_increment_hops(self):
        adapter = read("app/src/main/java/app/dkord/data/update/AppUpdater.kt")
        endpoints = re.findall(r'const val LATEST = "([^"]+)"', adapter)
        self.assertEqual(["https://api.github.com/repos/DeepuExplainsAi/dkord/releases/latest"], endpoints)
        self.assertIn("currentSigners.isEmpty()", adapter)
        self.assertIn("signatures(candidate) != currentSigners", adapter)
        self.assertIn("candidate.packageName != app.packageName", adapter)

    def test_choliwood_name_and_collapsed_new_releases_are_preserved(self):
        for folder in ("values", "values-hi"):
            values = strings(folder)
            for key, value in values.items():
                if "choliwood" in key:
                    self.assertIn("Choliwood", value, key)
                    self.assertNotIn("Bhojpuri", value, key)
        releases = read("app/src/main/java/app/dkord/ui/screens/NewReleases.kt")
        self.assertRegex(releases, r"expanded\s+by\s+rememberSaveable\s*\{\s*mutableStateOf\(false\)")

    def test_search_history_uses_private_local_singleton_storage(self):
        store = read("app/src/main/java/app/dkord/data/search/PreferencesSearchHistoryStorage.kt")
        module = read("app/src/main/java/app/dkord/di/AppModule.kt")
        self.assertIn('preferencesDataStore(name = "search-history")', store)
        self.assertIn("context.applicationContext.searchHistoryStore", store)
        self.assertIn("store.edit", store)
        self.assertIn("single { SearchHistoryRepository(PreferencesSearchHistoryStorage(androidContext())) }", module)
        manifest = ET.parse(MAIN / "AndroidManifest.xml").getroot()
        self.assertEqual("false", manifest.find("application").attrib[ANDROID + "allowBackup"])
        for filename in ("SearchHistory.kt", "SearchHistoryRepository.kt", "PreferencesSearchHistoryStorage.kt"):
            source = read("app/src/main/java/app/dkord/data/search/" + filename)
            self.assertNotRegex(source, r"https?://|\b(?:DebugLog|Log|OkHttpClient)\.")

    def test_recent_search_actions_are_wired_and_clear_all_requires_confirmation(self):
        ui = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        app = read("app/src/main/java/app/dkord/ui/App.kt")
        self.assertIn("query.isBlank() -> SavedSearches", ui)
        for action in ("saved::togglePinned", "saved::remove", "vm.repeat(entry)", "vm.edit(entry)"):
            self.assertIn(action, ui)
        self.assertIn("if (confirmClear) AlertDialog(", ui)
        self.assertIn("search_clear_message", ui)
        self.assertEqual(1, ui.count("saved.clearAll()"))
        self.assertLess(ui.index("confirmButton ="), ui.index("saved.clearAll()"))
        self.assertIn("onMessage = say", app)

    def test_only_submissions_record_history_and_search_selection_does_not_queue_alternative_matches(self):
        controller = read("app/src/main/java/app/dkord/ui/search/SearchController.kt")
        source = read("app/src/main/java/app/dkord/data/search/MusicSearchSource.kt")
        ui = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        self.assertEqual(1, controller.count("history.record("))
        submit = controller.index("    fun search(")
        record = controller.index("history.record(")
        self.assertLess(submit, record)
        self.assertLess(record, controller.index("searchJob = scope.launch", submit))
        for call in ("music.suggestions(query)", "music.search(query, filter)", "music.searchMore("):
            self.assertIn(call, source)
        self.assertIn("searchPlaybackQueue(item)", ui)
        self.assertIn("onPlay(selected, 0)", ui)
        self.assertNotIn("onPlay(songs, songs.indexOfFirst", ui)
        shelves = read("app/src/main/java/app/dkord/ui/common/Components.kt")
        self.assertIn("onPlay(songs, songs.indexOfFirst", shelves)
        self.assertIn("else onItem(item)", ui)
        self.assertIn("vm.loadMore(retry = true)", ui)
        self.assertIn("results == null -> SearchSuggestions", ui)

    def test_manual_search_is_music_first_with_explicit_broad_scopes_and_no_hardcoded_query(self):
        backend = read("app/src/main/java/app/dkord/data/yt/MusicRepository.kt")
        controller = read("app/src/main/java/app/dkord/ui/search/SearchController.kt")
        ui = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        for route in ("ALL(F.ALL)", "VIDEOS(F.VIDEOS)", "MUSIC_VIDEOS(F.MUSIC_VIDEOS)", "SONGS(F.MUSIC_SONGS)"):
            self.assertIn(route, backend)
        self.assertIn("mutableFilter = MutableStateFlow(SearchFilter.SONGS)", controller)
        self.assertIn('fromQuery(query, listOf(filter.id), "")', backend)
        self.assertIn('fromQuery(cursor.query, listOf(cursor.filter.id), "")', backend)
        self.assertIn("SearchFilter.ALL -> R.string.search_all", ui)
        self.assertIn("vm.setFilter(SearchFilter.ALL)", ui)
        for source in (backend, controller, ui):
            for query in ("mashup sad love 1 hour", "Teri meri kahani", "instumental", "Instagram version"):
                self.assertNotIn(query, source)

    def test_the_broad_upload_route_is_available_outside_empty_or_failed_results(self):
        ui = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        placement = ui.index("        SearchScopeHint(filter, onSearchAll =")
        content = ui.index("        Box(Modifier.fillMaxWidth().weight(1f))", placement)
        self.assertLess(placement, content)
        self.assertEqual(1, ui.count("vm.setFilter(SearchFilter.ALL)"))
        hint = ui[ui.index("private fun SearchScopeHint("):ui.index("private fun SearchSuggestions(")]
        self.assertIn("if (filter != SearchFilter.ALL) TextButton(onSearchAll)", hint)
        self.assertIn("search_scope_uploads", hint)
        self.assertIn("search_scope_music_catalogue", hint)

    def test_creator_versions_keep_identity_and_search_rows_show_more_than_the_song_name(self):
        controller = read("app/src/main/java/app/dkord/ui/search/SearchController.kt")
        row = read("app/src/main/java/app/dkord/ui/common/Components.kt")
        row = row[row.index("fun BrowseRow("):row.index("fun TextInputDialog(")]
        self.assertEqual(2, controller.count("distinctBy { it.kind to it.id }"))
        self.assertIn("searchResultSupportingText(item)", row)
        self.assertIn("Text(item.title, maxLines = 2", row)
        presentation = read("app/src/main/java/app/dkord/ui/search/SearchResultPresentation.kt")
        self.assertIn("item.subtitle", presentation)
        self.assertIn("item.track?.durationSec", presentation)
        self.assertNotIn("item.title", presentation)

    def test_suggestion_recovery_and_provider_corrections_are_visible_not_fake_recommendations(self):
        backend = read("app/src/main/java/app/dkord/data/yt/MusicRepository.kt")
        ui = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        controller = read("app/src/main/java/app/dkord/ui/search/SearchController.kt")
        self.assertIn("ServiceList.YouTube.suggestionExtractor.suggestionList(query)", backend)
        self.assertIn("info.searchSuggestion.orEmpty(), info.isCorrectedSearch", backend)
        for value in ("search_youtube_suggestions", "search_suggestions_failed", "search_suggestions_loading", "search_did_you_mean", "search_showing_results_for", "vm::retrySuggestions"):
            self.assertIn(value, ui)
        self.assertIn("fun retrySuggestions()", controller)
        self.assertIn("value.copy(query = suggested)", controller)
        self.assertIn("results.value != null || suggestionsLoading.value", controller)

    def test_radio_duration_rules_are_not_applied_to_user_search_results(self):
        backend = read("app/src/main/java/app/dkord/data/yt/MusicRepository.kt")
        mapper = read("app/src/main/java/app/dkord/data/yt/SearchItems.kt")
        radio = backend[backend.index("suspend fun related("):backend.index("// ---- Browse:")]
        policy = read("app/src/main/java/app/dkord/data/yt/RadioTracks.kt")
        self.assertIn("track.durationSec in 60..720", policy)
        self.assertIn("musicRadioRecommendations(track, queue", radio)
        self.assertIn("SearchFilter.SONGS", radio)
        self.assertIn("is StreamInfoItem", mapper)
        self.assertIn("i.duration", mapper)
        mapping = mapper[:mapper.index("internal fun searchVideoId(")]
        self.assertNotRegex(mapping, r"\b(?:filter|filterNot)\s*\{|duration\s+(?:in|[<>])")
        self.assertIn("YoutubeStreamLinkHandlerFactory.getInstance().getId(", mapper)

    def test_search_submit_is_outside_the_editable_text_and_placeholder_cannot_wrap(self):
        ui = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        field = ui[ui.index("            OutlinedTextField("):ui.index("        LazyRow(")]
        self.assertNotIn("leadingIcon", field)
        self.assertIn("maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis", field)
        self.assertIn("FilledIconButton({ submitted { vm.search() } }, Modifier.size(48.dp)", field)
        self.assertLess(field.index("keyboardActions ="), field.index("FilledIconButton("))
        self.assertIn("Modifier.weight(1f).focusRequester", field)

    def test_keyboard_has_one_shell_owner_and_nested_scaffolds_consume_padding(self):
        search = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        shell = read("app/src/main/java/app/dkord/ui/common/KeyboardAwareScaffold.kt")
        app = read("app/src/main/java/app/dkord/ui/App.kt")
        self.assertNotIn("imePadding", search)
        self.assertEqual(1, shell.count(".imePadding()"))
        self.assertIn("if (!keyboardVisible) bottomBar()", shell)
        self.assertEqual(2, app.count(".consumeWindowInsets(pad)"))
        self.assertIn("KeyboardAwareScaffold(", app)
        manifest = ET.parse(MAIN / "AndroidManifest.xml").getroot()
        activity = manifest.find("application/activity")
        self.assertEqual("adjustResize", activity.attrib[ANDROID + "windowSoftInputMode"])

    def test_player_secondary_controls_wrap_as_buttons_not_letter_by_letter(self):
        ui = read("app/src/main/java/app/dkord/ui/player/PlayerUi.kt")
        footer = ui[ui.index("            FlowRow("):ui.index('    if (sheet == "speed")')]
        self.assertEqual(5, footer.count("maxLines = 1, softWrap = false"))
        for action in ("sleep_timer", "autoplay", "add_to_playlist", "play_video"):
            self.assertIn(action, footer)

    def test_autoplay_uses_current_queue_intent_and_invalidates_old_selection_requests(self):
        player = read("app/src/main/java/app/dkord/player/PlayerController.kt")
        coordinator = read("app/src/main/java/app/dkord/player/AutoplayCoordinator.kt")
        self.assertIn("AutoplayCoordinator(scope", player)
        self.assertIn("playWhenReady = c.playWhenReady", player)
        self.assertIn("if (resumeEnded && c.playWhenReady && settings.settings.value.autoplay)", player)
        self.assertIn("settings.settings.map { it.autoplay }.distinctUntilChanged()", player)
        for method in ("fun play(tracks:", "fun playNext(", "fun addToQueue(", "fun pause()", "fun stop()"):
            start = player.index(method)
            self.assertIn("autoplay.invalidate()", player[start:player.index("\n    }", start) + 6])
        self.assertIn("now.queue.map { it.id } != request.ids", coordinator)
        self.assertIn("active !== request", coordinator)
        self.assertIn("currentCoroutineContext().ensureActive()", coordinator)
        for source in (player, coordinator):
            self.assertNotIn("SEM CONTROLE", source)

    def test_search_and_home_route_single_song_radio_with_context_and_keep_explicit_play_all(self):
        app = read("app/src/main/java/app/dkord/ui/App.kt")
        home = read("app/src/main/java/app/dkord/ui/screens/Home.kt")
        search = read("app/src/main/java/app/dkord/ui/screens/Search.kt")
        shelves = read("app/src/main/java/app/dkord/ui/common/Components.kt")
        self.assertIn("player.playRelated(track, hint)", app)
        self.assertIn("HomeScreen(onItem, onPlay, m, onRelated = onRelated)", app)
        self.assertIn("onMessage = say, onRelated = onRelated", app)
        self.assertIn("radioHint = query", home)
        self.assertEqual(home.count("ShelfRow("), home.count("onRelated = onRelated"))
        self.assertIn("NewReleasesSection(onItem, onPlay)", home)
        home_requests = read("app/src/main/java/app/dkord/ui/home/HomePageController.kt")
        self.assertIn("HomePageController(repo::home, viewModelScope)", home)
        self.assertIn("val selected = chip.value", home_requests)
        self.assertIn("if (id == request)", home_requests)
        self.assertIn("currentCoroutineContext().ensureActive()", home_requests)
        self.assertIn("SearchPlaybackRow(item, playbackHint", search)
        self.assertIn("onRelated(selected.single(), contextHint)", search)
        self.assertIn("onRelated(t, shelf.radioHint)", shelves)
        self.assertIn("TextButton({ onPlay(songs, 0) }", shelves)
        self.assertIn("onPlay(songs, songs.indexOfFirst", shelves)

    def test_contextual_radio_keeps_anonymous_bounded_metadata_and_never_serializes_private_intent(self):
        client = read("app/src/main/java/app/dkord/data/yt/InnerTubeClient.kt")
        facts = read("app/src/main/java/app/dkord/data/yt/RadioFactsSource.kt")
        radio = read("app/src/main/java/app/dkord/data/yt/RadioTracks.kt")
        for text in ("CookieJar.NO_COOKIES", "Authenticator.NONE", "callTimeout(8", "call.cancel()", "Radio metadata too large"):
            self.assertIn(text, client)
        self.assertIn("AudioTrackType.ORIGINAL", facts)
        self.assertIn("Semaphore(3)", facts)
        self.assertIn("cache.size > 192", facts)
        self.assertIn("24 - profiled", radio)
        self.assertIn("if (profiled >= 24) break", radio)
        self.assertNotIn("ServiceList", facts)
        self.assertNotIn('at("uploadDate")', facts)
        models = read("app/src/main/java/app/dkord/core/Models.kt")
        track = models[models.index("data class Track("):models.index("enum class ItemKind")]
        private_targets = [track, read("app/src/main/java/app/dkord/player/MediaItems.kt")]
        private_targets += [p.read_text() for p in (MAIN / "java/app/dkord/data/room").glob("*.kt")]
        for target in private_targets:
            for name in ("contextHint", "radioHint", "RadioFacts"):
                self.assertNotIn(name, target)

    def test_context_and_anchor_are_part_of_autoplay_response_ownership_not_queue_tail_reseeding(self):
        coordinator = read("app/src/main/java/app/dkord/player/AutoplayCoordinator.kt")
        controller = read("app/src/main/java/app/dkord/ui/search/SearchController.kt")
        self.assertIn("val seed = before.radioSeed ?: queue.last()", coordinator)
        self.assertIn("source(seed, queue, request.hint)", coordinator)
        self.assertNotIn("source(queue.last(), queue)", coordinator)
        self.assertIn("now.radioHint != request.hint", coordinator)
        self.assertIn("request.seedId", coordinator)
        self.assertIn("mutablePlaybackHint.value = mutableCorrection.value", controller)
        self.assertIn('mutablePlaybackHint.value = ""', controller)
        self.assertIn("currentCoroutineContext().ensureActive()", controller)

    def test_related_routing_has_translated_accessible_actions_and_mandatory_actual_device_cases(self):
        for key in ("shelf_play_all", "shelf_play_all_description"):
            self.assertIn(key, strings("values"))
            self.assertIn(key, strings("values-hi"))
        workflow = read(".github/workflows/validate-pr.yml")
        self.assertIn("--required-class app.dkord.RelatedPlaybackRoutingTest", workflow)
        native = read("app/src/androidTest/java/app/dkord/RelatedPlaybackRoutingTest.kt")
        for entry in ("ShelfRow(", "SearchPlaybackRow(", "Density(density.density, 1.3f)", "performClick()"):
            self.assertIn(entry, native)
        self.assertNotIn("Thread.sleep", native)

    def test_actual_ime_regressions_keep_geometry_and_real_visibility_with_ready_emulator_fixtures(self):
        workflow = read(".github/workflows/validate-pr.yml")
        self.assertIn("bash .github/scripts/prepare_emulator_ime.sh", workflow)
        setup = read(".github/scripts/prepare_emulator_ime.sh")
        for command in ("KEYCODE_WAKEUP", "dismiss-keyguard", "screen_off_timeout", "ime list -s -a", "ime enable", "ime set", "show_ime_with_hard_keyboard"):
            self.assertIn(command, setup)
        helper = read("app/src/androidTest/java/app/dkord/RealImeTestEnvironment.kt")
        self.assertIn("import androidx.compose.ui.test.junit4.ComposeTestRule", helper)
        self.assertIn("activity.hasWindowFocus()", helper)
        self.assertIn("isVisible(WindowInsetsCompat.Type.ime())", helper)
        self.assertNotIn("Thread.sleep", helper)
        search = read("app/src/androidTest/java/app/dkord/SearchKeyboardViewportTest.kt")
        self.assertIn("kotlin.math.abs(bottom - (height - ime)) <= 6 * density", search)
        self.assertIn('onNodeWithTag("navigation").assertDoesNotExist()', search)
        self.assertIn("shown = true, timeoutMs = 15_000", search)
        self.assertIn("shown = false, timeoutMs = 15_000", search)
        listen = read("app/src/androidTest/java/app/dkord/ListenAgainTest.kt")
        self.assertIn("shown = true, timeoutMs = 10_000", listen)

    def test_real_ime_timeout_reports_actual_focus_owner_and_keyguard_without_guessing_or_dismissing_it(self):
        helper = read("app/src/androidTest/java/app/dkord/RealImeTestEnvironment.kt")
        for diagnostic in ('executeShellCommand("dumpsys window")', "mCurrentFocus=", "mFocusedApp=", "isKeyguardLocked", "isDeviceLocked", "isAttachedToWindow", "decor.isShown"):
            self.assertIn(diagnostic, helper)
        self.assertNotIn("KEYCODE_BACK", helper)
        self.assertNotIn("statusbar collapse", helper)

    def test_all_junit_annotations_have_function_declarations(self):
        for path in (ROOT / "app/src/test").rglob("*.kt"):
            source = path.read_text()
            annotations = re.findall(r"@Test(?:\([^)]*\))?\s+([A-Za-z_]\w*)", source)
            self.assertEqual(source.count("@Test"), len(annotations), str(path))
            self.assertTrue(all(token == "fun" for token in annotations), str(path))

    def test_manual_entrypoints_retain_the_full_android_suite_and_build(self):
        for path in (".github/workflows/build.yml", ".github/workflows/release.yml"):
            workflow = read(path)
            self.assertIn("  workflow_dispatch:", workflow)
            if path.endswith("build.yml"):
                self.assertNotRegex(workflow, r"(?m)^\s+(?:push|pull_request|pull_request_target|schedule):")
            self.assertIn("./gradlew testDebugUnitTest assembleDebug --stacktrace", workflow)
            self.assertNotIn("continue-on-error:", workflow)
            self.assertNotIn("-x test", workflow)
            self.assertIn("python3 -B -m unittest discover", workflow)

    def test_release_push_is_only_the_explicit_versioned_request_and_keeps_original_gates(self):
        workflow = read(".github/workflows/release.yml")
        self.assertIn("branches: [arena/59a2f745-dkord]", workflow)
        self.assertIn("paths: [.github/release-requests/v0.9.1.json]", workflow)
        self.assertNotIn("paths: [.github/release-requests/v0.8.2.json]", workflow)
        self.assertNotIn("paths: [.github/release-requests/v0.9.0.json]", workflow)
        self.assertIn("TAG: ${{ inputs.tag || 'v0.9.1' }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("if: github.event_name == 'push'", workflow)
        self.assertLess(workflow.index("validate_release_request.py"),
                        workflow.index("Require the existing stable signing key"))
        self.assertNotRegex(workflow, r"(?m)^\s+(?:pull_request|pull_request_target|schedule):")
        self.assertNotIn("--clobber", workflow)

    def test_signing_password_is_passed_as_an_environment_value_not_shell_source(self):
        for path in (".github/workflows/build.yml", ".github/workflows/release.yml"):
            workflow = read(path)
            self.assertIn("KS_PASS: ${{ secrets.DKORD_KEYSTORE_PASS }}", workflow)
            self.assertIn("-storepass:env KS_PASS", workflow)
            self.assertNotRegex(workflow, r'(?m)^\s+(?:echo|printf).*secrets\.DKORD_KEYSTORE_PASS')
            self.assertIn('DKORD_KEYSTORE_PASS<<%s', workflow)

    def test_release_publication_is_after_tests_build_and_real_apk_signer_gate(self):
        workflow = read(".github/workflows/release.yml")
        gates = ["Validate release tag against app version", "python3 -B -m unittest discover",
                 "Require the existing stable signing key", "./gradlew testDebugUnitTest assembleDebug",
                 "Verify and prepare release APK", "python3 -B .github/scripts/verify_apk_update.py",
                 "Require successful full Android validation of this exact release head", "gh release create"]
        positions = [workflow.index(gate) for gate in gates]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("gh release delete", workflow)
        self.assertNotIn("gh release edit", workflow)
        self.assertIn('if [ "$previous_tag" = "$TAG" ]', workflow)
        self.assertIn('--target "$GITHUB_SHA"', workflow)
        gradle = read("app/build.gradle.kts")
        self.assertIn('applicationId = "app.dkord"', gradle)
        self.assertIn('keyAlias = "dkord"', gradle)
        self.assertRegex(gradle, r'versionName\s*=\s*"\d+\.\d+\.\d+"')

    def test_v091_publication_waits_for_its_own_full_android_run_and_has_current_honest_notes(self):
        workflow = read(".github/workflows/release.yml")
        for requirement in ('actions: read', 'checks: read', '/actions/workflows/validate-pr.yml/runs',
                            '-f head_sha="$GITHUB_SHA" -f event=pull_request -f per_page=1',
                            'gh run watch "$validation_id"', '--exit-status --interval 30',
                            'No matching-head PR validation found', 'exit 1',
                            '## New in v0.9.1', 'Shorts/Reels removed completely', 'Listen Again',
                            '378 JVM tests', '19 real Android emulator cases',
                            'Dkord-v0.9.1.apk', 'versionCode13', 'physical-phone/OEM',
                            'not account-personalized YouTube Music AI'):
            self.assertIn(requirement, workflow)
        self.assertNotIn('gh run rerun', workflow)
        self.assertNotIn('## New in v0.9.0', workflow)
        self.assertNotIn('Genuine Shorts:', workflow)

    def test_unwanted_shorts_feed_is_removed_not_hidden_behind_another_name(self):
        for path in ("app/src/main/java/app/dkord/data/shorts/ShortsRepository.kt",
                     "app/src/main/java/app/dkord/ui/shorts/ShortsController.kt",
                     "app/src/main/java/app/dkord/ui/screens/Reels.kt"):
            self.assertFalse((ROOT / path).exists(), path)
        app = read("app/src/main/java/app/dkord/ui/App.kt")
        module = read("app/src/main/java/app/dkord/di/AppModule.kt")
        self.assertNotIn("ShortsRepository", module)
        self.assertIn("TabSpec(Tab.LISTEN, Icons.Default.History, R.string.tab_listen)", app)
        self.assertNotIn("TabSpec(Tab.REELS", app)
        self.assertNotIn("ReelsScreen", app)
        for path in ("app/src/main/res/values/strings.xml", "app/src/main/res/values-hi/strings.xml"):
            self.assertNotIn('name="reels_', read(path))
            self.assertNotIn('name="tab_reels"', read(path))

    def test_listen_again_uses_local_history_single_track_play_and_safe_resume(self):
        screen = read("app/src/main/java/app/dkord/ui/screens/ListenAgain.kt")
        vm = read("app/src/main/java/app/dkord/ui/listen/ListenAgainViewModel.kt")
        self.assertIn("onPlay(listOf(it), 0)", screen)
        self.assertIn("actions.player.resume()", screen)
        self.assertIn("library.history()", vm)
        for forbidden in ("MusicRepository", "ShortsSource", "VideoResolver", "VerticalPager", "ExoPlayer", "searchQHFactory"):
            self.assertNotIn(forbidden, screen + vm)
        resume = read("app/src/main/java/app/dkord/player/ResumePlayback.kt")
        self.assertNotIn("setMediaItems", resume)
        self.assertNotIn("stop()", resume)
        self.assertIn("player.play()", resume)
        dao = read("app/src/main/java/app/dkord/data/db/Daos.kt")
        self.assertIn('DELETE FROM history WHERE trackId = :id', dao)
        self.assertNotIn('DELETE FROM tracks', dao)
        # History still uses a projection. Schema2 is exclusively the additive download-destination migration.
        database = read("app/src/main/java/app/dkord/data/db/AppDatabase.kt")
        self.assertIn('version = 2', database)
        self.assertIn('addMigrations(MIGRATION_1_2)', database)
        self.assertEqual(database.count('ALTER TABLE downloads ADD COLUMN'), 3)
        self.assertNotIn('ALTER TABLE history', database)
        self.assertNotIn('fallbackToDestructiveMigration', database)
        nav = read("app/src/main/java/app/dkord/ui/Nav.kt")
        self.assertIn("if (value == Tab.REELS) Tab.LISTEN", nav)
        self.assertIn("rememberSaveable(stateSaver = TabSaver)", read("app/src/main/java/app/dkord/ui/App.kt"))
        self.assertIn("--required-class app.dkord.ListenAgainTest", read(".github/workflows/validate-pr.yml"))

    def test_real_studio_uses_local_clips_actual_aac_composition_and_durable_background_work(self):
        exporter = read("app/src/main/java/app/dkord/data/studio/StudioAudioExporter.kt")
        worker = read("app/src/main/java/app/dkord/data/studio/StudioExportWorker.kt")
        repo = read("app/src/main/java/app/dkord/data/studio/StudioRepository.kt")
        for fragment in ("EditedMediaItemSequence.withAudioFrom", "setTransmuxAudio(false)", "MimeTypes.AUDIO_AAC",
                         "setStartPositionMs(clip.startMs)", "setEndPositionMs(clip.endMs)", "Dispatchers.Main.immediate",
                         "transformer?.cancel()", "output.delete()"):
            self.assertIn(fragment, exporter)
        self.assertIn("CoroutineWorker", worker)
        self.assertIn("FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING", worker)
        self.assertIn("db.withTransaction", worker)
        self.assertIn("DownloadState.DONE", worker)
        self.assertIn("MediaStore.Audio.Media.IS_PENDING", worker)
        self.assertIn("cleanUnreferencedSources", repo)
        self.assertIn("if (mutable.value.loading || mutable.value.failed) return", repo)
        self.assertIn("require(source != destination)", repo)
        self.assertIn("StudioRenderRequest(id, snapshot)", repo)
        self.assertIn("AtomicFile", repo)
        self.assertIn("importing", read("app/src/main/java/app/dkord/ui/studio/StudioViewModel.kt"))
        tests = read("app/src/androidTest/java/app/dkord/StudioAudioExportTest.kt")
        self.assertIn("assertTone(decoded", tests)
        self.assertIn("MediaCodec.createDecoderByType", tests)
        self.assertIn("job.cancelAndJoin()", tests)

    def test_generated_audio_cannot_leak_into_remote_resolvers_radio_lyrics_or_room_metadata(self):
        stream = read("app/src/main/java/app/dkord/player/StreamDataSource.kt")
        self.assertLess(stream.index("if (isLocalAudioId(id))"), stream.index("streams.resolve(id"))
        for path in ("data/stream/Resolvers.kt", "data/stream/VideoResolver.kt", "data/yt/MusicRepository.kt",
                     "data/yt/RadioTracks.kt", "data/lyrics/Lyrics.kt", "data/download/DownloadManager.kt",
                     "data/room/RoomPlayback.kt", "player/PlayerController.kt"):
            self.assertIn("isLocalAudioId", read("app/src/main/java/app/dkord/" + path))
        room = read("app/src/main/java/app/dkord/data/room/RoomPlayback.kt")
        self.assertIn("takeUnless { isLocalAudioId(it.id) }", room)
        self.assertIn("!isLocalAudioId(it.id)", room)
        sharing = read("app/src/main/java/app/dkord/ui/common/Share.kt")
        editor = read("app/src/main/java/app/dkord/ui/studio/ClipEditor.kt")
        self.assertIn("decorFitsSystemWindows = false", editor)
        self.assertIn("safeDrawingPadding()", editor)
        self.assertIn("Box(Modifier.weight(1f, fill = false)) { content() }", editor)
        self.assertIn("Intent.EXTRA_STREAM", sharing)
        self.assertIn("FLAG_GRANT_READ_URI_PERMISSION", sharing)
        paths = read("app/src/main/res/xml/file_paths.xml")
        self.assertIn('path="studio/exports/"', paths)
        self.assertNotIn("<root-path", paths)
        self.assertNotIn('path="studio/"', paths)
        self.assertNotIn('path="."', paths)

    def test_editor_is_reachable_and_device_gate_requires_real_audio_and_ui_regressions(self):
        app = read("app/src/main/java/app/dkord/ui/App.kt")
        self.assertIn("is Dest.Studio -> StudioScreen", app)
        self.assertIn("push(Dest.Studio(t))", app)
        self.assertIn("onOpenStudio = { push(Dest.Studio()) }", app)
        workflow = read(".github/workflows/validate-pr.yml")
        for case in ("SearchKeyboardViewportTest", "StudioAudioExportTest", "StudioClipEditorTest", "StudioExportPublicationTest"):
            self.assertIn("--required-class app.dkord." + case, workflow)
        self.assertIn("summarize_device_tests.py", workflow)
        self.assertIn("bash -o pipefail -c './gradlew connectedDebugAndroidTest", workflow)
        self.assertNotIn("continue-on-error:", workflow)


if __name__ == "__main__":
    unittest.main()
