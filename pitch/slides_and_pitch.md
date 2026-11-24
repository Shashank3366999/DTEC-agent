# Slides (max 3) and pitch

8 minutes: **3 pitch, 3 demo (our robot video), 2 questions**. Scores: working demo 25%, technical and ElevenLabs 20%, voice 20%, challenge fit 15%, pitch 10%, investable 10%.

## Slide 1: The problem
**Nobody in the room speaks both languages and knows the way.** The visitor knows where they want to go. The operator can walk the robot. They can't understand each other, and neither knows the route.

## Slide 2: How it works
**The AI talks. The planner decides.** Visitor (Arabic, English, Hindi) → ElevenLabs agent → route planner on the robot → operator (English), step by step.
- Understands, asks, translates. **Never invents a turn**: every step comes from the map.
- Knows where it is: counts steps, checks with people, reads markers with the camera.
- Changed your mind? Plans from where the robot stands, and asks only when the answer matters.
- Two voices from one agent: the operator hears their own voice. Every conversation is scored by ElevenLabs on five rules and feeds the map with what visitors asked for and could not get.

## Slide 3: Why DSO, and what's next
**One map, every building, any body.** Today a robot and an operator; the same planner guides a new receptionist, a phone, or a blind visitor. Adding a floor takes about 20 minutes of measuring. A monthly fee per building.

## Pitch talk (3 minutes)
**Problem (40 s).** "A visitor walks in and asks in Arabic for a quiet place to take a call. The person walking the robot doesn't speak Arabic, and doesn't know this floor. Somebody has to understand one, guide the other, and know the way."
**Answer (50 s).** "Our agent does all three. It talks to the visitor in their language and to the operator in English, one short step at a time, and calls the stop."
**What's different (50 s).** "Language models are great at talking and bad at directions. So ours is not allowed to give any. A planner on the robot decides every step from a measured map. We tested it with a simulated operator who only knows the words it hears: 500 trips with the destination changed on the way, and every one ended in the right place."
**Why DSO (30 s).** "Offices, campuses and malls side by side, visitors who speak Arabic first. One measured floor serves a robot today and phones tomorrow."
**Close (10 s).** "You can change its mind. You can't make it guess."

> Say only what is true on the day: the 500 trips are a simulation, on the map in the repo at that time.

## Likely questions
| Question | Short answer |
|---|---|
| How does it know where it is? | Counts from the start, one landmark per step. People can correct it. Printed markers and the head camera confirm it. |
| How does it tell visitor and operator apart? | By what they say and the language: short English reports are the operator. It asks when unsure. |
| What if it is lost? | It stops the operator, asks what is next to the robot, and replans. It never guesses. |
| What if the network drops? | The route lives on the robot. Two beeps mean stop; it repeats the step when it is back. |
| Why not LiDAR? | It needs a site map set up with AgiBot. It is the next step, and only replaces the position source. |
| Music and noise? | A noise gate that learns steady sound, place names as speech keywords, Scribe v3 Live. |
| How deep is the ElevenLabs use? | Client tools, multi-voice, language detection with 10 presets, evaluation criteria and data collection, post-call webhook, 9 agent tests in the dashboard, pronunciation dictionary, soft-timeout fillers. |
| Why that LLM? | We measured three inside ElevenLabs: DeepSeek was fastest and passed all 51 live cases; the others were slower or mislabelled languages. |
