# Handover: Team Hercules, AI Voice Navigator (blind navigation)

The brief changed on 24 Nov. The code is ready for the new one. The agent is built: **`agent_8901m8739kh0fna9wssypk694eq8`**. The real floor map is still missing, and the demo needs it.

## Do these first

| # | What | Who | Time |
|---|---|---|---|
| 1 | **Measure the real floor.** The map in `sdk/profiles/dtec_floor.json` is a made-up layout. Follow [onsite/COLLECT_FLOOR_MAP.md](onsite/COLLECT_FLOOR_MAP.md) | on site | 20 min |
| 2 | **Rebuild after the map changes**: `cd sdk && python3 -m oasis_voice build` (needs `ELEVENLABS_API_KEY` in `.env`). Same agent, same ID | account owner | 1 min |
| 3 | **Test it by voice** with two people: one visitor, one operator ([sdk/TEST_CONVERSATIONS.md](sdk/TEST_CONVERSATIONS.md)) | everyone | 30 min |

Then: `python3 robot/make_package.py`, send `dist/oasis_voice_robot.zip` to the robot, put the web app online (below).

## What changed in the brief

- The robot walks, with a MangoBot operator at the controls. The agent guides that operator.
- Film **three routes**, up to **3 minutes** in total, cuts only between routes: easy, background music, change of destination (the organisers choose the music and the new destination).
- Visitor, robot **and operator** must be in the shot. At least two languages in every route.
- Pitch is 8 minutes: 3 pitch, 3 demo, 2 questions.
- **Teams are being reshuffled.** New team list, robot slots, submission deadline and pitch order come in the next update. Ignore the old times until then.

## Brief against what we built

| Must have | How |
|---|---|
| Two or three languages in every route | Place names in English, Arabic and Hindi. Greetings and key lines also in Spanish, French, German, Russian, Portuguese, Turkish, Chinese and Urdu; any other language is translated by the AI. Requests in a language without place names are always confirmed first |
| Translation between visitor and operator | Prompt rules; operator lines start with "Operator:" and are English |
| Directions step by step | `navigator.py`: one straight walk per step, landmark to stop at |
| Clarifying question | `find_place`: confirms vague requests, offers options, never guesses |
| Clear stop, arrival confirmed | `step_done` on the last step: stop line, then arrival in the visitor's language |
| New route when the destination changes | `start_route` mid-route; asks the operator one question only if the answer changes the route |
| Stretch: knows where it is without asking | Counts steps; printed QR markers + head camera (`sense.py`) |
| Stretch: camera confirms the arrival | Marker at the destination |
| Stretch: visitor switches language mid-route | Language detection, not triggered by the operator's English |

LiDAR is not used: on the X2 it needs a SLAM map and relocalisation set up with AgiBot support.

## Tested with the live agent (24 Nov, demo map)

- **By text:** 9 risky situations, 4 times each, all passed (vague request, second person, "thanks" is not "done", arrival, stop, unknown place).
- **By voice:** computer-made Arabic and English speech through the robot's noise filter. The whole demo with a change of destination worked. Replies started after about 1.5 seconds (worst 2.1).
- **Over synthetic music:** usually works, replies about 1.2 to 2.7 seconds. Sometimes a turn is answered late, most often a lone "Done.", so the operator says "Okay, that step is done".

## Never tested yet

- **Real people, a real room, real music** (music with singing is harder).
- **The bridge on the robot.** Tested on a laptop with fake ROS only. The setup now follows what Denis (Denenis Lab) got working on the robot on 24 Nov: no container, AimDK at `/agibot/software/common`, raw mic (no wake word), half duplex, Lumi switched off. `run_robot.sh setup / takeover / restore` do those steps.
- **An English-speaking visitor and the operator on one mic.** Visitor and operator are told apart by what they say. If it mixes them up, have the operator start with "Operator here".
- **The voice.** Now "Layan" (Saudi, professional) from the ElevenLabs library. Five alternatives, same text, are in `dist/voices/`: listen, pick one, put its id in `"voice": {"voice_id": ...}` and build. All five are already added to the team account. The operator can have their own: `"supported_voices": [{"label": "Operator", "voice_id": "<id>", "language": "en"}]`.
- **Marker reading with the real camera.** Print two and try them before relying on them.
- **Arabic and Hindi wording.** Have native speakers check `VISITOR_LINES` in `navigator.py` and the names in the profile.

If `build` is refused because of `scribe_v3_live`, delete `"asr_provider"` from the profile and build again.

## ElevenLabs features in use (for the "best ElevenLabs build" pitch)

| Feature | What it does for us |
|---|---|
| Agents + 7 client tools | the planner runs on the robot; the AI never invents a route |
| Scribe v3 Live, keywords, language detection, 10 language presets | Arabic, English, Hindi plus Spanish, French, German, Russian, Portuguese, Turkish, Chinese, Urdu |
| **Multi-voice**: a second voice for the operator | every "Operator:" line is spoken in a different voice (River); the visitor keeps Layan. Listen: `dist/agent_two_voices.wav` |
| **Evaluation criteria + data collection** | ElevenLabs scores every conversation on 5 criteria (no invented directions, English to the operator, asked not guessed, clean stop and arrival, stayed brief) and extracts destination, languages, unknown requests, position questions, handovers |
| **Post-call webhook** → `/api/elevenlabs/post-call` | the live screen gets a trip log and "what visitors asked for that is not on the map". Needs the web app online (below) |
| **Agent tests** (9, in the ElevenLabs dashboard) | `python3 -m oasis_voice eltest --repeat 3`. Includes "thank you is not a finished step", "stop is obeyed at once", "Spanish confirmed first" |
| Pronunciation dictionary | Dtec, DSO, Oraseya |
| Soft-timeout filler in 11 languages, speculative turns, interruption ignore terms | "One moment" while thinking; "okay/hmm/طيب/ठीक है" do not cut the robot off |
| First-message override + contextual updates | resumes the trip after a network drop; camera markers arrive as sensor messages |

**Model choice (24 Nov):** DeepSeek v4.1 flash (the default) keeps the agent fast (about 1.5 s) and passed all 51 live multi-turn cases. Claude Haiku 4.5 passed all 27 ElevenLabs test runs but was slower and mislabelled Spanish and French visitors as English in live runs. Two ElevenLabs tool tests ("start_at" and "step_done") are flaky on DeepSeek in the test harness while the same cases pass live; treat them as known.

## Where the robot thinks it is

It counts: the start spot, then every step the operator reports as done. When the trip ends at booth 3, it knows it is at booth 3 and the next visitor is guided from there. People can correct it ("we are at the main junction"), and printed markers let the camera confirm it. The `/live` screen shows the position and where it came from. **Restart the bridge only at the start spot**; between visitors leave it running.

## The robot does not walk from our code

By the new brief the MangoBot operator walks the robot and our agent only tells them where to go. Moving the robot from code is out of scope and against the robot rules, so there is no walking code here and there must not be.

## Web app: live on Google Cloud Run

**https://dtec-agent-49766095359.me-central1.run.app** (project `salesai-477506`, region me-central1 Doha, service `dtec-agent`, one instance kept warm).
Pages: `/live`, `/walk`, `/markers`, `/kiosk`. The ElevenLabs post-call webhook is registered to it, so finished conversations show on `/live`.

The robot's `config.env` needs `TOOL_SECRET=<the value in the laptop's .env>`; `WEBAPP_URL` is already filled in the package.

Redeploy after changing `webapp/`:
```
cd webapp && docker build --platform linux/amd64 -t me-central1-docker.pkg.dev/salesai-477506/cloud-run-source-deploy/dtec-agent:v2 . && docker push $_
gcloud run deploy dtec-agent --image me-central1-docker.pkg.dev/salesai-477506/cloud-run-source-deploy/dtec-agent:v2 --region me-central1 --project salesai-477506
```
(Docker login first: `gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin me-central1-docker.pkg.dev`.)
After changing the profile: `cd sdk && python3 -m oasis_voice build` updates the agent; the live site reads the profile from the container, so redeploy too.
Data (trips, nav) lives in the container's memory and is lost on a redeploy. Fine for the demo.

## Secrets

Copy `.env.example` to `.env`. Only `build` needs the API key; the robot needs none. Never commit it. Delete keys shared during the day after the hackathon.
