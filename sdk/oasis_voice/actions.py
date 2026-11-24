"""On-device tool handlers.

The agent's tools are "client tools": ElevenLabs asks the device (robot bridge,
text chat, or the laptop demo page) to run them. This keeps answers fast and
deterministic, and the robot never depends on a second internet hop for directions.

Tools
  lookup_place         deterministic place directory (no network)
  check_in_visitor     tells reception a visitor arrived   -> web app /api/check-in
  send_route_to_phone  shows a route QR on the screen      -> web app /api/send-route
  request_operator     calls a human at reception          -> web app /api/operator
"""

import json
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


def enabled_tools(profile):
    actions = profile.get("actions", {})
    return [t for t in TOOL_SPECS if t["action"] is None or actions.get(t["action"])]


class ToolRouter:
    """Runs a tool call and returns (result_text, is_error)."""

    def __init__(self, profile, webapp_url="", tool_secret="", log=print):
        self.profile = profile
        self.directory = Directory(profile)
        self.webapp_url = (webapp_url or "").rstrip("/")
        self.tool_secret = tool_secret or ""
        self.log = log

    def handle(self, name, params):
        params = params or {}
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
