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
  env: { ...process.env, PORT: String(PORT), TOOL_SECRET: SECRET, DATA_FILE: dataFile, PUBLIC_URL: "", ELEVENLABS_WEBHOOK_SECRET: "whsec_test" },
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

  await check("operator alert works and shows in state", async () => {
    const r = await post("/api/operator", { reason: "Visitor disputes a fee", language: "en" });
    assert.equal(r.status, 200);
    const s = await (await fetch(base + "/api/state")).json();
    assert.equal(s.operator_calls[0].reason, "Visitor disputes a fee");
  });

  await check("same-origin browser call works without the secret", async () => {
    const r = await fetch(base + "/api/operator", {
      method: "POST",
      headers: { "content-type": "application/json", "sec-fetch-site": "same-origin" },
      body: JSON.stringify({ reason: "kiosk test" }),
    });
    assert.equal(r.status, 200);
  });

  await check("live route: needs the secret, is cleaned, shows in state", async () => {
    assert.equal((await post("/api/nav", { walking: true }, "")).status, 401);
    const r = await post("/api/nav", { walking: true, between: ["start", "junction"], path: ["start", "junction"], heading: 0, instruction: "Walk straight.", step: "x", extra: 1 });
    assert.equal(r.status, 200);
    const { nav } = await (await fetch(base + "/api/state")).json();
    assert.equal(nav.instruction, "Walk straight.");
    assert.deepEqual(nav.path, ["start", "junction"]);
    assert.equal(nav.step, 0);
    assert.equal(nav.extra, undefined);
  });

  await check("post-call webhook: signed only, lands in the trip log", async () => {
    const { createHmac } = await import("node:crypto");
    const payload = JSON.stringify({ type: "post_call_transcription", data: { conversation_id: "conv_1", agent_id: "a", metadata: { call_duration_secs: 61 },
      analysis: { transcript_summary: "Took a visitor to the kitchen.", call_successful: "success",
        evaluation_criteria_results: { no_invented_directions: { result: "success" }, stayed_brief: { result: "failure" } },
        data_collection_results: { destination: { value: "kitchen" }, visitor_language: { value: "ar" }, unknown_requests: { value: "mosque, pharmacy" }, steps_given: { value: 2 }, destination_changed: { value: false } } } } });
    const t = Math.floor(Date.now() / 1000);
    const sig = `t=${t},v0=${createHmac("sha256", "whsec_test").update(`${t}.${payload}`).digest("hex")}`;
    const bad = await fetch(base + "/api/elevenlabs/post-call", { method: "POST", headers: { "content-type": "application/json", "elevenlabs-signature": `t=${t},v0=deadbeef` }, body: payload });
    assert.equal(bad.status, 401);
    const good = await fetch(base + "/api/elevenlabs/post-call", { method: "POST", headers: { "content-type": "application/json", "elevenlabs-signature": sig }, body: payload });
    assert.equal(good.status, 200);
    const s = await (await fetch(base + "/api/state")).json();
    assert.equal(s.trips[0].destination, "kitchen");
    assert.equal(s.trips[0].unknown_requests, "mosque, pharmacy");
    assert.equal(s.trips[0].scores.stayed_brief, "failure");
    assert.equal(s.trips[0].steps_given, 2);
  });

  await check("state lists check-ins and routes, newest first", async () => {
    const s = await (await fetch(base + "/api/state")).json();
    assert.equal(s.checkins.length, 2);
    assert.equal(s.checkins[0].visitor_name, "سارة");
    assert.equal(s.routes[0].destination, "DSO Masjid");
  });

  await check("pages load", async () => {
    for (const p of ["/", "/screen", "/live", "/walk", "/markers", "/nav.js", "/map.js", "/profile.json", "/kiosk", "/test", "/styles.css", "/screen.js", new URL(routeUrl).pathname]) {
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
    assert.equal(s.nav, null);
    assert.equal(s.trips.length, 0);
  });

  ctrl.abort();
  await sse;
} finally {
  srv.kill();
}

console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
process.exit(failed ? 1 : 0);
