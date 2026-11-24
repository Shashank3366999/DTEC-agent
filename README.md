# Team Hercules: AI Voice Navigator

Voice of the Oasis Hackathon, Challenge 01 (Humanoid Robot A), **new brief: blind navigation** (Team Guide Update, 24 Nov).

A MangoBot operator walks the robot. They don't know where the visitor wants to go and don't speak the visitor's language. Our agent does: it understands the visitor (Arabic, English, Hindi), plans the route, talks the operator there in English one step at a time, calls the stop, and tells the visitor they have arrived. If someone changes the destination halfway, it plans again from where the robot stands.

```
Visitor (any language) ⇄ robot mic/speaker ⇄ bridge ⇄ ElevenLabs agent
                                               │           │ tools
Operator (English)     ⇄ same mic/speaker      └── navigator.py: map + position + next step (deterministic)
                                               └── web app: /live (operator's line, visitor's line, floor map)
```

ElevenLabs does more than talk here: a second voice for the operator, per-conversation scoring and data extraction, a post-call webhook that feeds a trip log, 9 agent tests in the dashboard, a pronunciation dictionary and fillers in 11 languages. The list is in [HANDOVER.md](HANDOVER.md).

The AI understands and translates. **It never invents the way**: every step comes from the planner, which only knows the floor map in `sdk/profiles/dtec_floor.json`.

## What's in this repo

| Folder | What it is |
|---|---|
| [`HANDOVER.md`](HANDOVER.md) | **Start here:** what is left to do, in order |
| [`sdk/`](sdk/README.md) | Floor map, route planner, tools, agent builder, robot bridge, tests |
| [`webapp/`](webapp/README.md) | `/live` screen, `/walk` phone test, `/markers` to print, `/kiosk` laptop demo |
| [`onsite/COLLECT_FLOOR_MAP.md`](onsite/COLLECT_FLOOR_MAP.md) | How to measure the real floor (about 20 minutes) |
| [`robot/`](robot/ROBOT_CHECKLIST.md) | Checklist at the robot; `make_package.py` builds the zip |
| [`pitch/`](pitch/) | Demo script for the three routes, pitch, submission text |

The earlier lobby guide (`profiles/dtec_navigator.json`, agent `agent_4001m86cac97egtb840g9whcrbz3`) still works: add `--profile profiles/dtec_navigator.json`. The new bot is a **separate agent**, so building it does not touch the old one.

## Quick start

```bash
cd sdk
python3 -m oasis_voice validate
python3 -m oasis_voice routes                      # every route, in the words the operator will hear
python3 -m oasis_voice walk "second booth" --lang ar   # play the operator by typing
python3 -m oasis_voice build                       # create/update the agent (ELEVENLABS_API_KEY in .env)
python3 -m unittest discover -s tests
cd ../webapp && npm test && node server.js         # then open /walk, /live, /kiosk
```

## Rules we follow

- Built on ElevenLabs Agents. **We never move the robot from code**; MangoBot does.
- Robot code runs only in the container on PC2 and only reads the camera.
- Layout data is marked demo until the real floor is measured. The API key never goes in this repo, a doc or a chat.
