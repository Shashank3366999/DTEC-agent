# Test conversations

Run these in the ElevenLabs test window first, then on the robot. Tick each one when it passes. Have the reception screen (`/screen`) open while testing.

## Must pass

- [ ] **Says it is an AI.** Start a chat. The first message says it is an AI guide.
- [ ] **Arabic question, Arabic answer.**
  Say: «وين مكتب أوراسيا كابيتال؟» ("Where is the Oraseya Capital office?")
  Expect: a short Arabic answer, first floor of Dtec TechnoHub 1.
- [ ] **Two goals at once (the brief's winning demo).**
  Say: «عندي اجتماع مع أوراسيا كابيتال الساعة ثلاثة، وأبي أصلي قبل.» ("I have a meeting with Oraseya Capital at three, and I want to pray first.")
  Expect: DSO Masjid in the Techno Point building first, then Oraseya Capital on the first floor of TechnoHub 1. It offers to tell Oraseya Capital she has arrived.
- [ ] **Check-in shows on the screen.** Say yes and give a first name. Expect: one sentence confirming, and a new row on the reception screen within 2 seconds.
- [ ] **Language switch mid-conversation.** After talking in Arabic, say in English: "Actually, can you send me the route?"
  Expect: it answers in English and calls the route tool. The QR code appears on the screen and it tells you to scan it.
- [ ] **Vague request → clarifying question.** Say: "Where is the bank?"
  Expect: it asks which one, or suggests Emirates NBD on the first floor of Silicon Central Mall. It does not guess a random bank.
- [ ] **Short answers.** Ask: "Where can I get coffee?" Expect: one or two sentences, not a speech.
- [ ] **"I don't know" instead of guessing.**
  - "What is the Wi-Fi password at Oraseya?" → doesn't know, sends you to reception.
  - "Which floor is Google's office on?" → doesn't know, sends you to reception.
  - "How long is the walk to the mall?" → doesn't know the walking time, suggests a taxi or maps.
- [ ] **No made-up inside directions.** Before we add on-site data, ask "Where are the toilets?" Expect: it says it doesn't know and sends you to reception. After we add the data, expect the real directions.
- [ ] **Interrupting.** Start a long question, let it start answering, then interrupt with a new question. It stops and answers the new one.

## Should pass

- [ ] **Opening hours.** "Is the mall open now?" → Silicon Central Mall is open 08:00 to midnight.
- [ ] **24-hour places.** "I need a pharmacy late at night." → Life Pharmacy in Palace Towers, open 24 hours.
- [ ] **Medical.** "I feel sick." → clinics (Burjeel Medical Center DSO, Life Medical Centre, 07:00 to 23:00). Mentions 999 for an emergency.
- [ ] **Off topic.** "Write me a poem." → politely says it only helps with finding your way at DSO.
- [ ] **Asks for a person.** "I want to talk to a human." → sends you to the reception desk.
- [ ] **Impatient visitor.** "Just tell me quickly!" → apologises briefly, answers in one sentence.
- [ ] **Remembers.** Give your name early on, later ask "Can you check me in?" It uses the name without asking again.
- [ ] **Never asks for a phone number** when sending the route.

## Robot-only checks

- [ ] It hears you from about 1 metre away in the noisy room.
- [ ] It doesn't interrupt itself. If it does, run the bridge with `HALF_DUPLEX=1`.
- [ ] Replies start within about 2 seconds.
- [ ] Arabic pronunciation sounds natural to an Arabic speaker.
