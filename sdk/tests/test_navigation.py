"""Blind navigation tests. Run: python3 -m unittest discover -s tests   (no network, no ROS)."""

import array
import copy
import json
import math
import os
import random
import re
import sys
import time
import types
import unittest
from unittest import mock

SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SDK)

from oasis_voice.actions import ToolRouter, enabled_tools  # noqa: E402
from oasis_voice.audio import NoiseGate  # noqa: E402
from oasis_voice.builder import _tool_body, agent_body  # noqa: E402
from oasis_voice.navigator import Navigator, turn_angle  # noqa: E402
from oasis_voice.profile import load_profile, validate  # noqa: E402
from oasis_voice.prompt import build_prompt  # noqa: E402
from oasis_voice.sense import MarkerFilter  # noqa: E402

PROFILE = load_profile(os.path.join(SDK, "profiles", "dtec_floor.json"))
NODES = {n["id"]: n for n in PROFILE["floor"]["nodes"]}


class WordForWordOperator:
    """Knows nothing about the route. Reads the sentence and does it, on the real floor."""

    def __init__(self, nav):
        self.names = {nav.node_name(k): k for k in nav.nodes}
        s = PROFILE["floor"]["start"]
        self.x, self.y, self.heading = NODES[s["node"]]["x"], NODES[s["node"]]["y"], s["heading"]

    def turn(self, text):
        if m := re.search(r"Turn to face (.+?), then", text):
            n = NODES[self.names[m.group(1)]]
            self.heading = math.degrees(math.atan2(n["x"] - self.x, n["y"] - self.y))
        elif "Turn around" in text:
            self.heading += 180
        elif m := re.search(r"Turn (slightly )?(left|right)", text):
            size = 45 if m.group(1) else 90
            self.heading += -size if m.group(2) == "left" else size
        self.heading %= 360

    def target(self, text):
        """(node, metres) of the landmark named in "stop at X", which must be ahead on this line."""
        node = self.names[re.search(r"and stop at (.+?)\.", text).group(1)]
        dx, dy = NODES[node]["x"] - self.x, NODES[node]["y"] - self.y
        dist = math.hypot(dx, dy)
        if dist > 1e-6:
            off = turn_angle(self.heading, math.degrees(math.atan2(dx, dy)))
            assert abs(off) < 1, f"{node} is not ahead ({off:.0f} degrees off): {text}"
        return node, dist

    def follow(self, text, part=1.0):
        self.turn(text)
        node, dist = self.target(text)
        self.x += math.sin(math.radians(self.heading)) * dist * part
        self.y += math.cos(math.radians(self.heading)) * dist * part
        return node

    def at(self, node):
        return math.hypot(NODES[node]["x"] - self.x, NODES[node]["y"] - self.y) < 1e-6


class RouteTest(unittest.TestCase):
    def setUp(self):
        self.nav = Navigator(PROFILE)

    def test_brief_demo(self):
        """The winning demo in the brief: quiet place, second booth, then someone wants the conference room."""
        found = self.nav.find("أبي مكان هادي أسوي فيه مكالمة", "ar")
        self.assertEqual(found["status"], "group")
        self.assertIn("will this do", found["say"])
        self.assertEqual(self.nav.find("الكابينة الثانية", "ar")["place_id"], "booth_2")
        out = self.nav.start_route("booth_2", "ar")
        self.assertIn("كابينة المكالمات الثانية", out["say_visitor"])
        out = self.nav.step_done(out["step"])
        self.assertIn("Turn left", out["say_operator"])
        self.assertIn("past the kitchen", out["say_operator"])
        self.assertIn("stop at the second call booth", out["say_operator"])
        out = self.nav.start_route("conference_room", "en")
        self.assertEqual(out["status"], "changed")
        self.assertIn("Turn around", out["say_operator"])
        self.assertIn("قاعة المؤتمرات", out["say_first_visitor"])
        self.assertEqual(out["say_in_order"][0], "Operator: stop, please.")  # the robot is moving
        self.assertIn("Turn around", out["say_in_order"][-1])
        out = self.nav.step_done(out["step"])
        self.assertEqual(out["status"], "arrived")
        self.assertEqual(out["offer_next"]["place_id"], "booth_2")

    def test_operator_words_are_always_english(self):
        for lang in ("ar", "hi", "ur"):
            nav = Navigator(PROFILE)
            out = nav.start_route("booth_3", lang)
            while out["status"] != "arrived":
                self.assertTrue(out["say_operator"].isascii(), out)
                out = nav.step_done(out["step"])

    def test_same_done_twice_does_not_skip(self):
        out = self.nav.start_route("booth_2", "en")
        second = self.nav.step_done(out["step"])
        again = self.nav.step_done(out["step"])
        self.assertEqual(again["status"], "same_step")
        self.assertEqual(again["say_operator"], second["say_operator"])

    def test_unknown_request_is_not_guessed(self):
        self.assertEqual(self.nav.find("where is the mosque", "en")["status"], "not_found")
        self.assertEqual(self.nav.start_route("mosque", "en")["status"], "error")

    def test_other_languages_retry_in_english(self):
        self.assertEqual(self.nav.find("sala de conferencias", "es")["status"], "retry_in_english")
        self.assertEqual(self.nav.find("conference room", "es")["status"], "ask_first")  # translated by the AI: confirm
        self.assertEqual(self.nav.find("sala de conferencias", "en")["status"], "not_found")

    def test_vague_request_asks(self):
        self.assertEqual(self.nav.find("I have a meeting", "en")["status"], "ambiguous")
        self.assertEqual(self.nav.find("I'm hungry", "en")["status"], "ask_first")
        self.assertEqual(self.nav.find("मुझे चाय चाहिए", "hi")["say_in_order"], ["क्या मैं आपको रसोई ले चलूँ?"])

    def test_visitor_says_where_they_are(self):
        """Reported live: "I'm at the main junction, take me to booth three" was routed from the start."""
        out = self.nav.start_route("booth_3", "hi", start_at="main junction")
        self.assertEqual(out["steps_left"], 1)
        self.assertIn("Turn to face the kitchen, then walk straight about 12 metres", out["say_operator"])
        self.assertEqual(self.nav.step_done(out["step"])["status"], "arrived")
        self.assertEqual(Navigator(PROFILE).start_route("booth_3", "hi", start_at="the moon")["status"], "not_found")

    def test_start_at_the_start_keeps_the_heading(self):
        self.assertIn("Walk straight about 6", self.nav.start_route("kitchen", "en", start_at="the starting point")["say_operator"])

    def test_one_visitor_changes_their_mind(self):
        self.nav.start_route("kitchen", "ar")
        out = self.nav.start_route("team_tables", "ar", same_person=True)
        self.assertEqual(len(out["say_in_order"]), 3)
        while out["status"] != "arrived":
            out = self.nav.step_done(out["step"])
        self.assertNotIn("offer_next", out)

    def test_asks_only_when_the_answer_matters(self):
        out = self.nav.start_route("booth_4", "en")
        out = self.nav.step_done(out["step"])
        asked = self.nav.start_route("booth_1", "en")  # before or after the first booth? it matters
        self.assertEqual(asked["status"], "need_position")
        out = self.nav.start_route("booth_1", "en", "third call booth")
        self.assertIn("Turn around", out["say_operator"])

    def test_lost_then_found(self):
        out = self.nav.start_route("booth_2", "en")
        old_step = out["step"]
        out = self.nav.update_position("conference room")  # nobody said which way the robot looks
        self.assertEqual(out["status"], "rerouted")
        self.assertIn("Turn to face the meeting room", out["say_operator"])
        self.assertEqual(self.nav.step_done(old_step)["status"], "same_step")  # an old "done" moves nothing
        out = self.nav.update_position("conference room", "meeting room")
        self.assertIn("Keep walking straight", self.nav.update_position("meeting room")["say_operator"])
        self.assertIn("stop at the second call booth", out["say_operator"])

    def test_cancel_forgets_the_position(self):
        self.nav.start_route("kitchen", "en")
        self.nav.cancel()
        self.assertEqual(self.nav.start_route("kitchen", "en")["status"], "need_position")

    def test_already_there(self):
        out = self.nav.start_route("kitchen", "en")
        while out["status"] != "arrived":
            out = self.nav.step_done(out["step"])
        self.assertEqual(self.nav.start_route("kitchen", "ar")["status"], "arrived")

    def test_operator_gets_there_from_everywhere(self):
        goals = [p for p in PROFILE["places"] if p.get("node")]
        for first in goals:
            for second in goals:
                nav = Navigator(PROFILE)
                op = WordForWordOperator(nav)
                for goal in (first, second):
                    out = nav.start_route(goal["id"], "en")
                    for _ in range(20):
                        if out["status"] == "arrived":
                            break
                        op.follow(out["say_operator"])
                        out = nav.step_done(out["step"])
                    self.assertTrue(op.at(goal["node"]), f"{first['id']} -> {second['id']}")

    def test_operator_gets_there_from_any_told_spot(self):
        for spot in NODES:
            for goal in [p for p in PROFILE["places"] if p.get("node")]:
                nav = Navigator(PROFILE)
                op = WordForWordOperator(nav)
                op.x, op.y, op.heading = NODES[spot]["x"], NODES[spot]["y"], 137  # looking anywhere
                if spot == PROFILE["floor"]["start"]["node"]:
                    op.heading = PROFILE["floor"]["start"]["heading"]
                out = nav.start_route(goal["id"], "ar", start_at=spot)
                for _ in range(20):
                    if out["status"] == "arrived":
                        break
                    op.follow(out["say_operator"])
                    out = nav.step_done(out["step"])
                self.assertTrue(op.at(goal["node"]), f"{spot} -> {goal['id']}")

    def test_destination_changes_anywhere_on_the_way(self):
        """500 trips: interrupted at a random point, up to 3 times. The operator only hears the words."""
        rnd = random.Random(1)
        goals = [p for p in PROFILE["places"] if p.get("node")]
        asked = 0
        for trip in range(500):
            nav = Navigator(PROFILE)
            op = WordForWordOperator(nav)
            goal = rnd.choice(goals)
            out = nav.start_route(goal["id"], "ar")
            changes = rnd.randint(1, 3)
            for _ in range(60):
                if out["status"] == "arrived":
                    break
                if changes and rnd.random() < 0.5:
                    changes -= 1
                    chain = list(nav._leg_now()["chain"])
                    op.follow(out["say_operator"], rnd.uniform(0.05, 0.95))
                    passed = [k for k in chain if (NODES[k]["x"] - op.x) * math.sin(math.radians(op.heading))
                              + (NODES[k]["y"] - op.y) * math.cos(math.radians(op.heading)) < 0]
                    goal = rnd.choice([g for g in goals if g is not goal])
                    out = nav.start_route(goal["id"], "en")
                    if out["status"] == "need_position":
                        asked += 1
                        out = nav.start_route(goal["id"], "en", passed[-1])
                    self.assertEqual(out["status"], "changed", out)
                    continue
                op.follow(out["say_operator"])
                out = nav.step_done(out["step"])
            self.assertEqual(out["status"], "arrived")
            self.assertTrue(op.at(goal["node"]), f"trip {trip} ended in the wrong place")
        self.assertGreater(asked, 5)


class FloorDataTest(unittest.TestCase):
    def bad(self, change):
        p = copy.deepcopy(PROFILE)
        change(p)
        return " ".join(validate(p))

    def test_mistakes_are_caught(self):
        self.assertIn("no way to reach", self.bad(lambda p: p["floor"]["edges"].remove(["junction", "team_tables"])
                                                  or p["floor"]["edges"].remove(["team_tables", "far_corner"])))
        self.assertIn("both ends must be known", self.bad(lambda p: p["floor"]["edges"].append(["kitchen", "roof"])))
        self.assertIn("needs a node", self.bad(lambda p: p["places"][1].pop("node")))
        self.assertIn("start.node", self.bad(lambda p: p["floor"]["start"].update(node="nowhere")))
        self.assertIn("needs a name", self.bad(lambda p: p["floor"]["nodes"][1].pop("name")))


class AgentTest(unittest.TestCase):
    def test_body(self):
        body = agent_body(PROFILE, ["t"])
        c = body["conversation_config"]
        self.assertEqual(c["asr"]["provider"], "scribe_v3_live")
        self.assertEqual(sorted(c["language_presets"]), ["ar", "de", "es", "fr", "hi", "pt", "ru", "tr", "ur", "zh"])
        self.assertEqual(c["tts"]["voice_id"], "gVzwmdZzRgBrNjXaTmi5")
        self.assertEqual(c["tts"]["agent_output_audio_format"], "pcm_16000")
        self.assertEqual(c["turn"]["turn_timeout"], 30)
        self.assertTrue(body["platform_settings"]["overrides"]["conversation_config_override"]["agent"]["first_message"])

    def test_tools(self):
        specs = enabled_tools(PROFILE)
        self.assertEqual([t["name"] for t in specs], ["find_place", "start_route", "step_done", "update_position",
                                                      "route_status", "cancel_route", "request_human"])
        for t in specs:
            cfg = _tool_body(t)["tool_config"]
            self.assertTrue(cfg["expects_response"])
            self.assertLessEqual(set(cfg["parameters"]["required"]), set(cfg["parameters"]["properties"]))
        self.assertIn("Operator:", build_prompt(PROFILE))

    def test_every_tool_name_runs(self):
        r = ToolRouter(PROFILE, log=lambda *a: None)
        for t in enabled_tools(PROFILE):
            text, err = r.handle(t["name"], {"query": "kitchen", "place_id": "kitchen", "language": "ar", "step": "1", "at": "kitchen"})
            self.assertFalse(err, text)
        self.assertTrue(r.handle("nope", {})[1])

    def test_human_is_honest_offline(self):
        out = json.loads(ToolRouter(PROFILE, log=lambda *a: None).handle("request_human", {"reason": "x"})[0])
        self.assertFalse(out["alerted"])
        self.assertIn("nobody was alerted", out["say"])


class MusicTest(unittest.TestCase):
    def test_gate_closes_on_steady_music_but_lets_speech_through(self):
        def noise(level, seed):
            rnd = random.Random(seed)
            return array.array("h", [int(rnd.gauss(0, level)) for _ in range(1600)]).tobytes()
        g = NoiseGate()
        for i in range(80):
            out = g.process(noise(800, i))
        self.assertEqual(out, [])
        self.assertTrue(g.process(noise(4000, 99)))

    def test_threshold_is_capped(self):
        g = NoiseGate()
        g.floor = 20000
        self.assertEqual(g.threshold, 2500)


class MarkerTest(unittest.TestCase):
    def test_filter(self):
        f = MarkerFilter(min_px=70)
        self.assertIsNone(f.look([("DTEC:kitchen", 30)]))   # too far
        self.assertIsNone(f.look([("DTEC:kitchen", 90)]))   # first look
        self.assertEqual(f.look([("DTEC:kitchen", 95)]), "kitchen")
        self.assertIsNone(f.look([("DTEC:kitchen", 99)]))   # only once
        self.assertIsNone(f.look([("https://example.com", 300)]))

    def test_marker_confirms_arrival_once(self):
        r = ToolRouter(PROFILE, log=lambda *a: None)
        r.handle("start_route", {"place_id": "kitchen", "language": "ar"})
        self.assertEqual(r.marker("junction")["status"], "next_step")
        self.assertIsNone(r.marker("not_ours"))
        self.assertEqual(r.marker("kitchen")["status"], "arrived")
        self.assertIsNone(r.marker("kitchen"))


def fake_ros():
    """Just enough of ROS 2 and AimDK to load bridge.py on a laptop."""
    def mod(name, **kw):
        m = types.ModuleType(name)
        m.__dict__.update(kw)
        return m

    class FakeNode:
        def __init__(self, name):
            pass
        create_subscription = create_publisher = create_client = lambda self, *a, **k: mock.MagicMock()

    vad = types.SimpleNamespace(AUDIO_VAD_STATE_BEGIN=1, AUDIO_VAD_STATE_END=3)
    msgs = {k: mock.MagicMock() for k in ("AudioCapture", "AudioData", "AudioInfo", "AudioPlayback", "CommonState", "FocusRequester",
                                          "FocusResponse", "ProcessedAudioOutput")}
    return {
        "websocket": mod("websocket"),
        "rclpy": mod("rclpy"), "rclpy.executors": mod("e", MultiThreadedExecutor=mock.MagicMock()),
        "rclpy.node": mod("n", Node=FakeNode),
        "rclpy.qos": mod("q", QoSHistoryPolicy=mock.MagicMock(), QoSProfile=mock.MagicMock(), QoSReliabilityPolicy=mock.MagicMock()),
        "aimdk_msgs": mod("a"), "aimdk_msgs.msg": mod("m", AudioVadStateType=vad, **msgs),
        "aimdk_msgs.srv": mod("s", AbandonAudioFocus=mock.MagicMock(), RequestAudioFocus=mock.MagicMock(), StopAudioPlay=mock.MagicMock()),
    }


class BridgeTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(sys.modules, fake_ros())
        patch.start()
        self.addCleanup(patch.stop)
        sys.modules.pop("oasis_voice.bridge", None)
        self.addCleanup(sys.modules.pop, "oasis_voice.bridge", None)
        import importlib
        bridge = importlib.import_module("oasis_voice.bridge")
        bridge.log = lambda *a: None
        self.bridge_mod = bridge
        self.b = bridge.Bridge("agent", "", ToolRouter(PROFILE, log=lambda *a: None))
        self.sent = []
        self.b.send = self.sent.append

    def mic(self, stream):
        self.b.on_mic(types.SimpleNamespace(stream_id=stream, audio_data=b"\0\0", audio_vad_state=types.SimpleNamespace(value=0)))

    def test_raw_mic_mixes_the_four_mics_and_drops_the_speaker_reference(self):
        import array
        frames = 50
        data = array.array("h")
        for _ in range(frames):
            data.extend([100, 200, 300, 400, 30000, 30000])  # 4 mics, 2 speaker reference channels
        msg = types.SimpleNamespace(info=types.SimpleNamespace(channels=6), mic_channels=4,
                                    data=types.SimpleNamespace(data=data.tobytes()))
        self.b.on_raw_mic(msg)
        out = array.array("h")
        out.frombytes(self.b.mic_q.get())
        self.assertEqual(len(out), frames)
        self.assertEqual(out[0], 250)

    def test_raw_mic_is_muted_while_the_robot_speaks(self):
        self.b.speaking_until = time.monotonic() + 5
        self.b.on_raw_mic(types.SimpleNamespace(info=types.SimpleNamespace(channels=6), mic_channels=4,
                                                data=types.SimpleNamespace(data=bytes(12))))
        self.assertTrue(self.b.mic_q.empty())

    def test_builtin_mic_zero_is_kept(self):
        self.mic(0)
        self.mic(1)
        self.assertEqual(self.b.mic_stream, 0)
        self.assertEqual(self.b.mic_q.qsize(), 1)
        self.assertEqual(self.b.heard_streams, {0, 1})

    def test_first_connection_greets_normally(self):
        self.b.on_open(None)
        self.assertEqual(self.sent, [{"type": "conversation_initiation_client_data"}])

    def test_network_drop_resumes_the_route(self):
        self.b.on_open(None)
        self.b.router.handle("start_route", {"place_id": "booth_2", "language": "ar"})
        self.b.on_close(None, 1006, "")
        self.assertEqual(bytes(self.b.spk), self.bridge_mod.LOST_SIGNAL)
        self.sent.clear()
        self.b.on_open(None)
        first = self.sent[0]["conversation_config_override"]["agent"]["first_message"]
        self.assertIn("Operator: Walk straight", first)
        self.assertEqual(self.sent[1]["type"], "contextual_update")

    def test_refused_override_is_not_repeated(self):
        self.b.on_open(None)
        self.b.router.handle("start_route", {"place_id": "booth_2", "language": "ar"})
        self.b.on_close(None, 1006, "")
        self.b.on_open(None)
        self.b.on_close(None, 1008, "override not allowed")
        self.sent.clear()
        self.b.on_open(None)
        self.assertNotIn("conversation_config_override", self.sent[0])

    def test_marker_speaks_only_when_it_matters(self):
        self.b.connected = True
        self.b.router.handle("start_route", {"place_id": "booth_2", "language": "ar"})
        self.b.on_marker("junction")
        self.assertEqual(self.sent[-1]["type"], "user_message")
        self.b.on_marker("kitchen")
        self.assertEqual(self.sent[-1]["type"], "contextual_update")
        self.b.on_marker("booth_2")
        self.assertIn("arrived", self.sent[-1]["text"])

    def test_tool_call_gets_an_answer(self):
        self.b.run_tool({"tool_name": "find_place", "tool_call_id": "c1", "parameters": {"query": "kitchen", "language": "en"}})
        self.assertEqual(self.sent[-1]["tool_call_id"], "c1")
        self.assertIn("kitchen", self.sent[-1]["result"])


if __name__ == "__main__":
    unittest.main()
