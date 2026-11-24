# DSO Visitor Guide: robot quick start

This folder is everything the robot needs. The voice, Arabic + English, and all the facts live in the ElevenLabs agent and in `profiles/dtec_navigator.json`. The robot only runs the bridge.

Agent ID: `agent_4001m86cac97egtb840g9whcrbz3` (already inside `state/`).

## 1. Copy it to the robot

Copy this whole folder to PC2, inside the container, under `/home/agi/` (never into `aimdk*`, never on PC1).

## 2. Install (once)

```bash
pip3 install websocket-client numpy
```

## 3. Settings (once)

```bash
cd /home/agi/oasis_voice_robot
cp config.env.example config.env
nano config.env      # fill in AIMDK_PATH (from the MangoBot engineer) and WEBAPP_URL (from the team)
chmod +x run_robot.sh
```

## 4. Check everything

```bash
./run_robot.sh doctor
```
Every line should say **OK**. Each **FIX** line says what to do.

## 5. Run

```bash
./run_robot.sh
```
Say the robot's wake word once, then talk normally. Stop with Ctrl+C.

Good output:
```
speaker focus: yes
connected. agent speaks pcm_16000 and listens to pcm_16000
visitor: Where is the bank?
tool lookup_place {"query": "bank", ...} -> {"status": "found", ...}
robot: Emirates NBD is on the first floor of Silicon Central Mall…
latency 0.94s
```

## If something goes wrong

| What you see | Fix (in config.env, then run again) |
|---|---|
| The robot interrupts itself | `HALF_DUPLEX=1` |
| Background chatter gets picked up | `NOISE_MIN_RMS=600` |
| Quiet visitors are not heard | `NOISE_MIN_RMS=200` or `NOISE_GATE=0` |
| It can't hear in the noisy room | ask for the external mic, then `MIC_STREAM=2` |
| `cannot reach ElevenLabs` | no internet in the container: tell the MangoBot engineer |
| `speaker focus: NO` | ask the MangoBot engineer to check the agent module |
| `screen is offline` | `WEBAPP_URL` / `TOOL_SECRET` wrong, or open the URL in a browser to wake it |
| The SDK won't start at all | fallback: `cd original_bridge && ELEVENLABS_AGENT_ID=agent_4001m86cac97egtb840g9whcrbz3 python3 elevenlabs_robot_bridge.py` (talks, but no place lookup or actions) |

## Robot rules (MangoBot / AgiBot)

Code only in the container on PC2, never on PC1. Don't touch the OS, drivers, DDS, firmware, power or hardware. Save only under `/home/agi`. We never move the robot. If anything looks wrong, stop and call the MangoBot engineer.

## Updating the directions

When the team sends a new `dtec_navigator.json`, replace `profiles/dtec_navigator.json` with it and run `./run_robot.sh` again. Directions are looked up on the robot, so this file must be up to date.
