# Walkthrough: from zero to demo

Each step says **who** does it and **what you should see**.

```
Part 1  The agent exists                           ✅ done (agent_4001m86cac97egtb840g9whcrbz3)
Part 2  Laptop demo                                ✅ works on any laptop, no Render needed
Part 3  Put the web app online (for the robot)     ⬜ to do
Part 4  Run the SDK bridge on the robot            ⬜ at the robot slots
Part 5  Show the demo                              ⬜ film Wed 06:30, pitch Wed 09:20
Extra   Add the real on-site directions            ⬜ when they arrive
```

Our agent ID: **`agent_4001m86cac97egtb840g9whcrbz3`** (saved in `sdk/state/dtec_navigator.json`). It is not secret.

---

## Part 1: The agent ✅

Made from `sdk/profiles/dtec_navigator.json` with the SDK. To change it after editing the profile:

```bash
cd DTEC-agent/sdk
python3 -m oasis_voice build        # needs ELEVENLABS_API_KEY in DTEC-agent/.env (copy .env.example)
```

It always updates the **same** agent, so the ID never changes. Details: [sdk/README.md](sdk/README.md).

**Test it by typing** (no mic needed, tools run locally):
```bash
pip3 install websocket-client
python3 -m oasis_voice chat --say "Where is the bank?" --say "Where can I pray?"
```

---

## Part 2: Laptop demo ✅

```bash
cd DTEC-agent/webapp
node server.js
```
Open **http://localhost:3000/kiosk**, press the call button, allow the microphone and talk. The reception screen beside it updates live: check-ins, route QR codes and operator alerts all work **by voice**, because the tools run in the browser.

Other pages: `/screen` (reception screen), `/test` (press buttons to fake tool calls, and **Reset all data** before filming).

---

## Part 3: Put the web app online (for the robot)

The robot needs a reception screen it can reach over the internet.

1. render.com → sign up with GitHub → **New → Web Service** → pick `DTEC-agent`.
2. **Root Directory:** `webapp` · **Build Command:** empty · **Start Command:** `node server.js` · **Instance:** Free.
3. **Environment:** `TOOL_SECRET` = a long made-up word.
4. Create, wait for **Live**, copy the URL, then add `PUBLIC_URL` = that URL.
5. Check `<URL>/health` says `{"ok":true}` and `<URL>/kiosk` works.

> Free Render sleeps when unused (about a minute to wake). Open `/screen` a few minutes before every robot slot.

No time for Render? Run the web app on a laptop on the **same network as the robot** and use `http://<laptop IP>:3000` as `WEBAPP_URL`.

---

## Part 4: Run the SDK bridge on the robot (on-site teammate)

Full checklist: [robot/ROBOT_CHECKLIST.md](robot/ROBOT_CHECKLIST.md). Short version, on PC2 inside the container:

```bash
pip3 install websocket-client numpy
source /opt/ros/humble/setup.bash && source <aimdk path>/install/setup.bash
cd /home/agi/sdk                       # the repo's sdk folder, copied to the robot
export WEBAPP_URL=<the Render URL>
export TOOL_SECRET=<the same secret word>
python3 -m oasis_voice bridge
```

Say the wake word, then talk. The terminal shows every `visitor:`, `tool ...`, `robot:` line and the reply latency. Fixes for common problems are in the checklist.

---

## Part 5: Show the demo

### A. Robot demo (filmed in the last robot slot, Wed 06:30)
1. Open `<URL>/test` → **Reset all data**.
2. Put a laptop with `<URL>/screen` next to the robot. The camera sees **both**.
3. Follow [pitch/demo_script.md](pitch/demo_script.md): Arabic greeting → meeting at Oraseya Capital + wants to pray → check-in appears → "where's the bank / mosque?" clarifying question → switch to English → QR route, scan it → unknown question → "I don't know, here's reception" → ask for a person → operator alert appears.
4. One unedited take, max 2 minutes. Practise once first.

### B. Backup laptop video (record before the slot)
Screen-record `/kiosk` (with sound) running the same script.

### C. Pitch (7 minutes)
3 min talk + 2 min demo (robot video or live `/kiosk`) + 2 min questions: [pitch/slides_and_pitch.md](pitch/slides_and_pitch.md).

---

## Extra: Add the real on-site directions

1. Open `sdk/profiles/dtec_navigator.json` and find the place (e.g. `"id": "toilets"`).
2. Replace the `directions` steps (English and Arabic) with what was walked, update `walk_minutes`, and delete `"demo": true`.
3. Check: `cd sdk && python3 -m oasis_voice validate && python3 -m oasis_voice ask "toilets"`
4. `python3 -m oasis_voice build`, then `git push`, and **pull the repo on the robot** (directions are looked up on the robot).

---

## If something goes wrong

| Problem | Fix |
|---|---|
| The agent says it can't look places up | The tools aren't running: use `/kiosk` (not the ElevenLabs test page), or the SDK bridge on the robot (not the original bridge) |
| Check-in or route says the screen is offline | `WEBAPP_URL` / `TOOL_SECRET` wrong or Render asleep. Open `<URL>/health` |
| The robot interrupts itself | `HALF_DUPLEX=1 python3 -m oasis_voice bridge` |
| It picks up background chatter | `NOISE_MIN_RMS=600 python3 -m oasis_voice bridge` |
| An answer is wrong | Fix the place in `sdk/profiles/dtec_navigator.json`, then `build` (and pull on the robot) |
| The Arabic voice sounds bad | Add `"voice": {"voice_id": "<id>"}` to the profile with a better voice, then `build` |
