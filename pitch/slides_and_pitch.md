# Slides (max 3) and pitch

The pitch is 7 minutes in total: 3 min talk, 2 min demo (live or the robot video), 2 min questions.

The jury scores: working demo 25%, technical quality and use of ElevenLabs 20%, voice experience 20%, challenge fit and could DSO run it 15%, pitch 10%, could it be a company 10%.

## Slide 1: The problem

**Title:** Finding your way in DSO starts with asking a stranger

- Offices, campuses, homes and malls sit side by side in Dubai Silicon Oasis.
- First-time visitors, new hires and guests don't know which building, entrance or floor.
- Nothing about the inside of buildings like Dtec is published, so they ask whoever is nearby.
- Many speak Arabic first, and switch to English mid-sentence.

*Picture:* a photo of the Dtec lobby (take one on site).

## Slide 2: How it works

**Title:** A voice guide that answers, then acts

Simple diagram, left to right:
Visitor → Robot (ears and mouth) → ElevenLabs agent (brain) → our web app → reception screen + phone

Under it, three short points:
- **Arabic and English**, switches when the visitor does, short answers first.
- **Real directions** our team walked inside Dtec; says "I don't know" instead of guessing.
- **Acts:** checks the visitor in with their host, and sends the route to their phone by QR code.

Small print: built on ElevenLabs Agents, with a knowledge base, webhook tools, and language detection.

## Slide 3: Why DSO, and what's next

**Title:** One agent, every DSO building, every channel

- **For DSO:** fewer repeat questions at reception, a welcome in the visitor's own language, and data on what visitors look for.
- **Next:** the same agent on lobby screens, the DSO phone line and WhatsApp. Add more buildings by adding their directions.
- **Business:** a monthly fee per building. Building managers see which places visitors ask about most.

## Pitch talk (about 3 minutes)

**Problem (40 s).** "Imagine it's your first day at Dubai Silicon Oasis. You have a meeting on the first floor of TechnoHub 1 at three, and you want to pray first. Offices, campuses and malls are side by side, nothing about the inside of the buildings is online, and the person you ask may not speak your language. So you ask a stranger."

**Our answer (40 s).** "We gave the lobby robot a voice. The DSO Visitor Guide speaks Arabic and English, follows you when you switch, and gives short directions you can actually follow. It doesn't make things up: when it doesn't know, it says so and sends you to reception."

**What makes it different (40 s).** "First, real directions: nothing about the inside of Dtec is published, so we walked the building ourselves. Second, it does things: it tells your host you've arrived and puts the route on your phone with a QR code. You saw both on the screen."

**Why it matters for DSO (40 s).** "DSO already has more than 340 online services, but not a voice you can just talk to. This guide works on a robot today, and the same agent can run on a lobby screen, the phone line or WhatsApp tomorrow. Each new building only needs its directions added."

**Close (20 s).** "Visitors get a welcome in their own language, reception answers fewer repeat questions, and DSO learns what visitors look for. Thank you."

## Likely questions

| Question | Short answer |
|---|---|
| What if it gives a wrong direction? | It only answers from facts in its knowledge base. Everything else gets "I don't know, please ask reception". We tested trick questions. |
| How did you get the inside directions? | We walked the building on Tuesday from the robot's spot, with photos and walking times. Anything we couldn't check is marked as demo data. |
| How does it handle Arabic and English mixing? | ElevenLabs language detection switches the agent's language when the visitor switches. |
| Is the check-in real? | It's a mock reception system for the demo. In production it would connect to DSO's visitor management or send the host a message. |
| What about privacy? | It only asks for a first name. No phone numbers or IDs. The route goes to the phone by QR code, so no phone number is needed. |
| What does it cost to run? | ElevenLabs usage per conversation plus a small web server. Per building, that is far less than a staffed desk at all hours. |
| How would DSO scale it? | One agent with a knowledge base per building, on robots, screens, the phone line and WhatsApp. |
