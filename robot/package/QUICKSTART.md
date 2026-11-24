# Dtec Floor Guide: robot quick start

This folder is everything the robot needs. A MangoBot operator walks the robot; our agent tells them where to go.
The route is planned here, from `profiles/dtec_floor.json`. The agent ID is in `state/dtec_floor.json`.

Based on what Denis (Denenis Lab) and the organisers found on the robot on 24 Nov: there is **no container**, you work
on the host as the shared user `run`, only inside your own folder.

## 1. Get in and copy the folder

From the engineers' screen or the hall Wi-Fi (addresses from the organisers' email; password is in that email):

```bash
ssh run@<robot address>            # cable: 10.0.1.41  ·  hall Wi-Fi: 172.21.224.102 (robot 1) / .110 (robot 2)
mkdir -p ~/hercules
```
Copy this whole folder into `~/hercules/` (from your laptop: `scp -r oasis_voice_robot run@<robot address>:~/hercules/`).
To find a robot on the Wi-Fi from a Mac: `dns-sd -B _agibot._tcp local`, then `dns-sd -L <name> _agibot._tcp local`.

## 2. Once: packages

```bash
cd ~/hercules/oasis_voice_robot
cp config.env.example config.env     # set WEBAPP_URL and TOOL_SECRET (from the team); the rest can stay
chmod +x run_robot.sh
./run_robot.sh setup
./run_robot.sh doctor                # every line OK, or a FIX line that says what to do
```

## 3. At the start of your slot

```bash
./run_robot.sh takeover              # Lumi (the built-in assistant) quiet, volume 95, shows who else uses the speaker
./run_robot.sh                       # the bridge. Ctrl+C stops it
```
Put the robot on the start spot first. No wake word is needed: just talk. Good output:
```
mic: raw /aima/hal/audio/capture (no wake word) · half duplex on
camera markers: on, /aima/hal/sensor/...      (or: off ... Counting steps instead)
speaker focus: yes
connected. agent speaks pcm_16000 and listens to pcm_16000
visitor: ...
tool start_route {"place_id": "booth_2", ...} -> {"status": "started", ...}
robot: ... Operator: Walk straight about 6 metres, and stop at ...
```

## 4. Before you leave

```bash
./run_robot.sh restore               # volume 72, Lumi back on
```

## If something goes wrong

| What you see | Fix (in config.env, then run again) |
|---|---|
| The robot answers itself | `HALF_DUPLEX=1` (it is forced on with the raw mic; check nobody set `RAW_MIC=0`) |
| It cannot be interrupted while it talks | Expected with the raw mic: the mic is muted while it speaks. Wait for the end of the sentence |
| Background chatter gets picked up | `NOISE_MIN_RMS=600` |
| Quiet visitors are not heard | `NOISE_MIN_RMS=200` or `NOISE_GATE=0`; stand closer |
| Lumi answers too | `./run_robot.sh takeover` again |
| Another team's bridge is on the speaker | `takeover` lists it; ask them to stop theirs |
| `cannot reach ElevenLabs` | no internet on the robot: tell the MangoBot engineer |
| `speaker focus: NO` | ask the MangoBot engineer to check the agent module |
| `screen is offline` | `WEBAPP_URL` / `TOOL_SECRET` wrong, or open the URL in a browser to wake it |
| `No module named aimdk_msgs` | `AIMDK_PATH` wrong. Try `ls /agibot/software/common/local/lib/python3.10/dist-packages` |
| The SDK won't start at all | fallback: `cd original_bridge && ELEVENLABS_AGENT_ID=<id in state/dtec_floor.json> HALF_DUPLEX=1 python3 elevenlabs_robot_bridge.py` (talks, but can't plan routes, and needs the wake word) |

## Robot rules (MangoBot / AgiBot)

Only your own folder under `/home/run`. No `pip --user`, no `sudo`, nothing in `aimdk*` or `/agibot`. Don't touch the OS,
drivers, DDS, firmware, power or hardware. We never move the robot from code. Stop your bridge and run `restore` before
you leave. If anything looks wrong, stop and call the MangoBot engineer.

## Updating the map

When the team sends a new `dtec_floor.json`, replace `profiles/dtec_floor.json` with it and run `./run_robot.sh` again.
