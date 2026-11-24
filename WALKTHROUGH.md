# Walkthrough: from zero to the three routes

1. **Measure the floor**: [onsite/COLLECT_FLOOR_MAP.md](onsite/COLLECT_FLOOR_MAP.md). Edit `sdk/profiles/dtec_floor.json`.
2. **Check the map**: `cd sdk && python3 -m oasis_voice validate && python3 -m oasis_voice routes`. Read every route: would you get there?
3. **Walk it with a phone**: `python3 -m oasis_voice export`, start the web app, open `/walk`. Do exactly what it says. Fix the map until every route works.
4. **Build the agent**: `python3 -m oasis_voice build`.
5. **Talk to it**: web app → `/kiosk`. One person is the visitor, one is the operator. Play music next to the laptop.
6. **Robot**: `python3 robot/make_package.py`, copy the zip, follow [robot/ROBOT_CHECKLIST.md](robot/ROBOT_CHECKLIST.md).
7. **Film** the three routes: [pitch/demo_script.md](pitch/demo_script.md).

| Problem | Fix |
|---|---|
| A direction is wrong | Fix the map in the profile, `validate`, `routes`, `export`; send the new profile to the robot |
| It mixes up operator and visitor | Operator starts with "Operator here". Short reports: "done", "I passed the kitchen" |
| It lost track of where it is | Tell it: "We are at the kitchen" |
| It interrupts itself | `HALF_DUPLEX=1` |
| Music gets in | `NOISE_MIN_RMS=600`; stand closer; ask for the external mic |
| The agent says a tool failed | Use `/kiosk` or the SDK bridge, not the ElevenLabs test page or the original bridge |
