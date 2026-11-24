"""Run: python3 -m unittest discover -s tests   (from the sdk folder). No network, no ROS."""

import array
import datetime as dt
import http.server
import json
import os
import sys
import threading
import unittest

SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SDK)

from oasis_voice.actions import ToolRouter, enabled_tools  # noqa: E402
from oasis_voice.audio import NoiseGate  # noqa: E402
from oasis_voice.builder import agent_body  # noqa: E402
from oasis_voice.directory import DUBAI, Directory, normalize, open_now  # noqa: E402
from oasis_voice.profile import load_profile, validate  # noqa: E402
from oasis_voice.prompt import build_prompt  # noqa: E402

PROFILE = load_profile(os.path.join(SDK, "profiles", "dtec_navigator.json"))


def tone(level, n=1600):
    return array.array("h", [level if i % 2 else -level for i in range(n)]).tobytes()


class DirectoryTest(unittest.TestCase):
    def setUp(self):
        self.d = Directory(PROFILE)

    def check(self, query, status, place=None, lang="en"):
        out = self.d.lookup(query, lang)
        self.assertEqual(out["status"], status, f"{query!r} -> {out}")
        if place:
            self.assertEqual(out["place_id"], place, query)
        return out

    def test_exact_names(self):
        self.check("where are the toilets", "found", "toilets")
        self.check("Oraseya Capital please", "found", "oraseya_capital")

    def test_misheard_name(self):
        self.check("I'm going to Orasia Capital", "found", "oraseya_capital")

    def test_arabic(self):
        out = self.check("وين المصعد", "found", "lifts", lang="ar")
        self.assertTrue(any("يسار" in s for s in out["steps"]))  # Arabic steps
        self.check("أوراسيا كابيتال", "found", "oraseya_capital", lang="ar")

    def test_keyword_single_match(self):
        self.check("where is the bank", "found", "emirates_nbd")

    def test_clarification(self):
        out = self.check("where is the mosque", "ambiguous")
        self.assertEqual(len(out["options"]), 3)
        out = self.check("I want to pray", "ambiguous")
        self.assertEqual(out["options"][0]["place_id"], "prayer_room")  # inside the building first

    def test_follow_up_by_id(self):
        out = self.d.lookup("", "en", place_id="dso_masjid")
        self.assertEqual(out["status"], "found")

    def test_unknown(self):
        self.check("where is the Google office", "not_found")

    def test_name_beats_keyword(self):
        self.check("Dtec cafe", "found", "cafe_dtec")

    def test_normalize_arabic_variants(self):
        self.assertEqual(normalize("أصلي"), normalize("اصلي"))
        self.assertEqual(normalize("café"), "cafe")

    def test_open_now(self):
        at = lambda h, m=0: dt.datetime(2026, 11, 24, h, m, tzinfo=DUBAI)
        self.assertTrue(open_now("08:00-24:00", at(23, 30)))
        self.assertFalse(open_now("08:00-24:00", at(7, 59)))
        self.assertTrue(open_now("20:00-02:00", at(1)))
        self.assertTrue(open_now("24h", at(3)))
        self.assertIsNone(open_now(None))


class ProfileTest(unittest.TestCase):
    def test_both_profiles_valid(self):
        for name in os.listdir(os.path.join(SDK, "profiles")):
            load_profile(os.path.join(SDK, "profiles", name))

    def test_validation_catches_mistakes(self):
        bad = json.loads(json.dumps({k: v for k, v in PROFILE.items() if k != "_path"}))
        bad["places"].append(dict(bad["places"][0]))
        bad["places"][-1]["hours"] = "9 to 5"
        problems = validate(bad)
        self.assertTrue(any("duplicate" in p for p in problems))
        self.assertTrue(any("hours" in p for p in problems))


class PromptAndBuildTest(unittest.TestCase):
    def test_prompt_rules(self):
        p = build_prompt(PROFILE)
        self.assertIn("ALWAYS call lookup_place", p)
        self.assertIn("{{system__time}}", p)
        self.assertIn("request_operator", p)

    def test_agent_body_for_robot(self):
        body = agent_body(PROFILE, ["t1"])
        c = body["conversation_config"]
        self.assertEqual(c["tts"]["agent_output_audio_format"], "pcm_16000")
        self.assertEqual(c["asr"]["user_input_audio_format"], "pcm_16000")
        self.assertIn("ar", c["language_presets"])
        self.assertIn("Oraseya Capital", c["asr"]["keywords"])
        self.assertFalse(body["platform_settings"]["auth"]["enable_auth"])

    def test_tools_follow_actions(self):
        names = [t["name"] for t in enabled_tools({"actions": {"operator": True}})]
        self.assertEqual(names, ["lookup_place", "request_operator"])


class NoiseGateTest(unittest.TestCase):
    def test_background_noise_blocked_speech_passes(self):
        g = NoiseGate(min_rms=300, hangover_s=0.2, preroll_s=0.2)
        for _ in range(20):
            self.assertEqual(g.process(tone(100)), [])  # steady background hum
        out = g.process(tone(3000))                      # someone talks
        self.assertEqual(len(out), 3)                    # 2 pre-roll chunks + this one
        self.assertEqual(g.process(tone(100)), [tone(100)])  # hangover keeps the sentence end
        g.process(tone(100))
        self.assertEqual(g.process(tone(100)), [])      # then closes again

    def test_disabled(self):
        g = NoiseGate(enabled=False)
        self.assertEqual(g.process(tone(10)), [tone(10)])


class _Screen(http.server.BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        _Screen.received.append((self.path, body, self.headers.get("x-tool-secret")))
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true, "message": "done"}')

    def log_message(self, *a):
        pass


class ToolRouterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Screen)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_lookup_tool(self):
        r = ToolRouter(PROFILE, log=lambda *a: None)
        text, err = r.handle("lookup_place", {"query": "toilets", "language": "en"})
        self.assertFalse(err)
        self.assertEqual(json.loads(text)["place_id"], "toilets")

    def test_route_uses_directory_steps(self):
        _Screen.received.clear()
        r = ToolRouter(PROFILE, self.url, "s3cret", log=lambda *a: None)
        text, err = r.handle("send_route_to_phone", {"place_id": "oraseya_capital", "language": "ar"})
        self.assertFalse(err, text)
        path, body, secret = _Screen.received[-1]
        self.assertEqual(path, "/api/send-route")
        self.assertEqual(secret, "s3cret")
        self.assertIn("الطابق الأول", body["steps"])

    def test_operator_always_gives_location(self):
        r = ToolRouter(PROFILE, "", log=lambda *a: None)  # no screen
        text, err = r.handle("request_operator", {"reason": "wants a person", "language": "en"})
        self.assertFalse(err)
        self.assertIn("reception desk", json.loads(text)["operator_location"])

    def test_offline_check_in_is_honest(self):
        r = ToolRouter(PROFILE, "", log=lambda *a: None)
        text, err = r.handle("check_in_visitor", {"host_company": "Oraseya Capital", "language": "en"})
        self.assertTrue(err)
        self.assertIn("offline", json.loads(text)["message"])

    def test_unknown_tool(self):
        _, err = ToolRouter(PROFILE, log=lambda *a: None).handle("nope", {})
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
