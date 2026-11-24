# ElevenLabs agent setup (step by step)

Do this once the credits are claimed. Button names can move a little in the ElevenLabs app; look for the same words.

## 1. Create the agent

1. Go to elevenlabs.io → **Agents** → **Create agent** → start from a **blank** agent.
2. Name: `DSO Visitor Guide (Team Hercules)`.

## 2. Agent tab

1. **First message:** paste the English text from `first_message.md`.
2. **System prompt:** paste everything in `system_prompt.md`.
3. **Default language:** English. **Additional languages:** add **Arabic**. If it lets you set a first message per language, use the Arabic one from `first_message.md`.
4. **LLM:** pick a fast model. Short replies matter more than a big model.
5. **Knowledge base:** upload `knowledge_base.md`. Upload it again every time we add new directions.

## 3. Voice tab

1. Pick a voice that sounds good in **both Arabic and English**. Test both before choosing.
2. Use a multilingual voice model. Ask the ElevenLabs mentors which voice works best for Arabic.

## 4. Audio format (the robot needs this)

In the **Advanced** tab (or Voice tab, depending on the version):
- **User input audio format:** `PCM 16000 Hz`
- **Agent output (TTS) audio format:** `PCM 16000 Hz`

If this is wrong, the robot's speaker stays silent.

## 5. Tools

### System tool: language detection
Add the **Language detection** system tool. This lets the agent switch between Arabic and English mid-conversation.

### Webhook tool 1: `check_in_visitor`

- **Type:** Webhook
- **Name:** `check_in_visitor`
- **Description:** Tell the host company that the visitor has arrived. Use only after the visitor agrees.
- **Method:** POST
- **URL:** `https://<OUR-WEB-APP>/api/check-in`
- **Headers:** `x-tool-secret` = the secret we set on the web app (see `webapp/README.md`). Store it as a secret if the app offers that.
- **Body parameters:**

| Key | Type | Required | Description |
|---|---|---|---|
| `host_company` | string | yes | The company the visitor is meeting, for example "Oraseya Capital". |
| `visitor_name` | string | no | The visitor's first name as they said it. Use "Guest" if they don't want to say. |
| `meeting_time` | string | no | The meeting time as the visitor said it, in 24-hour form, for example "15:00". |
| `language` | string | yes | The language the visitor is speaking: "ar" or "en". |

### Webhook tool 2: `send_route_to_phone`

- **Type:** Webhook
- **Name:** `send_route_to_phone`
- **Description:** Show a route card with a QR code on the screen next to the robot so the visitor can open the directions on their phone. Use only after the visitor agrees.
- **Method:** POST
- **URL:** `https://<OUR-WEB-APP>/api/send-route`
- **Headers:** `x-tool-secret` = same secret as above.
- **Body parameters:**

| Key | Type | Required | Description |
|---|---|---|---|
| `destination` | string | yes | The place the visitor is going, for example "Oraseya Capital, Dtec TechnoHub 1, first floor". |
| `steps` | string | yes | The directions you just gave, as short steps separated by " \| ", in the visitor's language. |
| `language` | string | yes | "ar" or "en". |
| `maps_query` | string | no | Only for places outside Dtec: a search text for Google Maps, for example "DSO Masjid Techno Point Dubai Silicon Oasis". |

### Optional
- Add the **End conversation** system tool so the agent can end the chat after saying goodbye.

## 6. Make it reachable

- **For the robot:** in the Advanced or Security settings, decide **public** (only the agent ID is needed, simplest on the robot) or **private** (the robot also needs the API key). For the hackathon, public is simplest.
- **The laptop demo page** (`/kiosk`) uses the ElevenLabs widget, which only works with a public agent.

## 7. Test before the robot

1. Use the **Test AI agent** button in ElevenLabs and talk to it.
2. Go through `test_conversations.md` and tick off each test.
3. Open the reception screen (`/screen`) at the same time and check that check-ins and routes show up.

## 8. Write down

- **Agent ID:** send it to the person at the robot.
- **Workspace ID:** ElevenLabs may ask for it.
- Never put the **API key** in the repo, this file or a chat.
