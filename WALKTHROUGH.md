# Walkthrough: from zero to demo

Five parts, in order. Each step says **who** does it and **what you should see**.

```
Part 1  Make the agent (get the agent ID)        ✅ done
Part 2  Put the web app online                    ⬜ to do
Part 3  Connect the agent to the web app          ⬜ to do
Part 4  Put the agent ID where it is needed       ⬜ to do
Part 5  Show the demo                             ⬜ to do
Extra   Add Chandan's directions                  ⬜ when they arrive
```

Our agent ID: **`agent_4001m86cac97egtb840g9whcrbz3`** (also saved in `agent/agent_id.txt`). It is not secret.

---

## Part 1: Make the agent (get the agent ID) ✅

**Already done.** This is how it was made, in case you need to do it again.

1. Open `hercules/.env` in VS Code and put the ElevenLabs key after `ELEVENLABS_API_KEY=`. Save.
   *Never paste the key in a chat or a doc.*
2. Open a terminal and run:
   ```bash
   cd ~/Documents/hackathn/hercules
   python3 agent/setup_agent.py
   ```
3. **You should see:** `Done. Agent ID: agent_…`

**Running it again does not make a new agent.** It updates the same one (the ID is in `agent/agent_id.txt`), so the ID never changes. Run it every time we change the instructions or the facts.

**To check it works:** open http://localhost:3000/kiosk?agent=agent_4001m86cac97egtb840g9whcrbz3 (the web app must be running, see Part 2, step 1). Press the call button, allow the microphone, and talk.

---

## Part 2: Put the web app online

The web app is the screen with check-ins and the QR code. It has to be online so the agent can reach it.

### Step 1: Run it on your laptop (for testing)
```bash
cd ~/Documents/hackathn/hercules/webapp
node server.js
```
**You should see:** `Hercules reception backend on http://localhost:3000`
Open http://localhost:3000/screen and http://localhost:3000/test side by side and press the buttons on the test page.

### Step 2: Put it online on Render (free)
1. Put the `hercules` folder on GitHub (a private repo is fine). Check `.env` is **not** in it (it is in `.gitignore`).
2. Go to render.com and sign up (GitHub login is easiest).
3. Click **New → Web Service** → pick the repo.
4. Fill in:
   - **Root Directory:** `webapp` (or `hercules/webapp` if the repo contains the whole hackathon folder)
   - **Build Command:** leave empty
   - **Start Command:** `node server.js`
   - **Instance type:** Free
5. Under **Environment**, add:
   - `TOOL_SECRET` = make up a long random word, for example `hercules-oasis-4821-lobby`
6. Click **Create Web Service** and wait until it says **Live**.
7. Copy the URL at the top (something like `https://hercules-abcd.onrender.com`).
8. Add one more environment variable: `PUBLIC_URL` = that URL. Render restarts by itself.
9. **Check:** open `<your URL>/health`. **You should see:** `{"ok":true}`. Then open `<your URL>/screen`.

> Free Render sleeps when nobody uses it and takes about a minute to wake. Open `/screen` a few minutes before every robot slot and before the pitch.

**No time for Render?** Run it on a laptop and share it with a temporary link: `npx localtunnel --port 3000`. The link changes each time, and the laptop must stay on.

---

## Part 3: Connect the agent to the web app

This makes "check in" and "send route to phone" work.

1. Open `hercules/.env` and fill in:
   ```
   WEBAPP_URL=https://hercules-abcd.onrender.com
   TOOL_SECRET=hercules-oasis-4821-lobby
   ```
   (Same URL as Part 2, no `/` at the end, same secret word as on Render.)
2. Run:
   ```bash
   cd ~/Documents/hackathn/hercules
   python3 agent/setup_agent.py
   ```
3. **You should see:** `Creating webhook tools…` then `Updating agent agent_4001m86…` then `Done.`
4. **Test:** open `<your URL>/kiosk?agent=agent_4001m86cac97egtb840g9whcrbz3`, press call, and say:
   *"I have a meeting at Oraseya Capital at three. My name is Sara. Please tell them I'm here."*
   **You should see:** a new arrival appear on the right side within a few seconds.
   Then say: *"Can you send me the route?"* → a QR code appears. Scan it with your phone.

If nothing appears: check the URL and secret in `.env` match Render exactly, and that `<your URL>/health` works.

---

## Part 4: Put the agent ID where it is needed

The ID goes in three places.

| Where | Who | How |
|---|---|---|
| **The robot** | Chandan | In the robot terminal: `export ELEVENLABS_AGENT_ID=agent_4001m86cac97egtb840g9whcrbz3`, then `python3 elevenlabs_robot_bridge.py` (full steps in `robot/ROBOT_CHECKLIST.md`) |
| **The laptop demo** | Anyone | Open `<your URL>/kiosk?agent=agent_4001m86cac97egtb840g9whcrbz3` |
| **The ElevenLabs website** | Account owner | Agents → *DSO Visitor Guide (Team Hercules)* → **Test AI agent** |

**Message to send Chandan:**
> Agent ID: `agent_4001m86cac97egtb840g9whcrbz3`
> Reception screen: `<your URL>/screen` (open this on a laptop next to the robot)
> At the robot: `export ELEVENLABS_AGENT_ID=agent_4001m86cac97egtb840g9whcrbz3` then `python3 elevenlabs_robot_bridge.py`. Say the wake word, then talk. If it interrupts itself, run it with `HALF_DUPLEX=1` in front.

---

## Part 5: Show the demo

### A. The robot demo (the main one, filmed in the last robot slot)
1. **Before:** open `<your URL>/test` and press **Reset all data**, so the screen starts empty.
2. Put a laptop with `<your URL>/screen` next to the robot. The camera must see **both** the robot and the screen.
3. Chandan starts the bridge on the robot (Part 4).
4. One person plays the visitor and follows `pitch/demo_script.md`:
   - Says hello in Arabic → the robot says it's an AI guide
   - "Meeting at Oraseya Capital at three, I want to pray first" → short directions, offers check-in
   - Says yes + first name → **the arrival appears on the screen**
   - Switches to English, asks for the route → **the QR code appears**, scan it with a phone on camera
   - Asks something it can't know → "I don't know, please ask reception"
5. Film **one unedited take, max 2 minutes**. Practise once before filming.

### B. The laptop demo (the backup, record this tonight)
1. Open `<your URL>/kiosk?agent=agent_4001m86cac97egtb840g9whcrbz3` on a laptop.
2. Start a screen recording (with sound).
3. Press call and run the same demo script. The screen on the right updates live.
4. Keep this video in case the robot fails.

### C. In the pitch (7 minutes)
- **3 min talk:** `pitch/slides_and_pitch.md` has the 3 slides and what to say.
- **2 min demo:** play the robot video, or do the laptop demo live.
- **2 min questions:** likely questions and answers are in `pitch/slides_and_pitch.md`.

---

## Extra: Add Chandan's directions

When Chandan sends the walking directions:
1. Open `agent/knowledge_base.md`.
2. Replace each `NOT COLLECTED YET` with the real directions, and add `[On site 24 Nov]` at the end.
3. Run `python3 agent/setup_agent.py` again. The agent knows the new directions straight away, on the robot too.

(Or paste his messages to Claude and ask it to do this.)

---

## If something goes wrong

| Problem | Fix |
|---|---|
| The agent answers but check-in does nothing | Part 3 not done, or `WEBAPP_URL` / `TOOL_SECRET` wrong. Check `<your URL>/health` |
| The laptop demo has no call button | The agent ID in the link is wrong, or the page needs a refresh |
| The robot is silent | Ask the team to check the agent's output audio is PCM 16000 (it is, unless someone changed it) |
| The robot interrupts itself | Run the bridge with `HALF_DUPLEX=1` |
| The Arabic voice sounds bad | Pick a better voice in ElevenLabs (Voice tab), or ask the ElevenLabs mentors |
| An answer is wrong | Change `agent/system_prompt.md` or `agent/knowledge_base.md`, then run `python3 agent/setup_agent.py` |
| The screen is slow to load | Render was asleep. Wait a minute and refresh |
