// Checks that the browser directory (public/oasis.js) answers exactly like the SDK (sdk/oasis_voice/directory.py).
// Run from the webapp folder: node test/parity.mjs   (needs python3)
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
require(path.join(here, "..", "public", "oasis.js")); // browser script: attaches itself to globalThis.Oasis
const Oasis = globalThis.Oasis;
const sdk = path.join(here, "..", "..", "sdk");
const profilePath = path.join(sdk, "profiles", "dtec_navigator.json");
const profile = JSON.parse(readFileSync(profilePath, "utf8"));

const queries = [
  ["where is the bank", "en"], ["Where's Orasia Capital", "en"], ["I need coffee", "en"], ["where can I pray", "en"],
  ["وين المصعد", "ar"], ["أبي أصلي", "ar"], ["where is the mosque", "en"], ["where is google office", "en"],
  ["toilet please", "en"], ["Dtec café", "en"], ["the mall", "ar"], ["I feel sick", "en"], ["مسجد", "ar"],
  ["first floor", "en"], ["pharmacy", "ar"], ["taxi", "en"], ["أوراسيا كابيتال", "ar"], ["summit agenda", "en"],
  ["Oraseya", "en"], ["lifts", "ar"], ["random words here", "en"], ["", "en"],
];

const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(sdk)})
from oasis_voice.profile import load_profile
from oasis_voice.directory import Directory
d = Directory(load_profile(${JSON.stringify(profilePath)}))
qs = json.loads(sys.stdin.read())
print(json.dumps([d.lookup(q, l) for q, l in qs], ensure_ascii=False))
`;
const pyOut = JSON.parse(execFileSync("python3", ["-c", py], { input: JSON.stringify(queries) }).toString());
const dir = new Oasis.Directory(profile);
let failed = 0;
queries.forEach(([q, l], i) => {
  const a = JSON.stringify(dir.lookup(q, l));
  const b = JSON.stringify(pyOut[i]);
  if (a !== b) {
    failed++;
    console.log("DIFF", JSON.stringify(q), "\n  js:", a, "\n  py:", b);
  }
});
console.log(failed ? `${failed} of ${queries.length} differ` : `all ${queries.length} lookups match the SDK`);
process.exit(failed ? 1 : 0);
