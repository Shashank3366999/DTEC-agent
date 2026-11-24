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
            **spec.get("config", {}),
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


def agent_body(profile, tool_ids, state_extra=None, webhook_id=""):
    state_extra = state_extra or {}
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
    if voice.get("supported_voices"):  # e.g. [{"label": "Operator", "voice_id": "...", "language": "en"}]
        tts["supported_voices"] = voice["supported_voices"]
    if profile.get("floor"):
        tts["expressive_mode"] = False  # no "[happy]" tags: a calm voice that fits a robot
    asr = {"user_input_audio_format": "pcm_16000", "keywords": keywords}
    if voice.get("asr_provider"):
        asr["provider"] = voice["asr_provider"]
    turn = {"turn_eagerness": voice.get("turn_eagerness", DEFAULT_TURN_EAGERNESS)}
    if voice.get("interruption_ignore_terms"):  # "okay", "hmm" from a visitor must not cut the robot off
        turn["interruption_ignore_terms"] = voice["interruption_ignore_terms"]
    if "speculative_turn" in voice:
        turn["speculative_turn"] = bool(voice["speculative_turn"])
    soft = voice.get("soft_timeout", {})
    if soft:  # a filler while the model thinks, so a gap never feels broken
        turn["soft_timeout_config"] = {"timeout_seconds": 3.0, "message": soft.get("en", "One moment."), "use_llm_generated_message": False}
    if state_extra.get("pronunciation"):
        tts["pronunciation_dictionary_locators"] = [state_extra["pronunciation"]]
    platform = {"auth": {"enable_auth": False}}
    analysis = profile.get("analysis", {})
    if analysis.get("criteria"):  # ElevenLabs scores every conversation against these, visible in the dashboard
        platform["evaluation"] = {"criteria": [
            {"id": c["id"], "name": c["name"], "type": "prompt", "conversation_goal_prompt": c["prompt"]}
            for c in analysis["criteria"]]}
    if analysis.get("collect"):  # ...and extracts these fields from every conversation
        platform["data_collection"] = {k: {"type": v["type"], "description": v["description"]}
                                       for k, v in analysis["collect"].items()}
    if webhook_id:
        platform["workspace_overrides"] = {"webhooks": {"post_call_webhook_id": webhook_id, "events": ["transcript"]}}
    extra = {}
    if profile.get("floor"):
        # The operator and the visitor are two people: don't flip language on the operator's English "done".
        prompt["built_in_tools"]["language_detection"]["description"] = (
            "Call only when the VISITOR starts speaking another language. Never call it for the operator's "
            "short English reports such as 'done' or 'I'm there'.")
        turn["turn_timeout"] = 30  # quiet while walking is normal (the bridge also sends user_activity)
        extra["conversation"] = {"max_duration_seconds": 3600}
        # lets the bridge carry on mid-route after the network drops
        platform["overrides"] = {"conversation_config_override": {"agent": {"first_message": True}}}
    return {
        "name": f"{profile['bot']['name']} ({profile['bot']['id']})",
        "conversation_config": {
            "agent": {"first_message": en_first, "language": profile["languages"]["default"], "prompt": prompt},
            "language_presets": {lang: {"overrides": {"agent": {"first_message": msg}},
                                        **({"soft_timeout_translation": {"source_hash": "", "text": soft[lang]}}
                                           if soft.get(lang) and lang != "en" else {})}
                                 for lang, msg in other_firsts.items()},
            "tts": tts,
            "asr": asr,
            "turn": turn,
            **extra,
        },
        "platform_settings": platform,
    }


def build(profile, api_key, dry_run=False, new=False, log=print, webhook_url=""):
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

    extra = {}
    if profile.get("pronunciation"):
        rules = [{"string_to_replace": r["say"], "type": "alias", "alias": r["as"]} for r in profile["pronunciation"]]
        h = _hash(rules)
        saved = state.get("pronunciation", {})
        if saved.get("hash") == h:
            extra["pronunciation"] = saved["locator"]
        else:
            log("Creating pronunciation dictionary…")
            out = api.call("POST", "/v1/pronunciation-dictionaries/add-from-rules",
                           {"name": f"{bot_id} names", "rules": rules})
            extra["pronunciation"] = {"pronunciation_dictionary_id": out.get("id", "DRY"), "version_id": out.get("version_id", "DRY")}
            state["pronunciation"] = {"hash": h, "locator": extra["pronunciation"]}
    webhook_id = state.get("webhook", {}).get("id", "")
    if webhook_url:
        if state.get("webhook", {}).get("url") != webhook_url:
            log(f"Creating post-call webhook -> {webhook_url}")
            out = api.call("POST", "/v1/workspace/webhooks",
                           {"settings": {"auth_type": "hmac", "name": f"{bot_id} post-call", "webhook_url": webhook_url}})
            webhook_id = out.get("webhook_id", "DRY")
            state["webhook"] = {"id": webhook_id, "url": webhook_url}
            if out.get("webhook_secret"):
                log("\n  Webhook secret (put it in the web app as ELEVENLABS_WEBHOOK_SECRET, never in git):\n  "
                    + out["webhook_secret"] + "\n")
    body = agent_body(profile, tool_ids, extra, webhook_id)
    if state.get("agent_id"):
        log(f"Updating agent {state['agent_id']}…")
        api.call("PATCH", f"/v1/convai/agents/{state['agent_id']}", body)
        agent_id = state["agent_id"]
    else:
        log("Creating agent…")
        agent_id = api.call("POST", "/v1/convai/agents/create", body)["agent_id"]

    if not dry_run:
        save_state(bot_id, {**state, "agent_id": agent_id, "tools": tools_state})
        export_for_web(profile, agent_id)
    return agent_id


def export_for_web(profile, agent_id):
    """Copy the profile to the web app so the laptop demo page runs the same tools."""
    if not os.path.isdir(WEB_PUBLIC):
        return
    clean = {k: v for k, v in profile.items() if not k.startswith("_")}
    clean["agent_id"] = agent_id
    from .navigator import VISITOR_LINES
    clean["visitor_lines"] = VISITOR_LINES
    with open(os.path.join(WEB_PUBLIC, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
