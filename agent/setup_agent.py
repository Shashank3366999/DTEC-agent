#!/usr/bin/env python3
"""
Build (or update) the DSO Visitor Guide agent on ElevenLabs from the files in this folder.

What it does
  1. Uploads knowledge_base.md to the ElevenLabs knowledge base.
  2. Creates the two webhook tools (check_in_visitor, send_route_to_phone) if WEBAPP_URL is set.
  3. Creates the agent (or updates it if agent_id.txt exists) with:
       - system prompt (system_prompt.md) and first message (first_message.md, English + Arabic)
       - English + Arabic, language detection tool
       - audio in and out as PCM 16000 Hz (what the robot needs)
       - public agent (no signed token), so the robot only needs the agent ID
  4. Saves the agent ID to agent_id.txt (the agent ID is not secret).

Settings come from hercules/.env (never commit that file, never paste the key in chat):
  ELEVENLABS_API_KEY=...        required
  WEBAPP_URL=https://...        optional, the public URL of our web app (no trailing slash)
  TOOL_SECRET=...               optional, same value as the web app's TOOL_SECRET
  VOICE_ID=...                  optional, an ElevenLabs voice that sounds good in Arabic and English
  TTS_MODEL_ID=...              optional, e.g. eleven_flash_v2_5 (default: ElevenLabs' default)
  LLM=...                       optional, e.g. gemini-2.5-flash (default: ElevenLabs' default)

Run:
  python3 hercules/agent/setup_agent.py            # create, or update if agent_id.txt exists
  python3 hercules/agent/setup_agent.py --new      # always create a new agent
  python3 hercules/agent/setup_agent.py --dry-run  # print what would be sent, call nothing
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
API = "https://api.elevenlabs.io"
AGENT_NAME = "DSO Visitor Guide (Team Hercules)"
ID_FILE = os.path.join(HERE, "agent_id.txt")


def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if k in ("ELEVENLABS_API_KEY", "WEBAPP_URL", "TOOL_SECRET", "VOICE_ID", "TTS_MODEL_ID", "LLM"):
            env[k] = v
    return env


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def first_messages():
    """English and Arabic first messages from first_message.md."""
    text = read("first_message.md")
    en = re.search(r"## English\s+(.+?)\n\s*\n", text, re.S)
    ar = re.search(r"## Arabic\s+(.+?)\n\s*\n", text, re.S)
    if not en or not ar:
        sys.exit("Could not find the English and Arabic first messages in first_message.md")
    return en.group(1).strip(), ar.group(1).strip()


class Api:
    def __init__(self, key, dry):
        self.key = key
        self.dry = dry

    def call(self, method, path, body=None):
        if self.dry:
            print(f"\n--- {method} {path}")
            print(json.dumps(body, ensure_ascii=False, indent=2)[:3000])
            return {"id": "DRY_RUN_ID", "agent_id": "DRY_RUN_AGENT"}
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={"xi-api-key": self.key, "content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:2000]
            sys.exit(f"\nElevenLabs said {e.code} for {method} {path}:\n{detail}")
        except urllib.error.URLError as e:
            sys.exit(f"\nCould not reach ElevenLabs: {e.reason}")


def webhook_tool(name, description, url, props, required, secret):
    headers = {"x-tool-secret": secret} if secret else {}
    return {
        "tool_config": {
            "type": "webhook",
            "name": name,
            "description": description,
            "response_timeout_secs": 10,
            "api_schema": {
                "url": url,
                "method": "POST",
                "content_type": "application/json",
                "request_headers": headers,
                "request_body_schema": {
                    "type": "object",
                    "properties": {k: {"type": "string", "description": d} for k, d in props.items()},
                    "required": required,
                },
            },
        }
    }


def main():
    dry = "--dry-run" in sys.argv
    force_new = "--new" in sys.argv
    env = load_env(os.path.join(ROOT, ".env"))
    key = env.get("ELEVENLABS_API_KEY", "")
    if not key and not dry:
        sys.exit("Put ELEVENLABS_API_KEY=... in hercules/.env first (never paste it in chat).")
    api = Api(key, dry)

    webapp = env.get("WEBAPP_URL", "").rstrip("/")
    secret = env.get("TOOL_SECRET", "")

    # 1. knowledge base
    print("Uploading knowledge base…")
    kb = api.call("POST", "/v1/convai/knowledge-base/text",
                  {"text": read("knowledge_base.md"), "name": "DSO Visitor Guide facts"})
    kb_ref = {"type": "text", "name": "DSO Visitor Guide facts", "id": kb["id"], "usage_mode": "auto"}

    # 2. tools (reused on later runs if the web app URL and secret did not change)
    tool_ids = []
    tools_file = os.path.join(HERE, "tool_ids.json")
    saved = {}
    if os.path.exists(tools_file):
        with open(tools_file, encoding="utf-8") as f:
            saved = json.load(f)
    if webapp and saved.get("webapp") == webapp and saved.get("secret_set") == bool(secret) and saved.get("ids"):
        print("Reusing the webhook tools made earlier…")
        tool_ids = saved["ids"]
    elif webapp:
        print("Creating webhook tools…")
        t1 = api.call("POST", "/v1/convai/tools", webhook_tool(
            "check_in_visitor",
            "Tell the host company that the visitor has arrived. Use only after the visitor agrees.",
            webapp + "/api/check-in",
            {
                "host_company": "The company the visitor is meeting, for example Oraseya Capital.",
                "visitor_name": "The visitor's first name as they said it. Use Guest if they don't want to say.",
                "meeting_time": "The meeting time as the visitor said it, 24-hour form, for example 15:00.",
                "language": "The language the visitor is speaking: ar or en.",
            },
            ["host_company", "language"], secret))
        t2 = api.call("POST", "/v1/convai/tools", webhook_tool(
            "send_route_to_phone",
            "Show a route card with a QR code on the screen next to the robot so the visitor can open "
            "the directions on their phone. Use only after the visitor agrees.",
            webapp + "/api/send-route",
            {
                "destination": "The place the visitor is going, for example Oraseya Capital, Dtec TechnoHub 1, first floor.",
                "steps": "The directions you just gave, as short steps separated by ' | ', in the visitor's language.",
                "language": "ar or en.",
                "maps_query": "Only for places outside Dtec: a Google Maps search text. Otherwise leave empty.",
            },
            ["destination", "steps", "language"], secret))
        tool_ids = [t1["id"], t2["id"]]
        if not dry:
            with open(tools_file, "w", encoding="utf-8") as f:
                json.dump({"webapp": webapp, "secret_set": bool(secret), "ids": tool_ids}, f)
    else:
        print("WEBAPP_URL not set: creating the agent WITHOUT the two tools. Run again once the web app is online.")

    # 3. agent
    en_first, ar_first = first_messages()
    tts = {"agent_output_audio_format": "pcm_16000"}
    if env.get("VOICE_ID"):
        tts["voice_id"] = env["VOICE_ID"]
    if env.get("TTS_MODEL_ID"):
        tts["model_id"] = env["TTS_MODEL_ID"]
    prompt = {
        "prompt": read("system_prompt.md"),
        "tool_ids": tool_ids,
        "knowledge_base": [kb_ref],
        "built_in_tools": {
            "language_detection": {
                "type": "system",
                "name": "language_detection",
                "description": "",
                "params": {"system_tool_type": "language_detection"},
            }
        },
    }
    if env.get("LLM"):
        prompt["llm"] = env["LLM"]
    body = {
        "name": AGENT_NAME,
        "conversation_config": {
            "agent": {"first_message": en_first, "language": "en", "prompt": prompt},
            "language_presets": {"ar": {"overrides": {"agent": {"first_message": ar_first}}}},
            "tts": tts,
            "asr": {"user_input_audio_format": "pcm_16000"},
        },
        "platform_settings": {"auth": {"enable_auth": False}},
    }

    existing = ""
    if os.path.exists(ID_FILE) and not force_new:
        existing = open(ID_FILE, encoding="utf-8").read().strip()

    if existing:
        print(f"Updating agent {existing}…")
        out = api.call("PATCH", f"/v1/convai/agents/{existing}", body)
        agent_id = out.get("agent_id", existing)
    else:
        print("Creating agent…")
        out = api.call("POST", "/v1/convai/agents/create", body)
        agent_id = out["agent_id"]

    if not dry:
        with open(ID_FILE, "w", encoding="utf-8") as f:
            f.write(agent_id + "\n")
    print(f"\nDone. Agent ID: {agent_id}")
    print("Test it: ElevenLabs dashboard → Agents → DSO Visitor Guide → Test, or open /kiosk?agent=<id> on the web app.")
    print("Send the agent ID to the person at the robot.")


if __name__ == "__main__":
    main()
