# Handover: Team Hercules, AI Voice Navigator

For the teammate taking over on Tuesday 24 Nov, from 18:00 (Dubai time). Everything you need is in this repo; nothing depends on the previous person's laptop.

## In one minute

- We make the **voice and brain** of Humanoid Robot A: a guide in the Dtec lobby that answers visitors in **Arabic and English**.
- The brain is an **ElevenLabs agent**: `agent_4001m86cac97egtb840g9whcrbz3` (public; the robot only needs this ID).
- What it knows comes from **one data file**: `sdk/profiles/dtec_navigator.json`. Nothing is "trained": we configure the agent and the data, then run `build`.
- The robot runs our **SDK bridge**, shipped as one zip: `dist/oasis_voice_robot.zip` (rebuild with `python3 robot/make_package.py`).
- The **web app** shows check-ins, route QR codes and operator alerts on a screen next to the robot.

## Deadlines

| When (Dubai) | What |
|---|---|
| **Tue 19:00** | Robot test round 1 (our slot 3): first run of the SDK on the robot |
| Tue 20:00–22:00 | Organisers visit teams: show the demo |
| **Wed 06:30** | Robot round 2: **film the demo** (one unedited take, max 2 min) |
| **Wed 08:30** | **Submission closes** (aim for 08:00): link, 100 words, video, ≤3 slides, robot take |
| **Wed 09:20** | Our pitch: 3 min talk, 2 min demo, 2 min questions |

## Done ✅

| Item | Where | Checked how |
|---|---|---|
| ElevenLabs agent: English + Arabic, language switching, PCM 16000 audio for the robot, place names as speech keywords, 4 tools | built by `sdk` | read back from ElevenLabs; live text conversation worked |
| Deterministic directions: 23 places with Arabic + English names and routes, clarifying questions, "open now", tips | `sdk/oasis_voice/directory.py`, profile | 22 unit tests; 22 sample questions |
| Tools: `lookup_place`, `check_in_visitor`, `send_route_to_phone`, `request_operator` (run on the robot / in the browser) | `sdk/oasis_voice/actions.py`, `webapp/public/oasis.js` | browser and Python give identical answers on 22 questions |
| Robot bridge = organisers' bridge + noise gate + tools + latency log | `sdk/oasis_voice/bridge.py` | **not yet run on the robot** (no ROS on laptops) |
| Robot package with `run_robot.sh`, `config.env`, health check (`doctor`), fallback to the original bridge | `dist/oasis_voice_robot.zip` | unzipped fresh and ran `doctor` on a laptop |
| Web app: reception screen, phone route page, operator alert, laptop demo `/kiosk`, test panel `/test` | `webapp/` | 13 automated checks |
| Second example bot from data only (startup front desk) | `sdk/profiles/startup_office.json` | validated |
| Pitch material: demo script, 99-word description, 3-slide outline, pitch talk, Q&A | `pitch/` | drafts |
| On-site guides: what to collect in the building, robot checklist | `onsite/`, `robot/ROBOT_CHECKLIST.md` | |

## To do, in order

### Remote (you)

1. **Put the web app online (15 min, do before 19:00).** render.com → New Web Service → repo `DTEC-agent` → Root `webapp` → Start `node server.js` → env `TOOL_SECRET=<long word>` → after it is Live add `PUBLIC_URL=<its URL>`. Check `<URL>/health`. Steps: [WALKTHROUGH.md](WALKTHROUGH.md) Part 3.
2. **Send the on-site teammate:** `dist/oasis_voice_robot.zip`, the Render URL and the secret word. They follow `QUICKSTART.md` inside the zip.
3. **Voice test on a laptop:** `cd webapp && node server.js`, open `http://localhost:3000/kiosk`, run the demo script in [pitch/demo_script.md](pitch/demo_script.md). Fix wrong answers in the profile, then `cd sdk && python3 -m oasis_voice build`.
4. **Real directions:** when photos/voice notes arrive from the building, update each place in `sdk/profiles/dtec_navigator.json` (English + Arabic steps, `walk_minutes`, remove `"demo": true`). Then `validate` → `ask "<place>"` → `build` → `python3 robot/make_package.py` → send the new zip (or just the new profile JSON) to the robot.
5. **Arabic check:** an Arabic speaker listens to the greeting and a few answers. If the voice sounds bad, add `"voice": {"voice_id": "<better voice>"}` to the profile and `build`.
6. **Backup demo video:** screen-record `/kiosk` (with sound) running the demo script.
7. **Slides:** 3 slides from [pitch/slides_and_pitch.md](pitch/slides_and_pitch.md), plus a photo of the robot/lobby from the venue.
8. **Submit by Wed 08:00:** make the GitHub repo public just before, then fill in the form ([pitch/submission.md](pitch/submission.md)).

### On site

1. **Robot round 1 (Tue 19:00):** copy the zip to `/home/agi/` on PC2 → `./run_robot.sh doctor` → `./run_robot.sh`. Ask for the wake word, the robot's standing spot, the external mic and the AimDK path. Keep a video call open with the remote teammate.
2. **Walk the building** from the robot's spot and send directions ([onsite/COLLECT_DIRECTIONS.md](onsite/COLLECT_DIRECTIONS.md)).
3. **Ask the organisers** that remote teammates are fine.
4. **Wed 06:30:** reset the screen (`<URL>/test` → Reset), film one take with the robot **and** the screen in view.
5. **Wed 09:20:** pitch.

## Settings and secrets

- Copy `.env.example` to `.env` in the repo root. `ELEVENLABS_API_KEY` is needed only to run `build`; get it privately from the ElevenLabs account owner. Never commit it or paste it in chats/docs.
- The robot needs **no** API key: only `WEBAPP_URL` and `TOOL_SECRET` in its `config.env`.
- After the hackathon, the account owner should delete the API key that was shared during the day.

## Useful commands

```bash
cd sdk
python3 -m oasis_voice validate                       # check the data file
python3 -m oasis_voice ask "where can I pray"         # test directions offline
python3 -m oasis_voice ask "وين المصعد" --lang ar
python3 -m oasis_voice chat --say "Where is the bank?"   # talk to the live agent by text (pip3 install websocket-client)
python3 -m oasis_voice build                          # push data/prompt changes to the agent (same ID)
python3 -m unittest discover -s tests                 # 22 tests
cd ../webapp && npm test && node test/parity.mjs      # web app checks
cd .. && python3 robot/make_package.py                # rebuild dist/oasis_voice_robot.zip
```

## Known limits and risks

- **The SDK bridge has not run on the real robot yet.** Its ROS part is the organisers' code unchanged. If it fails, the zip has the original bridge as a fallback (it talks, but without place lookup and actions).
- **The ElevenLabs dashboard "Test" button can't run our tools.** Use `/kiosk` or `oasis_voice chat` to test.
- **Inside-building directions are demo data** until the real walk is added.
- **Free Render sleeps** when unused (about a minute to wake). Open `<URL>/screen` before each robot slot.
- **Robot data comes from the zip:** after changing directions, the robot needs the new profile file too.
- The ElevenLabs account has 4 unused tools from an earlier failed build; harmless, delete if you like.
