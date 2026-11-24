// Team Hercules - mock reception backend for the AI Voice Navigator.
//
// The ElevenLabs agent calls two webhook tools here:
//   POST /api/check-in     -> tells "reception" a visitor has arrived
//   POST /api/send-route   -> makes a route card the visitor opens on their phone
// Screens:
//   /screen   reception screen next to the robot (live, shows check-ins + QR for the latest route)
//   /r/<id>   the route card the visitor opens on their phone
//   /kiosk    laptop demo: the ElevenLabs widget next to the live screen (backup demo)
//
// No npm packages needed. Run: node server.js   (Node 18+)
// Environment variables (all optional):
//   PORT         port to listen on (default 3000)
//   TOOL_SECRET  if set, tool calls must send header  x-tool-secret: <value>
//   PUBLIC_URL   base URL used in links and QR codes, e.g. https://hercules.onrender.com
//   DATA_FILE    where to save data (default ./data.json)

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 3000);
const TOOL_SECRET = (process.env.TOOL_SECRET || "").trim();
const PUBLIC_URL = (process.env.PUBLIC_URL || "").trim().replace(/\/+$/, "");
const DATA_FILE = process.env.DATA_FILE || path.join(__dirname, "data.json");
const PUBLIC_DIR = path.join(__dirname, "public");
const MAX_ITEMS = 50;
const MAX_BODY = 32 * 1024;

// ------------------------------------------------------------------ storage
let db = { checkins: [], routes: [], operator_calls: [] };
try {
  db = { checkins: [], routes: [], operator_calls: [], ...JSON.parse(fs.readFileSync(DATA_FILE, "utf8")) };
} catch {
  /* first run: start empty */
}
function save() {
  fs.writeFile(DATA_FILE, JSON.stringify(db, null, 2), () => {});
}

// ------------------------------------------------------------------ live updates (Server-Sent Events)
const listeners = new Set();
function broadcast(event, data) {
  const msg = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of listeners) res.write(msg);
}
setInterval(() => {
  for (const res of listeners) res.write(": keep-alive\n\n");
}, 20000);

// ------------------------------------------------------------------ helpers
const clean = (v, max = 300) =>
  typeof v === "string" ? v.trim().slice(0, max) : v == null ? "" : String(v).trim().slice(0, max);

function baseUrl(req) {
  if (PUBLIC_URL) return PUBLIC_URL;
  const proto = (req.headers["x-forwarded-proto"] || "http").split(",")[0].trim();
  return `${proto}://${req.headers.host}`;
}

function sendJson(res, status, obj) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "access-control-allow-origin": "*",
  });
  res.end(JSON.stringify(obj));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new Error("body too large"));
        req.destroy();
      } else chunks.push(c);
    });
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      if (!raw) return resolve({});
      const type = req.headers["content-type"] || "";
      try {
        if (type.includes("application/x-www-form-urlencoded")) {
          resolve(Object.fromEntries(new URLSearchParams(raw)));
        } else {
          resolve(JSON.parse(raw));
        }
      } catch {
        reject(new Error("invalid JSON"));
      }
    });
    req.on("error", reject);
  });
}

function authorized(req) {
  if (!TOOL_SECRET) return true;
  // The laptop demo page (/kiosk) runs on this same site and calls the tools from the browser.
  // Browsers set Sec-Fetch-Site themselves; page scripts cannot fake it. All data here is demo data.
  if (req.headers["sec-fetch-site"] === "same-origin") return true;
  const got = String(req.headers["x-tool-secret"] || "");
  const a = Buffer.from(got);
  const b = Buffer.from(TOOL_SECRET);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

const isArabic = (lang, text = "") => /^ar/i.test(lang) || /[؀-ۿ]/.test(text);

// Steps arrive as one string (webhook body fields are plain strings).
// Accept newlines, ";", "|" or "1) 2)" / "1. 2." numbering as separators.
function splitSteps(text) {
  return clean(text, 2000)
    .split(/\r?\n|;|\||\s(?=\d+[.)]\s)/)
    .map((s) => s.replace(/^\s*\d+[.)]\s*/, "").trim())
    .filter(Boolean)
    .slice(0, 12);
}

function newId() {
  return crypto.randomBytes(4).toString("hex");
}

function pushLimited(list, item) {
  list.unshift(item);
  if (list.length > MAX_ITEMS) list.length = MAX_ITEMS;
}

// ------------------------------------------------------------------ tool handlers
function handleCheckIn(body) {
  const visitor = clean(body.visitor_name, 80) || "Guest";
  const company = clean(body.host_company, 120);
  const time = clean(body.meeting_time, 40);
  const language = clean(body.language, 10) || "en";
  if (!company) {
    return [400, { ok: false, message: "host_company is required. Ask the visitor which company they are visiting." }];
  }
  const item = {
    id: newId(),
    visitor_name: visitor,
    host_company: company,
    meeting_time: time,
    language,
    note: clean(body.note, 200),
    created_at: new Date().toISOString(),
    demo: true,
  };
  pushLimited(db.checkins, item);
  save();
  broadcast("checkin", item);
  const ar = isArabic(language);
  return [
    200,
    {
      ok: true,
      checkin_id: item.id,
      message: ar
        ? `تم إبلاغ ${company} بوصول ${visitor}.`
        : `${company} has been told that ${visitor} has arrived${time ? ` for the ${time} meeting` : ""}.`,
      note_for_agent:
        "Tell the visitor in one short sentence that their host has been notified. This is a demo reception system.",
    },
  ];
}

function handleSendRoute(body, req) {
  const destination = clean(body.destination, 120);
  const steps = splitSteps(body.steps);
  const language = clean(body.language, 10) || "en";
  if (!destination || steps.length === 0) {
    return [400, { ok: false, message: "destination and steps are both required." }];
  }
  const item = {
    id: newId(),
    destination,
    steps,
    language,
    visitor_name: clean(body.visitor_name, 80),
    maps_query: clean(body.maps_query, 160),
    created_at: new Date().toISOString(),
    demo: true,
  };
  pushLimited(db.routes, item);
  save();
  const url = `${baseUrl(req)}/r/${item.id}`;
  broadcast("route", { ...item, url });
  const ar = isArabic(language, destination);
  return [
    200,
    {
      ok: true,
      route_id: item.id,
      route_url: url,
      message: ar
        ? "المسار جاهز. امسح رمز QR على الشاشة بجانبي لفتحه على هاتفك."
        : "The route is ready. Scan the QR code on the screen next to me to open it on your phone.",
      note_for_agent: "Tell the visitor to scan the QR code on the screen next to the robot. Do not read the URL out loud.",
    },
  ];
}

function handleOperator(body) {
  const language = clean(body.language, 10) || "en";
  const item = {
    id: newId(),
    reason: clean(body.reason, 200) || "Visitor asked for help",
    visitor_name: clean(body.visitor_name, 80),
    language,
    created_at: new Date().toISOString(),
    demo: true,
  };
  pushLimited(db.operator_calls, item);
  save();
  broadcast("operator", item);
  return [
    200,
    {
      ok: true,
      call_id: item.id,
      message: isArabic(language)
        ? "تم تنبيه موظف الاستقبال."
        : "A colleague at reception has been alerted.",
    },
  ];
}

// ------------------------------------------------------------------ static files
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};
function serveFile(res, file) {
  const full = path.join(PUBLIC_DIR, file);
  if (!full.startsWith(PUBLIC_DIR)) return sendJson(res, 404, { ok: false });
  fs.readFile(full, (err, buf) => {
    if (err) return sendJson(res, 404, { ok: false, message: "not found" });
    res.writeHead(200, { "content-type": TYPES[path.extname(full)] || "application/octet-stream" });
    res.end(buf);
  });
}

// ------------------------------------------------------------------ router
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const p = url.pathname.replace(/\/+$/, "") || "/";

  try {
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,POST,OPTIONS",
        "access-control-allow-headers": "content-type,x-tool-secret",
      });
      return res.end();
    }

    // --- tools called by the ElevenLabs agent
    if (req.method === "POST" && (p === "/api/check-in" || p === "/api/send-route" || p === "/api/operator")) {
      if (!authorized(req)) return sendJson(res, 401, { ok: false, message: "wrong or missing x-tool-secret" });
      const body = await readBody(req);
      const [status, out] =
        p === "/api/check-in" ? handleCheckIn(body) : p === "/api/operator" ? handleOperator(body) : handleSendRoute(body, req);
      console.log(new Date().toISOString(), p, status, JSON.stringify(body).slice(0, 300));
      return sendJson(res, status, out);
    }

    if (req.method === "POST" && p === "/api/reset") {
      if (!authorized(req)) return sendJson(res, 401, { ok: false, message: "wrong or missing x-tool-secret" });
      db = { checkins: [], routes: [], operator_calls: [] };
      save();
      broadcast("reset", {});
      return sendJson(res, 200, { ok: true });
    }

    // --- data for the screens
    if (req.method === "GET" && p === "/api/state") {
      const base = baseUrl(req);
      return sendJson(res, 200, {
        checkins: db.checkins.slice(0, 20),
        operator_calls: db.operator_calls.slice(0, 5),
        routes: db.routes.slice(0, 20).map((r) => ({ ...r, url: `${base}/r/${r.id}` })),
      });
    }
    if (req.method === "GET" && p.startsWith("/api/route/")) {
      const r = db.routes.find((x) => x.id === p.split("/").pop());
      return r ? sendJson(res, 200, r) : sendJson(res, 404, { ok: false, message: "route not found" });
    }
    if (req.method === "GET" && p === "/api/events") {
      res.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
        "x-accel-buffering": "no",
      });
      res.write("retry: 2000\n\n");
      listeners.add(res);
      req.on("close", () => listeners.delete(res));
      return;
    }
    if (req.method === "GET" && p === "/health") return sendJson(res, 200, { ok: true });

    // --- pages
    if (req.method === "GET") {
      if (p === "/") return serveFile(res, "index.html");
      if (p === "/screen") return serveFile(res, "screen.html");
      if (p === "/kiosk") return serveFile(res, "kiosk.html");
      if (p === "/test") return serveFile(res, "test.html");
      if (p.startsWith("/r/")) return serveFile(res, "route.html");
      if (/^\/[\w.-]+\.(css|js|json|svg|png|ico)$/.test(p)) return serveFile(res, p.slice(1));
    }
    sendJson(res, 404, { ok: false, message: "not found" });
  } catch (err) {
    console.error(err);
    sendJson(res, 400, { ok: false, message: String(err.message || err) });
  }
});

server.listen(PORT, () => {
  console.log(`Hercules reception backend on http://localhost:${PORT}`);
  console.log(`  reception screen: http://localhost:${PORT}/screen`);
  console.log(`  laptop demo:      http://localhost:${PORT}/kiosk?agent=YOUR_AGENT_ID`);
  console.log(TOOL_SECRET ? "  tool calls need header x-tool-secret" : "  WARNING: TOOL_SECRET not set, tool calls are open");
});
