# Team Hercules: AI Voice Navigator

Voice of the Oasis Hackathon, Challenge 01 (Humanoid Robot A).

A talking guide for the lobby robot at Dtec, Dubai Silicon Oasis. Visitors speak Arabic or English; the robot gives short directions, checks them in with their host, and sends the route to their phone by QR code.

```
Visitor ⇄ Robot (mic + speaker) ⇄ bridge ⇄ ElevenLabs agent ──tools──▶ web app ──▶ reception screen + phone page
```

## What's in this folder

| Folder | What it is | Status |
|---|---|---|
| `agent/` | Agent instructions, first message, knowledge base, setup steps, test list | Ready to paste into ElevenLabs |
| `webapp/` | Mock reception system: check-in + route tools, live reception screen, phone route page, laptop demo page | Built and tested on a laptop (smoke test passes) |
| `robot/` | The organisers' bridge code (unchanged) and a checklist for the person at the robot | Ready |
| `onsite/` | What to collect inside Dtec, and a message to send the on-site teammate | Ready |
| `pitch/` | Demo script, 100-word description, 3 slides, pitch talk, likely questions | Draft ready |

**Start here: [WALKTHROUGH.md](WALKTHROUGH.md)** has every step from zero to demo, in order.

Agent ID: `agent_4001m86cac97egtb840g9whcrbz3` (created, English + Arabic, PCM 16000; the tools get connected once the web app is online).

## What still needs a person

1. **Claim ElevenLabs credits** (Discord → coupon-codes → Start Redemption), then follow `agent/ELEVENLABS_SETUP.md`.
2. **Put the web app online** (`webapp/README.md`, Render recommended) and set a `TOOL_SECRET`.
3. **Add the two webhook tools** to the agent with the web app URL and the secret.
4. **Send the agent ID and the `/screen` link** to the on-site teammate, plus `onsite/MESSAGE_TO_ONSITE.md`.
5. **Run `agent/test_conversations.md`** in the ElevenLabs test window.
6. **When directions arrive from the building,** fill the "NOT COLLECTED YET" rows in `agent/knowledge_base.md` and upload it again.
7. **Ask an Arabic speaker** to check the Arabic first message and the test phrases.
8. **Before filming,** reset the screen (`POST /api/reset`).
9. **Make the 3 slides** from `pitch/slides_and_pitch.md`, and add a photo of the Dtec lobby.

## Rules we follow

- The agent is built on ElevenLabs Agents. We never move the robot.
- Robot code runs only in the container on PC2. Don't touch the robot's system.
- Facts come from the challenge brief or from our own walk of the building. Anything made up is marked "demo data".
- The ElevenLabs API key never goes in this repo, a doc or a chat.
