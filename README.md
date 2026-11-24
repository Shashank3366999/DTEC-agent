# Team Hercules: AI Voice Navigator

Voice of the Oasis Hackathon, Challenge 01 (Humanoid Robot A).

A talking guide for the lobby robot at Dtec, Dubai Silicon Oasis. Visitors speak Arabic or English; the robot gives exact directions from our data, asks when a request is unclear, checks visitors in with their host, sends the route to their phone by QR code, and calls a human when needed.

```
Visitor ⇄ Robot mic/speaker ⇄ SDK bridge (noise gate, tools) ⇄ ElevenLabs agent
                                     │
                                     └──▶ web app: reception screen (check-ins, QR, operator alerts) + phone page
```

Agent ID: **`agent_4001m86cac97egtb840g9whcrbz3`** (public, English + Arabic, PCM 16000 for the robot).

## What's in this repo

| Folder | What it is |
|---|---|
| [`sdk/`](sdk/README.md) | **The Oasis Voice SDK.** Bot data (`profiles/`), deterministic directions, the 4 tools, agent builder, robot bridge, text chat tester, 22 tests |
| [`webapp/`](webapp/README.md) | Reception screen, phone route page, laptop demo (`/kiosk`), test panel (`/test`) |
| [`robot/`](robot/ROBOT_CHECKLIST.md) | Checklist for the person at the robot, and the organisers' original bridge as a fallback |
| [`onsite/`](onsite/COLLECT_DIRECTIONS.md) | What to collect inside Dtec, and a message for the on-site teammate |
| [`pitch/`](pitch/) | Demo script, 100-word description, 3 slides, pitch talk, likely questions |
| [`WALKTHROUGH.md`](WALKTHROUGH.md) | Every step from zero to demo, in order |

## Quick start

```bash
# Laptop demo (works fully offline from Render: tools run in the browser)
cd webapp && node server.js
# open http://localhost:3000/kiosk   and press the call button

# Test the agent by typing (tools run locally)
cd sdk && pip3 install websocket-client && python3 -m oasis_voice chat

# After changing sdk/profiles/dtec_navigator.json
cd sdk && python3 -m oasis_voice build      # needs ELEVENLABS_API_KEY in .env
```

## Rules we follow

- The agent is built on ElevenLabs Agents. We never move the robot.
- Robot code runs only in the container on PC2. Don't touch the robot's system.
- Facts come from the challenge brief, public sources (`sdk/SOURCES.md`) or our own walk of the building. Anything made up is marked `"demo": true`.
- The ElevenLabs API key never goes in this repo, a doc or a chat.
