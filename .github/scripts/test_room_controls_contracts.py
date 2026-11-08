"""Source safety rails only; real protocol/player/UI execution is covered by Kotlin/device CI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class RoomControlsContractsTest(unittest.TestCase):
    def test_default_and_administration_remain_creator_only(self):
        controller = read("app/src/main/java/app/dkord/data/room/RoomController.kt")
        service = read("app/src/main/java/app/dkord/data/room/RoomSharing.kt")
        self.assertIn("private var mode = RoomControlMode.HOST_ONLY", service)
        for method in ("fun controlMode(", "fun memberControl("):
            section = controller[controller.index(method):].split("\n", 1)[0]
            self.assertIn("state.value.role == RoomRole.HOST", section)
        self.assertIn("if (value == RoomControlMode.HOST_ONLY) selected.clear()", service)
        self.assertIn("unsigned.revision == revision", service)

    def test_guests_propose_explicit_commands_not_playback_state_listeners(self):
        player = read("app/src/main/java/app/dkord/player/PlayerController.kt")
        room = read("app/src/main/java/app/dkord/data/room/RoomController.kt")
        adapter = read("app/src/main/java/app/dkord/data/room/PlayerRoomPlayback.kt")
        self.assertIn("playback.controls.collect", room)
        listener = player[player.index("private val listener ="):player.index("private fun autoplaySnapshot")]
        self.assertNotIn("commandEvents", listener)
        self.assertIn("val ticket = commandGate.capture()", player)
        self.assertIn("if (!ticket.isCurrent()) return@execute", player)
        self.assertIn("isPlaying = value.playWhenReady", player)
        self.assertIn("player.withoutRoomCommands(isCurrent =", adapter)
        self.assertIn("player.resume()", adapter)
        self.assertNotIn("player.togglePlay()", adapter)

    def test_roles_and_playback_topics_stay_separate_with_original_privacy(self):
        transport = read("app/src/main/java/app/dkord/data/room/NtfyRoomTransport.kt")
        self.assertIn('RoomCode.topic(code) + "-controls"', transport)
        for guard in ("CookieJar.NO_COOKIES", "Authenticator.NONE", "followRedirects(false)", "call.cancel()", "readUtf8LineStrict(16_384)"):
            self.assertIn(guard, transport)
        self.assertIn('addQueryParameter("since", "12h")', transport)

    def test_control_security_has_crypto_binding_replay_permission_and_payload_bounds(self):
        codec = read("app/src/main/java/app/dkord/data/room/RoomControlMessage.kt")
        service = read("app/src/main/java/app/dkord/data/room/RoomSharing.kt")
        for guard in ("SHA256withECDSA", "secp256r1", "ownerCode(message.publicKey) == code", "const val MAX_MEMBERS = 48"):
            self.assertIn(guard, codec)
        for guard in ("frame.revision == revision", "allowed(id)", "frame.sequence <= (received[id] ?: 0)", "frame.timestamp >= now() - 10_000"):
            self.assertIn(guard, service)

    def test_all_previous_native_classes_plus_real_room_cases_remain_mandatory(self):
        workflow = read(".github/workflows/validate-pr.yml")
        for name in ("SearchKeyboardViewportTest", "StudioAudioExportTest", "StudioClipEditorTest", "StudioExportPublicationTest",
                     "ListenAgainTest", "RelatedPlaybackRoutingTest", "OnlineStudioAndStorageTest", "DownloadDestinationTest", "StudioSongPickerTest", "RoomCoHostTest"):
            self.assertIn("--required-class app.dkord." + name, workflow)
        native = read("app/src/androidTest/java/app/dkord/RoomCoHostTest.kt")
        for executed in ("performClick()", "RoomIdentity.generate()", "RoomController(relay", "Density(density.density, 1.35f)"):
            self.assertIn(executed, native)
        self.assertNotIn("Thread.sleep", native)

    def test_room_lifecycle_expires_remote_callbacks_without_stopping_the_normal_player(self):
        controller = read("app/src/main/java/app/dkord/data/room/RoomController.kt")
        self.assertIn("playback.cancelSync()", controller)
        self.assertNotIn("playback.stop()", controller)
        self.assertNotIn("player.stop()", controller)
        for file in ("RoomControlMessageTest", "RoomSharingTest", "RoomCoHostControllerTest", "PlaybackCommandGateTest"):
            self.assertIn("@Test", read(f"app/src/test/java/app/dkord/{file}.kt"))

if __name__ == "__main__":
    unittest.main()
