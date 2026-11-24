# Robot checklist (for the person at the robot)

The robot is only the ears and mouth. All the thinking happens in the ElevenLabs agent, which the remote team can change live. **You never need to change code on the robot.** You only run the bridge.

## Bring to every robot slot

- [ ] Laptop, charged, with `elevenlabs_robot_bridge.py` on it (this folder)
- [ ] The **agent ID** (from the remote team)
- [ ] The **reception screen** link open on the laptop (`<web app>/screen`)
- [ ] Phone, to scan the QR code and to film
- [ ] A video call open with the remote team, so they can fix the agent live
- [ ] The demo script (`../pitch/demo_script.md`), printed or on your phone

## Ask at the first robot session

- [ ] What is the robot's **wake word**?
- [ ] Where will the robot **stand** during the demo? (All our directions start from there.)
- [ ] Is there an **external microphone** for the noisy room?
- [ ] What is the **AimDK path** for the setup command?
- [ ] Does the container on **PC2** have internet?
- [ ] Ask the teams who went before you what went wrong for them.

## Run it (on robot PC2, inside the container MangoBot gives you)

```bash
pip3 install websocket-client numpy
source /opt/ros/humble/setup.bash && source <aimdk path>/install/setup.bash
export ELEVENLABS_AGENT_ID=<agent id>
# only if the agent is private:  export ELEVENLABS_API_KEY=<key>   (type it in, never save it in a file)
python3 elevenlabs_robot_bridge.py
```

Then say the wake word once and talk normally.

Good signs in the output:
- `speaker focus: yes`
- `connected. agent speaks pcm_16000 and listens to pcm_16000`
- `visitor: ...` and `robot: ...` lines as you talk

## If something goes wrong

| What you see | Fix |
|---|---|
| The robot interrupts itself | Stop it (Ctrl+C) and run again with `HALF_DUPLEX=1 python3 elevenlabs_robot_bridge.py` |
| Speaker stays silent, or `ERROR: set the agent's output audio to PCM 16000 Hz` | Ask the remote team to set the agent's output audio to PCM 16000 Hz |
| `WARNING: set the agent's input audio to PCM 16000 Hz` | Ask the remote team to set the input audio to PCM 16000 Hz |
| `cannot reach ElevenLabs` | No internet in the container. Tell the MangoBot engineer |
| `speaker focus: NO` | Ask the MangoBot engineer to check the agent module |
| It can't hear people in the room | Ask the engineer for the external mic. To force it: `MIC_STREAM=2` |
| You want to see everything | Add `VERBOSE=1` |
| The answer is wrong or too long | Tell the remote team. They fix the agent, then you just ask again (no restart needed for a new conversation) |

## Robot rules (from MangoBot and AgiBot)

- Our code runs only in the container on PC2. **Never on PC1.**
- Don't touch the operating system, drivers, DDS, firmware, power or hardware. No factory reset.
- Save files only under `/home/agi`, never in `aimdk*`. Keep a copy on your laptop.
- We never move the robot. MangoBot controls all movement.
- If anything looks wrong, stop and call the MangoBot engineer.

## Filming the demo on the robot

- [ ] Remote team resets the reception screen first (`/api/reset`)
- [ ] The camera sees the robot **and** the reception screen
- [ ] Do one practice run, then film **one unedited take, max 2 minutes**
- [ ] Scan the QR code with a phone on camera when the route appears
