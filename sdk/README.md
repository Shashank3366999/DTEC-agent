# Oasis Voice SDK

Turns a **data file** into a voice reception bot on ElevenLabs Agents, and runs it on the AgiBot X2 robot.

```
profile (JSON data) ──build──▶ ElevenLabs agent (prompt, voice, Arabic + English, 4 tools)
                     ──bridge─▶ robot: mic ⇄ noise gate ⇄ agent ⇄ speaker, tools run on the robot
                     ──export─▶ webapp/public/profile.json (the laptop demo runs the same tools)
```

## What it does (the team's checklist)

| Goal | How |
|---|---|
| **Deterministic layer** | Places, routes and opening hours come from the profile through `lookup_place`, never from the AI's memory. Same question → same answer. The AI only phrases it. |
| **Query clarification** | If a request matches several places ("mosque", "coffee", "pray"), `lookup_place` returns the options and the agent asks one short question. |
| **Context beyond what was asked** | The agent knows the local time (`{{system__time}}`), where it stands, today's event, and whether a place is open now. It remembers the visitor's name and meeting, and adds one useful next step (check-in, route to phone, "closed now"). |
| **Noise filtering** | On the robot, a noise gate learns the background level and only passes speech. Place names are added as speech-to-text keywords so they are heard correctly. |
| **Arabic and English** | Both built in, with Arabic names and Arabic directions in the data. The agent switches language mid-conversation. Arabic spelling variants and misheard names still match. |
| **Guide to an operator** | `request_operator` alerts reception (orange banner on the screen) and tells the visitor where the desk is. |
| **Latency** | Tools run on the device (no extra internet hop), short answers, no knowledge-base search. The bridge logs the delay after every reply. |
| **Many bots from data** | A new bot = a new profile. `profiles/startup_office.json` is a startup front desk made with zero code changes. |

## Files

| Path | What |
|---|---|
| `profiles/dtec_navigator.json` | **Our bot.** All facts, places, Arabic + English directions. Edit this to change what the robot knows. |
| `profiles/startup_office.json` | A second example bot (demo data) |
| `oasis_voice/directory.py` | Deterministic place matching and directions |
| `oasis_voice/actions.py` | The 4 tools: lookup_place, check_in_visitor, send_route_to_phone, request_operator |
| `oasis_voice/prompt.py` | Builds the agent's instructions from the profile |
| `oasis_voice/builder.py` | Creates/updates the ElevenLabs agent |
| `oasis_voice/bridge.py` | Robot bridge (organisers' bridge + noise gate + tools + latency) |
| `oasis_voice/chat.py` | Text chat with the agent for testing (no mic needed) |
| `state/dtec_navigator.json` | Our agent ID and tool IDs (not secret) |
| `TEST_CONVERSATIONS.md`, `SOURCES.md` | Test list and where the facts come from |

Our agent ID: **`agent_4001m86cac97egtb840g9whcrbz3`**

## Commands (run inside the `sdk` folder)

```bash
python3 -m oasis_voice validate                    # check the profile
python3 -m oasis_voice ask "where is the bank"     # test the directory, offline
python3 -m oasis_voice ask "وين المصعد" --lang ar
python3 -m oasis_voice prompt                      # see the agent's instructions
python3 -m oasis_voice build                       # update the ElevenLabs agent (needs the key in .env)
python3 -m oasis_voice chat                        # type to the agent; tools run locally
python3 -m oasis_voice chat --say "Where can I pray?"
python3 -m unittest discover -s tests              # 22 tests, no network
```

`chat` and `bridge` need `pip3 install websocket-client`. Every command takes `--profile path/to/profile.json`.

Settings go in `.env` in the repo root (copy `.env.example`): `ELEVENLABS_API_KEY` (only for `build`), `WEBAPP_URL` and `TOOL_SECRET` (so tools can reach the reception screen).

## On the robot (PC2, inside the container)

```bash
pip3 install websocket-client numpy
source /opt/ros/humble/setup.bash && source <aimdk path>/install/setup.bash
cd DTEC-agent/sdk
export WEBAPP_URL=<reception screen web app URL>     # e.g. https://dtec-agent.onrender.com
python3 -m oasis_voice bridge
```

No API key is needed on the robot (the agent is public). Options: `HALF_DUPLEX=1` (robot interrupts itself), `MIC_STREAM=2` (external mic), `NOISE_MIN_RMS=600` (very loud room), `NOISE_GATE=0` (gate off), `VERBOSE=1`.

You will see lines like:
```
visitor: Where is the bank?
tool lookup_place {"query": "bank", "language": "en"} -> {"status": "found", ...} (1 ms)
robot: Emirates NBD is on the first floor of Silicon Central Mall…
latency 0.94s  (3 replies, median 0.98s, worst 1.31s)
```

If the SDK cannot run for any reason, the organisers' original bridge (`robot/elevenlabs_robot_bridge.py`) still works with the same agent ID. The tools then won't run, so the agent will say it can't look places up.

## Change what the robot knows

1. Edit `profiles/dtec_navigator.json` (e.g. replace a demo route with the real one walked on site, and remove `"demo": true`).
2. `python3 -m oasis_voice validate` → `python3 -m oasis_voice ask "<place>"` to check.
3. `python3 -m oasis_voice build`. The robot uses the new data from its next conversation. The robot itself needs the updated file too (pull the repo) because directions are looked up on the device.

## Make a new bot

Copy a profile, change `bot.id`, the greeting, operator and places, then `python3 -m oasis_voice build --profile profiles/<new>.json`. It creates a new agent and prints its ID.
