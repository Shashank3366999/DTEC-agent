# Reception web app

A small mock reception system. The ElevenLabs agent calls it to **check in a visitor** and **send a route to the visitor's phone**. A screen next to the robot shows both live.

No packages to install. Needs Node 18 or newer.

## Pages

| Page | What it is |
|---|---|
| `/screen` | Reception screen. Open it on a laptop or monitor next to the robot. Shows arrivals and a QR code for the latest route. |
| `/r/<id>` | The route card the visitor opens on their phone (from the QR code). Has an "Open in Google Maps" button. |
| `/kiosk?agent=AGENT_ID` | Laptop demo: talk to the agent in the browser, with the reception screen beside it. Our backup if the robot fails. Needs a public agent. |

## Tool endpoints (called by the agent)

| Endpoint | Body fields |
|---|---|
| `POST /api/check-in` | `host_company` (required), `visitor_name`, `meeting_time`, `language` |
| `POST /api/send-route` | `destination` (required), `steps` (required, separated by `\|`), `language`, `maps_query` |
| `POST /api/reset` | clears all data (use before filming) |

If `TOOL_SECRET` is set, every POST must send the header `x-tool-secret: <secret>`.

## Run on your laptop

```bash
cd webapp
TOOL_SECRET=pick-a-long-random-word node server.js
# open http://localhost:3000/screen
npm test   # runs the smoke test
```

Try it without the agent:

```bash
curl -X POST localhost:3000/api/check-in -H 'content-type: application/json' \
  -H 'x-tool-secret: pick-a-long-random-word' \
  -d '{"visitor_name":"Sara","host_company":"Oraseya Capital","meeting_time":"15:00","language":"en"}'
```

## Put it online (the agent needs a public URL)

### Option A: Render (recommended)
1. Push this repo to GitHub (private is fine).
2. On render.com: **New → Web Service** → pick the repo.
3. **Root directory:** `webapp` · **Build command:** leave empty · **Start command:** `node server.js`
4. **Environment variables:** `TOOL_SECRET` = a long random word. `PUBLIC_URL` = the Render URL once you have it, for example `https://hercules-xyz.onrender.com`.
5. Deploy, then open `<url>/health`. It should say `{"ok":true}`.

> The free Render plan goes to sleep when unused and takes about a minute to wake up. **Open `/screen` a few minutes before every robot slot and the demo** so it is awake. Keeping the screen open also keeps it awake.

### Option B: quick tunnel from a laptop (fastest, for testing)
Run the server on a laptop, then expose it:
```bash
npx localtunnel --port 3000
# or, if cloudflared is installed:
cloudflared tunnel --url http://localhost:3000
```
Use the printed https URL in the agent's tools. The URL changes every time, and the laptop must stay on, so use Render for the real demo.

## Before filming the demo

```bash
curl -X POST <url>/api/reset -H 'x-tool-secret: <secret>'
```
That clears the test check-ins so the screen starts empty.

## Notes

- Data is kept in memory and in `data.json`. All of it is demo data. Never put real visitor details in it.
- Arabic is shown right-to-left automatically.
- The QR code uses a small library from cdnjs. If the screen has no internet, it shows the link as text instead.
