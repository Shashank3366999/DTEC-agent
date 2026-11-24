"""Create or update an ElevenLabs agent from a profile.

State (agent ID, tool IDs) is kept in sdk/state/<bot id>.json, so running the
build again updates the SAME agent: the agent ID given to the robot never changes.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request

from .actions import enabled_tools
from .directory import Directory
from .prompt import build_prompt, first_messages

API = "https://api.elevenlabs.io"
SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(SDK_DIR, "state")
WEB_PUBLIC = os.path.join(os.path.dirname(SDK_DIR), "webapp", "public")

# Defaults (override in the profile under "voice").
# Voice model: ElevenLabs' default is used unless the profile sets "tts_model". Note: an agent whose
# default language is English only accepts English-capable fast models (ElevenLabs validates this).
DEFAULT_TURN_EAGERNESS = "normal"         # "patient" waits longer in noisy rooms, "eager" answers faster


class BuildError(RuntimeError):
    pass


class ElevenLabs:
    def __init__(self, api_key, dry_run=False, log=print):
        self.key = api_key
        self.dry = dry_run
        self.log = log

    def call(self, method, path, body=None):
        if self.dry:
            self.log(f"--- {method} {path}")
            self.log(json.dumps(body, ensure_ascii=False, indent=2)[:1500])
            return {"id": "DRY_TOOL", "agent_id": "DRY_AGENT"}
        req = urllib.request.Request(
            API + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"xi-api-key": self.key, "content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise BuildError(f"ElevenLabs said {e.code} for {method} {path}: "
                             f"{e.read().decode('utf-8', 'replace')[:1500]}") from e
        except urllib.error.URLError as e:
            raise BuildError(f"Could not reach ElevenLabs: {e.reason}") from e


def _tool_body(spec):
    return {
        "tool_config": {
            "type": "client",
            "name": spec["name"],
            "description": spec["description"],
            "expects_response": True,
            "response_timeout_secs": 10,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string", "description": d} for k, d in spec["parameters"].items()},
                "required": spec["required"],
            },
        }
    }


def _hash(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def load_state(bot_id):
    path = os.path.join(STATE_DIR, f"{bot_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(bot_id, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, f"{bot_id}.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def agent_body(profile, tool_ids):
    voice = profile.get("voice", {})
    en_first, other_firsts = first_messages(profile)
    directory = Directory(profile)
    keywords = list(dict.fromkeys(profile.get("asr_keywords", []) + directory.all_names()))[:100]
    tts = {"agent_output_audio_format": "pcm_16000"}
    if voice.get("tts_model"):
        tts["model_id"] = voice["tts_model"]
    if voice.get("voice_id"):
        tts["voice_id"] = voice["voice_id"]
    prompt = {
        "prompt": build_prompt(profile),
        "tool_ids": tool_ids,
        "knowledge_base": [],          # places come from lookup_place, not from fuzzy search
        "timezone": profile["bot"].get("timezone", "UTC"),
        "built_in_tools": {
            "language_detection": {
                "type": "system", "name": "language_detection", "description": "",
                "params": {"system_tool_type": "language_detection"},
            }
        },
    }
    if voice.get("llm"):
        prompt["llm"] = voice["llm"]
    return {
        "name": f"{profile['bot']['name']} ({profile['bot']['id']})",
        "conversation_config": {
            "agent": {"first_message": en_first, "language": profile["languages"]["default"], "prompt": prompt},
            "language_presets": {lang: {"overrides": {"agent": {"first_message": msg}}}
                                 for lang, msg in other_firsts.items()},
            "tts": tts,
            "asr": {"user_input_audio_format": "pcm_16000", "keywords": keywords},
            "turn": {"turn_eagerness": voice.get("turn_eagerness", DEFAULT_TURN_EAGERNESS)},
        },
        "platform_settings": {"auth": {"enable_auth": False}},
    }


def build(profile, api_key, dry_run=False, new=False, log=print):
    api = ElevenLabs(api_key, dry_run, log)
    bot_id = profile["bot"]["id"]
    state = {} if new else load_state(bot_id)
    tools_state = state.get("tools", {})

    tool_ids = []
    for spec in enabled_tools(profile):
        body = _tool_body(spec)
        h = _hash(body)
        saved = tools_state.get(spec["name"])
        if saved and saved.get("hash") == h:
            tool_ids.append(saved["id"])
            continue
        log(f"Creating tool {spec['name']}…")
        out = api.call("POST", "/v1/convai/tools", body)
        tools_state[spec["name"]] = {"id": out["id"], "hash": h}
        tool_ids.append(out["id"])
        if not dry_run:  # remember new tools even if the agent update below fails
            save_state(bot_id, {**state, "tools": tools_state})

    body = agent_body(profile, tool_ids)
    if state.get("agent_id"):
        log(f"Updating agent {state['agent_id']}…")
        api.call("PATCH", f"/v1/convai/agents/{state['agent_id']}", body)
        agent_id = state["agent_id"]
    else:
        log("Creating agent…")
        agent_id = api.call("POST", "/v1/convai/agents/create", body)["agent_id"]

    if not dry_run:
        save_state(bot_id, {"agent_id": agent_id, "tools": tools_state})
        export_for_web(profile, agent_id)
    return agent_id


def export_for_web(profile, agent_id):
    """Copy the profile to the web app so the laptop demo page runs the same tools."""
    if not os.path.isdir(WEB_PUBLIC):
        return
    clean = {k: v for k, v in profile.items() if not k.startswith("_")}
    clean["agent_id"] = agent_id
    with open(os.path.join(WEB_PUBLIC, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
