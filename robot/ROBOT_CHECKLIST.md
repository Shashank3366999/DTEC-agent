# Robot checklist: blind navigation

**You never need to change code on the robot.** You run the bridge; MangoBot moves the robot.

## Before the slot

- [ ] `dist/oasis_voice_robot.zip` built **after** the real map and after `build` (it must contain `state/dtec_floor.json`)
- [ ] `/live` open on a laptop, web app awake
- [ ] Markers stuck up, if allowed
- [ ] Robot on the start spot, facing map north

## Ask MangoBot

- [ ] Wake word, AimDK path, internet on PC2, external mic
- [ ] OK to put opencv-python-headless into our own `pylib` folder? (`setup` tries; if it fails the robot counts steps)

## Run (full steps: QUICKSTART.md in the zip)

```bash
ssh run@<robot address>            # password in the organisers' email
cd ~/hercules/oasis_voice_robot
./run_robot.sh setup               # once
./run_robot.sh doctor              # fix every FIX line
./run_robot.sh takeover            # Lumi quiet, volume up
./run_robot.sh
./run_robot.sh restore             # before you leave
```

- No wake word: the bridge listens to the raw microphone. The robot cannot be interrupted while it speaks (the mic is muted then).
- `camera markers: on` or `off ... Counting steps instead`. If `on` but no `marker:` line appears near a marker, ask MangoBot for the camera topic and set `CAMERA_TOPIC`.
- **Restart the bridge at the start spot before every route.** It assumes the robot is there.

## Brief the operator (30 seconds)

"It talks to you in English and starts with 'Operator'. Do exactly that. When the step is finished say **"Okay, that step is done"** (a lone "done" is sometimes slow or missed under music). If it asks something, answer short: 'I passed the kitchen'. Say **say again** to repeat. Wait until it finishes a sentence before you speak: it cannot hear while it talks. Two low beeps: stop and wait."

## Filming

- [ ] Find an organiser first: they bring the music and the new destination
- [ ] Visitor, robot **and operator** in the shot
- [ ] Three routes, one take each, cuts only between them, 3 minutes in total

## Problems

| What you see | Fix |
|---|---|
| Interrupts itself | `HALF_DUPLEX=1` |
| Music or chatter gets in | `NOISE_MIN_RMS=600` |
| Quiet visitors not heard | `NOISE_MIN_RMS=200` or `NOISE_GATE=0` |
| `speaker focus: NO` | MangoBot engineer: agent module |
| `cannot reach ElevenLabs` | No internet in the container |
| Wrong place | "Stop. We are at the X" |
| A marker counts too early | `MARKER_MIN_PX=100`, or `MARKERS=0` to turn them off |

## Robot rules (MangoBot and AgiBot)

Code only in the container on PC2, **never on PC1**. Don't touch the OS, drivers, DDS, firmware, power or hardware. Save only under `/home/agi`, never in `aimdk*`. Never publish to a motion topic. If anything looks wrong, stop and call the engineer.
