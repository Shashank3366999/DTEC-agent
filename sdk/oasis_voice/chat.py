"""Text chat with the agent from a terminal, with the client tools running locally.

Use it to test the whole agent (prompt + tools + data) without a robot or a mic:
  python3 -m oasis_voice chat
  python3 -m oasis_voice chat --say "Where is the bank?" --say "Emirates NBD please"
The agent still produces audio; this tool ignores it and prints the text.
"""

import json
import queue
import threading
import time

import websocket  # pip3 install websocket-client

URL = "wss://api.elevenlabs.io/v1/convai/conversation?agent_id="


class Chat:
    def __init__(self, agent_id, router, show_tools=True, out=print):
        self.router = router
        self.show_tools = show_tools
        self.out = out
        self.events = queue.Queue()
        self.ws = websocket.create_connection(URL + agent_id, timeout=20)
        self.ws.send(json.dumps({"type": "conversation_initiation_client_data"}))
        self.alive = True
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while self.alive:
            try:
                raw = self.ws.recv()
            except Exception:
                self.alive = False
                self.events.put({"type": "_closed"})
                return
            if raw:
                self.events.put(json.loads(raw))

    def _send(self, obj):
        self.ws.send(json.dumps(obj))

    def wait_reply(self, quiet_s=3.0, max_s=40.0):
        """Handle events until the agent has finished replying. Returns the agent's text lines."""
        lines = []
        start = time.monotonic()
        last = time.monotonic()
        pending_tools = 0
        while time.monotonic() - start < max_s:
            try:
                ev = self.events.get(timeout=0.2)
            except queue.Empty:
                if lines and not pending_tools and time.monotonic() - last > quiet_s:
                    break
                continue
            t = ev.get("type")
            if t == "ping":
                self._send({"type": "pong", "event_id": ev["ping_event"]["event_id"]})
            elif t == "agent_response":
                text = ev["agent_response_event"]["agent_response"]
                lines.append(text)
                self.out(f"  robot: {text}")
                last = time.monotonic()
            elif t == "client_tool_call":
                pending_tools += 1
                call = ev["client_tool_call"]
                result, is_error = self.router.handle(call.get("tool_name"), call.get("parameters") or {})
                if self.show_tools:
                    self.out(f"  [tool] {call.get('tool_name')} {json.dumps(call.get('parameters'), ensure_ascii=False)}")
                    self.out(f"         -> {result[:300]}")
                self._send({"type": "client_tool_result", "tool_call_id": call.get("tool_call_id"),
                            "result": result, "is_error": is_error})
                pending_tools -= 1
                last = time.monotonic()
            elif t == "_closed":
                self.out("  (conversation closed)")
                break
        return lines

    def say(self, text):
        self.out(f"visitor: {text}")
        self._send({"type": "user_message", "text": text})
        return self.wait_reply()

    def close(self):
        self.alive = False
        try:
            self.ws.close()
        except Exception:
            pass


def run(agent_id, router, says=None):
    chat = Chat(agent_id, router)
    chat.wait_reply(quiet_s=1.5, max_s=15)  # greeting
    try:
        if says:
            for s in says:
                chat.say(s)
        else:
            print("Type a message (empty line to quit).")
            while True:
                text = input("> ").strip()
                if not text:
                    break
                chat.say(text)
    finally:
        chat.close()
