"""On-device tool handlers.

The agent's tools are "client tools": ElevenLabs asks the device (robot bridge,
text chat, or the laptop demo page) to run them. This keeps answers fast and
deterministic, and the robot never depends on a second internet hop for directions.

Tools
  lookup_place         deterministic place directory (no network)
  check_in_visitor     tells reception a visitor arrived   -> web app /api/check-in
  send_route_to_phone  shows a route QR on the screen      -> web app /api/send-route
  request_operator     calls a human at reception          -> web app /api/operator

Profiles with a "floor" map (blind navigation) get NAV_TOOL_SPECS instead: the route planner in
navigator.py, plus request_human. The live route is shown on the screen -> web app /api/nav
"""

import json
import queue
import threading
import urllib.error
import urllib.request

from .directory import Directory
from .profile import text_for

# Tool definitions sent to ElevenLabs (parameters are JSON schema).
TOOL_SPECS = [
    {
        "name": "lookup_place",
        "description": "Find a place and get exact directions from the robot. ALWAYS call this before giving any "
                       "location, directions, floor or opening hours. Call it once per destination.",
        "parameters": {
            "query": "What the visitor is looking for, in their words, e.g. 'bank', 'Oraseya Capital', 'مصلى'.",
            "language": "The visitor's language: ar or en.",
            "place_id": "Optional. A place_id from a previous lookup_place answer, after the visitor chose an option.",
        },
        "required": ["query", "language"],
        "action": None,
    },
    {
        "name": "check_in_visitor",
        "description": "Tell the host company that the visitor has arrived. Use only after the visitor agrees.",
        "parameters": {
            "host_company": "The company the visitor is meeting, e.g. Oraseya Capital.",
            "visitor_name": "The visitor's first name as they said it. Use Guest if they don't want to say.",
            "meeting_time": "The meeting time as the visitor said it, 24-hour form, e.g. 15:00. Empty if unknown.",
            "language": "ar or en.",
        },
        "required": ["host_company", "language"],
        "action": "check_in",
    },
    {
        "name": "send_route_to_phone",
        "description": "Show the route to a place as a QR code on the screen next to the robot, so the visitor can "
                       "open it on their phone. Use only after the visitor agrees.",
        "parameters": {
            "place_id": "The place_id from lookup_place.",
            "language": "ar or en.",
        },
        "required": ["place_id", "language"],
        "action": "send_route",
    },
    {
        "name": "request_operator",
        "description": "Call a human operator at reception. Use when the visitor asks for a person, is upset, "
                       "disputes something, or needs help you cannot give.",
        "parameters": {
            "reason": "One short sentence: why a person is needed.",
            "language": "ar or en.",
            "visitor_name": "The visitor's first name if known, else empty.",
        },
        "required": ["reason", "language"],
        "action": "operator",
    },
]


_PLACE_LANG = "Language code of the person asking, e.g. ar, en, hi."

# "config" is merged into the ElevenLabs tool settings.
NAV_TOOL_SPECS = [
    {
        "name": "find_place",
        "description": "Understand which place on this floor someone wants. ALWAYS call this first for a new request. "
                       "It does not start walking.",
        "parameters": {"query": "What they asked for, in their own words and language.", "language": _PLACE_LANG},
        "required": ["query", "language"],
        "action": None,
    },
    {
        "name": "start_route",
        "description": "Start guiding to a place, or change the destination on the way. Call it when the place is clear.",
        "parameters": {
            "place_id": "The place_id from find_place.",
            "language": "Language code of the person who asked for THIS place, e.g. ar, en, hi.",
            "last_passed": "Only after start_route answered need_position: the last_passed id the operator named. Else empty.",
            "same_person": "yes if the visitor who is being guided changed their own mind. no if another person asks.",
            "start_at": "Where they say they or the robot are NOW, in their words, e.g. main junction. Empty if nobody said it.",
        },
        "required": ["place_id", "language"],
        "action": None,
        "config": {"pre_tool_speech": "off"},
    },
    {
        "name": "step_done",
        "description": "The OPERATOR says the current step is finished (done, okay, I'm there, reached). Returns the next step.",
        "parameters": {"step": "The step number of the instruction that was finished, e.g. 2."},
        "required": ["step"],
        "action": None,
        "config": {"pre_tool_speech": "off"},
    },
    {
        "name": "update_position",
        "description": "Someone says where the robot is now, during a trip or before they said where to go. Replans from there.",
        "parameters": {
            "at": "The place right next to the robot, in their words, e.g. kitchen.",
            "facing": "The place the robot is facing, if they said it. Else empty.",
        },
        "required": ["at"],
        "action": None,
        "config": {"pre_tool_speech": "off"},
    },
    {
        "name": "route_status",
        "description": "Get the current step again, e.g. when the operator did not hear it or anyone asks what is happening.",
        "parameters": {}, "required": [], "action": None, "config": {"pre_tool_speech": "off"},
    },
    {
        "name": "cancel_route",
        "description": "Stop guiding, because the visitor no longer wants to go.",
        "parameters": {}, "required": [], "action": None, "config": {"pre_tool_speech": "off"},
    },
    {
        "name": "request_human",
        "description": "Alert an organiser on the screen. Use when someone asks for a person, is upset, or needs help you cannot give.",
        "parameters": {"reason": "One short sentence: why a person is needed.", "language": _PLACE_LANG},
        "required": ["reason", "language"],
        "action": "operator",
    },
]


def enabled_tools(profile):
    actions = profile.get("actions", {})
    if profile.get("floor"):
        return [t for t in NAV_TOOL_SPECS if t["action"] is None or actions.get(t["action"])]
    return [t for t in TOOL_SPECS if t["action"] is None or actions.get(t["action"])]


class ToolRouter:
    """Runs a tool call and returns (result_text, is_error)."""

    def __init__(self, profile, webapp_url="", tool_secret="", log=print):
        self.profile = profile
        self.directory = Directory(profile)
        self.webapp_url = (webapp_url or "").rstrip("/")
        self.tool_secret = tool_secret or ""
        self.log = log
        self.nav = None
        if profile.get("floor"):
            from .navigator import Navigator
            self.nav = Navigator(profile)
            self._nav_lock = threading.RLock()
            self._nav_out = queue.Queue()
            threading.Thread(target=self._nav_sender, daemon=True).start()
            self._show()

    def handle(self, name, params):
        params = params or {}
        if self.nav:
            return self._handle_nav(name, params)
        try:
            fn = {
                "lookup_place": self._lookup,
                "check_in_visitor": self._check_in,
                "send_route_to_phone": self._send_route,
                "request_operator": self._operator,
            }.get(name)
            if not fn:
                return json.dumps({"ok": False, "message": f"Unknown tool {name}"}), True
            out = fn(params)
            return json.dumps(out, ensure_ascii=False), not out.get("ok", True)
        except Exception as e:  # never leave the agent waiting
            self.log(f"tool {name} failed: {e}")
            return json.dumps({"ok": False, "message": "That didn't work. Send the visitor to reception."}), True

    # ---------------------------------------------------------------- blind navigation
    def _handle_nav(self, name, p):
        nav = self.nav
        try:
            with self._nav_lock:
                if name == "find_place":
                    out = nav.find(p.get("query", ""), p.get("language", "en"))
                elif name == "start_route":
                    out = nav.start_route(p.get("place_id", ""), p.get("language", "en"), p.get("last_passed", ""),
                                          str(p.get("same_person", "")).lower() == "yes", p.get("start_at", ""))
                elif name == "step_done":
                    out = nav.step_done(p.get("step"))
                elif name == "update_position":
                    out = nav.update_position(p.get("at", ""), p.get("facing", ""))
                elif name == "route_status":
                    out = nav.status()
                elif name == "cancel_route":
                    out = nav.cancel()
                elif name == "request_human":
                    out = self._human(p)
                else:
                    return json.dumps({"status": "error", "say": f"Unknown tool {name}"}), True
                self._show(out)
            return json.dumps(out, ensure_ascii=False), False
        except Exception as e:  # never leave the agent (and the operator) waiting
            self.log(f"tool {name} failed: {e}")
            return json.dumps({"status": "error", "say_operator": "Operator: stop, please.",
                               "say": "Something failed. Say this, then call request_human."}), True

    def marker(self, node_id):
        """The camera sees one of our printed markers. Returns the tool-style result, or None if it changes nothing."""
        with self._nav_lock:
            if node_id not in self.nav.nodes or (self.nav.at == node_id and self.nav.source == "marker"):
                return None
            out = self.nav.update_position(node_id, source="marker")
            self._show(out)
            return out

    def _human(self, p):
        op = self.profile["operator"]
        body = {"reason": p.get("reason", ""), "visitor_name": "", "language": p.get("language", "en")}
        sent = self._post("/api/operator", body, offline_message="").get("alerted")
        return {"status": "ok", "alerted": bool(sent),
                "say": ("An organiser has been alerted on the screen. " if sent else "The screen is offline, nobody was alerted. ")
                       + f"Tell the visitor: for a person, {text_for(op['where'], 'en')}. The operator stays stopped."}

    def _show(self, last=None):
        """Send the live route to the screen without holding up the conversation."""
        self._nav_out.put({**self.nav.snapshot(),
                           "say_operator": (last or {}).get("say_operator", ""),
                           "say_visitor": (last or {}).get("say_visitor", ""),
                           "status": (last or {}).get("status", "")})

    def _nav_sender(self):
        while True:
            body = self._nav_out.get()
            if self.webapp_url:
                self._post("/api/nav", body, offline_message="")

    # ---------------------------------------------------------------- tools
    def _lookup(self, p):
        out = self.directory.lookup(p.get("query", ""), p.get("language", "en"), p.get("place_id", ""))
        out["ok"] = True
        return out

    def _check_in(self, p):
        body = {
            "visitor_name": p.get("visitor_name") or "Guest",
            "host_company": p.get("host_company", ""),
            "meeting_time": p.get("meeting_time", ""),
            "language": p.get("language", "en"),
        }
        return self._post("/api/check-in", body, offline_message=self._offline(p))

    def _send_route(self, p):
        lang = "ar" if str(p.get("language", "")).startswith("ar") else "en"
        place = self.directory.places.get(p.get("place_id", ""))
        if not place:
            return {"ok": False, "message": "Unknown place_id. Call lookup_place first."}
        found = self.directory.lookup(place_id=place["id"], language=lang)
        steps = found["steps"] or [found["where"]]
        body = {
            "destination": found["name"] + (f" · {found['where']}" if found["where"] else ""),
            "steps": " | ".join(steps),
            "language": lang,
            "maps_query": found.get("maps_query", ""),
        }
        return self._post("/api/send-route", body, offline_message=self._offline(p))

    def _operator(self, p):
        lang = "ar" if str(p.get("language", "")).startswith("ar") else "en"
        op = self.profile["operator"]
        where = f"{text_for(op['name'], lang)}, {text_for(op['where'], lang)}"
        body = {"reason": p.get("reason", ""), "visitor_name": p.get("visitor_name", ""), "language": lang}
        out = self._post("/api/operator", body, offline_message="")
        out["ok"] = True  # the visitor can always walk to the desk
        out["operator_location"] = where
        out["say"] = ("A colleague at reception has been alerted. " if out.get("alerted") else "") + \
                     "Tell the visitor kindly where the reception desk is, in one sentence."
        return out

    # ---------------------------------------------------------------- http
    def _offline(self, p):
        lang = "ar" if str(p.get("language", "")).startswith("ar") else "en"
        op = self.profile["operator"]
        return ("The reception screen is offline. Apologise and send the visitor to "
                f"{text_for(op['name'], lang)}, {text_for(op['where'], lang)}.")

    def _post(self, path, body, offline_message):
        if not self.webapp_url:
            self.log(f"(no WEBAPP_URL) would POST {path} {body}")
            return {"ok": bool(not offline_message), "alerted": False, "message": offline_message or "No screen."}
        req = urllib.request.Request(
            self.webapp_url + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"content-type": "application/json",
                     **({"x-tool-secret": self.tool_secret} if self.tool_secret else {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                out = json.loads(r.read() or b"{}")
                out.setdefault("ok", True)
                out["alerted"] = True
                return out
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            self.log(f"POST {path} failed: {e}")
            return {"ok": False, "alerted": False, "message": offline_message or "Screen unreachable."}
