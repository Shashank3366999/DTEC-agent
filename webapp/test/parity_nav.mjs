// Plays the same random trips through nav.js and navigator.py and checks every answer is identical,
// on the real profile. Run from the webapp folder: node test/parity_nav.mjs   (needs python3)
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
require(path.join(here, "..", "public", "oasis.js"));
require(path.join(here, "..", "public", "nav.js"));
const sdk = path.join(here, "..", "..", "sdk");
const profilePath = path.join(sdk, "profiles", "dtec_floor.json");
const profile = JSON.parse(readFileSync(profilePath, "utf8"));

let seed = 7; // mulberry32
const rnd = (n) => {
  seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return Math.floor((((t ^ (t >>> 14)) >>> 0) / 4294967296) * n);
};
const pick = (l) => l[rnd(l.length)];
const places = profile.places.map((p) => p.id), nodes = profile.floor.nodes.map((n) => n.id);
const langs = ["en", "ar", "hi", "ur", "ar-AE"];
const asks = ["a quiet place to take a call", "أبي مكان هادي أسوي فيه مكالمة", "الكابينة الثانية", "second booth", "I have a meeting",
  "conferense room", "मुझे चाय चाहिए", "दूसरा बूथ", "tables", "where is the mosque", "", "I'm hungry", "قاعة المؤتمرات", "मीटिंग"];
const spots = [...nodes, ...places, "I see the main junction", "next to the kitchen", "nowhere", ""];

const script = [];
for (let trip = 0; trip < 150; trip++) {
  script.push(["reset"]);
  for (let i = 0; i < 14; i++) {
    const k = rnd(12);
    if (k < 2) script.push(["find", pick(asks), pick(langs)]);
    else if (k < 5) script.push(["start", pick(places), pick(langs), pick(["", "", pick(nodes), "the kitchen"]), pick([true, false, false]), pick(["", "", pick(spots)])]);
    else if (k < 9) script.push(["done", pick([true, true, true, false])]); // true = the current step, false = an old one
    else if (k < 10) script.push(["at", pick(spots), pick(["", pick(nodes)])]);
    else if (k < 11) script.push(["marker", pick(nodes)]);
    else script.push([pick(["status", "cancel"])]);
  }
}

const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(sdk)})
from oasis_voice.profile import load_profile
from oasis_voice.navigator import Navigator, VISITOR_LINES
n = Navigator(load_profile(${JSON.stringify(profilePath)}))
out = []
for s in json.loads(sys.stdin.read()):
    k = s[0]
    r = (n.reset() if k == "reset" else n.find(s[1], s[2]) if k == "find" else n.start_route(s[1], s[2], s[3], s[4], s[5]) if k == "start"
         else n.step_done(n.step_id if s[1] else n.step_id - 1) if k == "done" else n.update_position(s[1], s[2]) if k == "at"
         else n.update_position(s[1], source="marker") if k == "marker" else n.status() if k == "status" else n.cancel())
    out.append([r, n.snapshot()])
print(json.dumps({"lines": VISITOR_LINES, "out": out}, ensure_ascii=False))
`;
const { lines, out } = JSON.parse(execFileSync("python3", ["-c", py], { input: JSON.stringify(script), maxBuffer: 1e9 }).toString());
profile.visitor_lines = lines;
const n = new globalThis.OasisNav.Navigator(profile);
const canon = (v) => JSON.stringify(v, (k, x) =>
  typeof x === "number" ? Math.round(x * 1e6) / 1e6 :
  x && typeof x === "object" && !Array.isArray(x) ? Object.fromEntries(Object.entries(x).sort(([a], [b]) => (a < b ? -1 : 1))) : x);
let failed = 0;
const seen = {};
script.forEach((s, i) => {
  const k = s[0];
  const r = k === "reset" ? n.reset() : k === "find" ? n.find(s[1], s[2]) : k === "start" ? n.startRoute(s[1], s[2], s[3], s[4], s[5])
    : k === "done" ? n.stepDone(s[1] ? n.stepId : n.stepId - 1) : k === "at" ? n.updatePosition(s[1], s[2])
    : k === "marker" ? n.updatePosition(s[1], "", "marker") : k === "status" ? n.status() : n.cancel();
  seen[r.status] = (seen[r.status] || 0) + 1;
  if (canon([r, n.snapshot()]) !== canon(out[i]) && failed++ < 3) console.log("DIFF at", i, s, "\n js:", canon([r, n.snapshot()]), "\n py:", canon(out[i]));
});
console.log(failed ? `${failed} of ${script.length} differ` : `all ${script.length} navigation events match the SDK`, JSON.stringify(seen));
const must = ["started", "changed", "next_step", "arrived", "need_position", "rerouted", "on_track", "located",
  "same_step", "already_going", "cancelled", "walking", "standing", "group", "ambiguous", "found", "ask_first", "retry_in_english", "not_found"];
const missed = must.filter((x) => !seen[x]);
if (missed.length) console.log("never reached:", missed.join(", "));
process.exit(failed || missed.length ? 1 : 0);
