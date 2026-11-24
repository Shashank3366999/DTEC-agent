# Message to send to the person at the robot

Attach `dist/oasis_voice_robot.zip`. Then paste this:

---

Hi! Here is the robot package. Everything is ready, you only run it. Four steps, about 15 minutes.

**1. Put the zip on the robot**

- Connect to the hall Wi-Fi and open a terminal.
- Copy the zip to the robot (password from the organisers' email):
  `scp oasis_voice_robot.zip run@172.21.224.102:~/`
  (robot 2 is `172.21.224.110`)
- Log in: `ssh run@172.21.224.102`
- Then: `mkdir -p ~/hercules && cd ~/hercules && unzip ~/oasis_voice_robot.zip && cd oasis_voice_robot`

**2. Install once**

```
cp config.env.example config.env
nano config.env        # put the secret word I send you separately after TOOL_SECRET=
chmod +x run_robot.sh
./run_robot.sh setup
./run_robot.sh doctor
```
Every line should say OK. "FIX: the floor map is still demo data" is fine for now.

**3. Run it**

Put the robot on the start spot facing forward. Then:
```
./run_robot.sh takeover
./run_robot.sh
```
No wake word needed. Say "Take me to the kitchen" and see what it says. Press Ctrl+C to stop.

Before you leave the robot: `./run_robot.sh restore`

**4. Measure the floor (most important, 20 minutes)**

The directions are made up until we have the real floor. Stand where the robot will start, facing forward. Count steps (one step is about 0.7 m) to each place we will demo: the call booths, the kitchen, the meeting room, the conference room. Note every corner where the robot has to turn, and which places are on a straight line from each other. Photos help. Send it all to me and I'll send back one file to replace.

**Live screen:** open https://dtec-agent-49766095359.me-central1.run.app/live on any laptop or phone next to the robot. It shows what the robot told the operator and the map.

**If something goes wrong**, send me a photo of the screen. The quick start inside the zip has a table of fixes.

---

## What to tell the operator (the MangoBot person walking the robot)

"The robot talks to you in English and starts with 'Operator'. Do exactly that. When you finish a step say 'Okay, that step is done'. Wait until it finishes a sentence before you speak."
