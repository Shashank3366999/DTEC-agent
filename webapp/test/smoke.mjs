// Smoke test: starts the server on a free port, calls both tools like the
// ElevenLabs agent would, and checks the screens get the data.
// Run: npm test   (from the webapp folder)
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3900 + Math.floor(Math.random() * 90);
const SECRET = "test-secret";
const base = `http://localhost:${PORT}`;
const dataFile = path.join(mkdtempSync(path.join(tmpdir(), "hercules-")), "data.json");

const srv = spawn(process.execPath, [path.join(here, "..", "server.js")], {
  env: { ...process.env, PORT: String(PORT), TOOL_SECRET: SECRET, DATA_FILE: dataFile, PUBLIC_URL: "" },
  stdio: ["ignore", "pipe", "inherit"],
});
await new Promise((ok) => srv.stdout.once("data", ok));

const post = (p, body, secret = SECRET) =>
  fetch(base + p, {
    method: "POST",
    headers: { "content-type": "application/json", ...(secret ? { "x-tool-secret": secret } : {}) },
    body: JSON.stringify(body),
  });

let failed = 0;
async function check(name, fn) {
  try {
    await fn();
    console.log("ok   ", name);
  } catch (e) {
    failed++;
    console.log("FAIL ", name, "\n     ", e.message);
  }
}

try {
  // listen to live events while we call the tools
  const events = [];
  const ctrl = new AbortController();
  const sse = fetch(base + "/api/events", { signal: ctrl.signal }).then(async (r) => {
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      events.push(dec.decode(value));
    }
  }).catch(() => {});
  await new Promise((r) => setTimeout(r, 200));

  await check("tool call without secret is refused", async () => {
    const r = await post("/api/check-in", { host_company: "X" }, "");
    assert.equal(r.status, 401);
  });

  await check("check-in needs host_company", async () => {
    const r = await post("/api/check-in", { visitor_name: "Sara" });
    assert.equal(r.status, 400);
  });

  await check("check-in works (English)", async () => {
    const r = await post("/api/check-in", {
      visitor_name: "Sara (demo)", host_company: "Oraseya Capital", meeting_time: "15:00", language: "en",
    });
    assert.equal(r.status, 200);
    const j = await r.json();
    assert.equal(j.ok, true);
    assert.match(j.message, /Oraseya Capital/);
  });

  await check("check-in reply is Arabic for an Arabic visitor", async () => {
    const r = await post("/api/check-in", { visitor_name: "سارة", host_company: "أوراسيا كابيتال", language: "ar" });
    const j = await r.json();
    assert.match(j.message, /[؀-ۿ]/);
  });

  let routeUrl;
  await check("send-route splits steps and returns a link", async () => {
    const r = await post("/api/send-route", {
      destination: "Oraseya Capital, Dtec TechnoHub 1, first floor",
      steps: "1. Walk to the lifts on your left. 2. Go to the first floor. 3. Turn right.",
      language: "en",
    });
    assert.equal(r.status, 200);
    const j = await r.json();
    assert.ok(j.route_url.includes("/r/"));
    routeUrl = j.route_url;
    const route = await (await fetch(base + "/api/route/" + j.route_id)).json();
    assert.equal(route.steps.length, 3);
    assert.equal(route.steps[0], "Walk to the lifts on your left.");
  });

  await check("send-route accepts newline steps and form encoding", async () => {
    const r = await fetch(base + "/api/send-route", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded", "x-tool-secret": SECRET },
      body: new URLSearchParams({ destination: "DSO Masjid", steps: "Exit the main door\nTaxi to Techno Point", language: "en" }),
    });
    const j = await r.json();
    const route = await (await fetch(base + "/api/route/" + j.route_id)).json();
    assert.equal(route.steps.length, 2);
  });

  await check("send-route needs steps", async () => {
    const r = await post("/api/send-route", { destination: "Somewhere" });
    assert.equal(r.status, 400);
  });

  await check("state lists check-ins and routes, newest first", async () => {
    const s = await (await fetch(base + "/api/state")).json();
    assert.equal(s.checkins.length, 2);
    assert.equal(s.checkins[0].visitor_name, "سارة");
    assert.equal(s.routes[0].destination, "DSO Masjid");
  });

  await check("pages load", async () => {
    for (const p of ["/", "/screen", "/kiosk", "/test", "/styles.css", "/screen.js", new URL(routeUrl).pathname]) {
      const r = await fetch(base + p);
      assert.equal(r.status, 200, p);
    }
  });

  await check("live screen received events", async () => {
    await new Promise((r) => setTimeout(r, 200));
    const all = events.join("");
    assert.match(all, /event: checkin/);
    assert.match(all, /event: route/);
  });

  await check("reset clears everything", async () => {
    const r = await post("/api/reset", {});
    assert.equal(r.status, 200);
    const s = await (await fetch(base + "/api/state")).json();
    assert.equal(s.checkins.length + s.routes.length, 0);
  });

  ctrl.abort();
  await sse;
} finally {
  srv.kill();
}

console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
