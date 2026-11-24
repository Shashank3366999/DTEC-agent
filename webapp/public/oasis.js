// Oasis Voice: browser version of the SDK's deterministic directory and client tools.
// Mirrors sdk/oasis_voice/directory.py and actions.py so the laptop demo behaves like the robot.
// Kept in sync by webapp/test/parity.mjs.
(function (root) {
  const STOP = new Set(["the", "a", "an", "to", "is", "where", "please", "find", "go", "i", "want", "need", "how", "do", "get"]);
  const FOLD = { "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي", "ٱ": "ا", "ـ": "" };
  const MAX_OPTIONS = 4;

  function normalize(text) {
    let t = String(text || "").toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");
    t = t.replace(/[ةىؤئٱـ]/g, (c) => FOLD[c]);
    t = t.replace(/[^\p{L}\p{N}_\s]/gu, " ");
    return t.split(/\s+/).filter(Boolean).map((w) => (w.length > 3 && w.startsWith("ال") ? w.slice(2) : w)).join(" ");
  }

  // Ratcliff/Obershelp similarity, same as Python's difflib.SequenceMatcher.ratio()
  function matches(a, b) {
    if (!a.length || !b.length) return 0;
    let best = 0, ai = 0, bj = 0;
    for (let i = 0; i < a.length; i++) {
      for (let j = 0; j < b.length; j++) {
        let k = 0;
        while (i + k < a.length && j + k < b.length && a[i + k] === b[j + k]) k++;
        if (k > best) { best = k; ai = i; bj = j; }
      }
    }
    if (!best) return 0;
    return best + matches(a.slice(0, ai), b.slice(0, bj)) + matches(a.slice(ai + best), b.slice(bj + best));
  }
  const ratio = (a, b) => (a.length + b.length ? (2 * matches(a, b)) / (a.length + b.length) : 1);

  function fuzzy(words, alias) {
    const n = alias.split(" ").length;
    let best = 0;
    for (let i = 0; i < Math.max(1, words.length - n + 1); i++) best = Math.max(best, ratio(words.slice(i, i + n).join(" "), alias));
    return best;
  }

  const contains = (hay, needle) => (" " + hay + " ").includes(" " + needle + " ");
  const textFor = (v, lang) => (v && typeof v === "object" ? v[lang] || v.en || "" : v || "");

  function dubaiNow() {
    const d = new Date(Date.now() + 4 * 3600e3);
    return { hour: d.getUTCHours(), minute: d.getUTCMinutes() };
  }

  function openNow(hours, now) {
    if (!hours) return null;
    if (hours === "24h") return true;
    now = now || dubaiNow();
    const [start, end] = hours.split("-");
    const [sh, sm] = start.split(":").map(Number);
    const [eh, em] = end.split(":").map(Number);
    let s = sh * 60 + sm, e = eh * 60 + em;
    const t = now.hour * 60 + now.minute;
    if (e === 0) e = 24 * 60;
    if (s <= e) return s <= t && t < e;
    return t >= s || t < e;
  }

  class Directory {
    constructor(profile) {
      this.profile = profile;
      this.places = {};
      this.index = [];
      for (const p of profile.places) {
        this.places[p.id] = p;
        for (const names of Object.values(p.names || {})) for (const n of names) this.index.push([p.id, normalize(n), "name"]);
        for (const kws of Object.values(p.keywords || {})) for (const k of kws) this.index.push([p.id, normalize(k), "keyword"]);
      }
    }

    lang(language) {
      const code = String(language || "").toLowerCase().slice(0, 2);
      return [this.profile.languages.default, ...(this.profile.languages.others || [])].includes(code) ? code : "en";
    }

    match(query) {
      const q = normalize(query);
      let words = q.split(" ").filter((w) => w && !STOP.has(w));
      if (!words.length) words = q.split(" ").filter(Boolean);
      const qClean = words.join(" ");
      const scores = new Map();
      for (const [pid, phrase, kind] of this.index) {
        if (!phrase) continue;
        const n = phrase.split(" ").length;
        let score = 0;
        if (contains(q, phrase) || contains(qClean, phrase)) score = (kind === "name" ? 10 : 3) + n;
        else if (kind === "name" && phrase.length >= 5 && fuzzy(words, phrase) >= 0.82) score = 6 + n;
        if (score > (scores.get(pid) || 0)) scores.set(pid, score);
      }
      return scores;
    }

    lookup(query = "", language = "en", placeId = "") {
      const lang = this.lang(language);
      if (placeId && this.places[placeId]) return this.found(this.places[placeId], lang);
      const scores = this.match(query);
      if (!scores.size) {
        return { status: "not_found", query,
          say: "You don't have this place. Say you don't know, and offer to call the operator or send the visitor to the reception desk. Do not guess." };
      }
      const top = Math.max(...scores.values());
      const best = [...scores].filter(([, s]) => s === top).map(([id]) => id);
      let candidates;
      if (top >= 6) {
        if (best.length === 1) return this.found(this.places[best[0]], lang);
        candidates = best;
      } else {
        candidates = [...scores].filter(([, s]) => s >= 3).map(([id]) => id);
        if (candidates.length === 1) return this.found(this.places[candidates[0]], lang);
      }
      candidates.sort((a, b) => {
        const pa = this.places[a], pb = this.places[b];
        return (+!!pa.outside - +!!pb.outside) || ((pa.walk_minutes || 99) - (pb.walk_minutes || 99));
      });
      return {
        status: "ambiguous", query,
        options: candidates.slice(0, MAX_OPTIONS).map((id) => ({ place_id: id, name: this.name(this.places[id], lang), where: textFor(this.places[id].where, lang) })),
        say: "Several places match. Ask ONE short question naming the options, then call lookup_place again with the chosen place_id.",
      };
    }

    name(place, lang) {
      const names = place.names || {};
      return (names[lang] && names[lang].length ? names[lang] : names.en)[0];
    }

    found(place, lang, now) {
      const steps = place.directions || {};
      const stepsLang = (steps[lang] && steps[lang].length ? steps[lang] : steps.en) || [];
      const translated = lang !== "en" && !(steps[lang] && steps[lang].length) && !!(steps.en && steps.en.length);
      const isOpen = openNow(place.hours, now);
      return {
        status: "found",
        place_id: place.id,
        name: this.name(place, lang),
        where: textFor(place.where, lang),
        steps: stepsLang,
        walk_minutes: place.walk_minutes ?? null,
        outside_building: !!place.outside,
        hours: place.hours || "unknown",
        open_now: isOpen,
        tip: textFor(place.tip, lang),
        can_check_in: !!place.check_in,
        maps_query: place.maps_query || "",
        example_data: !!place.demo,
        say: "Give the steps briefly in the visitor's language." +
          (translated ? " Translate the steps faithfully, do not add anything." : "") +
          (isOpen === false ? " It is CLOSED now: say so first." : "") +
          (place.tip ? " Mention the tip only if it helps." : "") +
          (!stepsLang.length ? " No steps are known: give the 'where' text and offer to send a map link." : ""),
      };
    }
  }

  // Client tools for the ElevenLabs widget (same names and results as the robot bridge).
  function makeClientTools(profile, base = "") {
    if (profile.floor) return makeNavTools(profile, base);
    const dir = new Directory(profile);
    const langOf = (p) => (String(p.language || "").startsWith("ar") ? "ar" : "en");
    const op = profile.operator;
    const offline = (p) => `The reception screen is offline. Apologise and send the visitor to ${textFor(op.name, langOf(p))}, ${textFor(op.where, langOf(p))}.`;

    async function post(path, body, offlineMessage) {
      try {
        const r = await fetch(base + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
        const out = await r.json();
        out.alerted = r.ok;
        if (!r.ok) out.ok = false;
        return out;
      } catch (e) {
        return { ok: false, alerted: false, message: offlineMessage || "Screen unreachable." };
      }
    }
    const log = (name, params, out) => console.log("[tool]", name, params, out);

    return {
      lookup_place: async (p) => {
        const out = { ...dir.lookup(p.query || "", p.language || "en", p.place_id || ""), ok: true };
        log("lookup_place", p, out);
        return JSON.stringify(out);
      },
      check_in_visitor: async (p) => {
        const out = await post("/api/check-in", {
          visitor_name: p.visitor_name || "Guest", host_company: p.host_company || "",
          meeting_time: p.meeting_time || "", language: p.language || "en",
        }, offline(p));
        log("check_in_visitor", p, out);
        return JSON.stringify(out);
      },
      send_route_to_phone: async (p) => {
        const lang = langOf(p);
        if (!dir.places[p.place_id]) return JSON.stringify({ ok: false, message: "Unknown place_id. Call lookup_place first." });
        const f = dir.lookup("", lang, p.place_id);
        const steps = f.steps.length ? f.steps : [f.where];
        const out = await post("/api/send-route", {
          destination: f.name + (f.where ? " · " + f.where : ""), steps: steps.join(" | "), language: lang, maps_query: f.maps_query,
        }, offline(p));
        log("send_route_to_phone", p, out);
        return JSON.stringify(out);
      },
      request_operator: async (p) => {
        const lang = langOf(p);
        const out = await post("/api/operator", { reason: p.reason || "", visitor_name: p.visitor_name || "", language: lang }, "");
        out.ok = true;
        out.operator_location = `${textFor(op.name, lang)}, ${textFor(op.where, lang)}`;
        out.say = (out.alerted ? "A colleague at reception has been alerted. " : "") + "Tell the visitor kindly where the reception desk is, in one sentence.";
        log("request_operator", p, out);
        return JSON.stringify(out);
      },
    };
  }

  // Blind navigation (profiles with a floor map): same tools as actions.py, planned by nav.js
  function makeNavTools(profile, base = "") {
    const nav = root.OasisNav ? new root.OasisNav.Navigator(profile) : null;
    const send = (path, body) => fetch(base + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    let queue = Promise.resolve();
    function show(last) {
      const body = { ...nav.snapshot(), say_operator: (last && last.say_operator) || "", say_visitor: (last && last.say_visitor) || "", status: (last && last.status) || "" };
      queue = queue.then(() => send("/api/nav", body)).catch(() => {});
    }
    const tool = (name, fn) => async (p) => {
      let out;
      try {
        out = await fn(p || {});
        show(out);
      } catch (e) {
        out = { status: "error", say_operator: "Operator: stop, please.", say: "Something failed. Say this, then call request_human." };
      }
      console.log("[tool]", name, p, out);
      if (typeof root.onNavTool === "function") root.onNavTool(name, p, out);
      return JSON.stringify(out);
    };
    const tools = {
      find_place: (p) => nav.find(p.query || "", p.language || "en"),
      start_route: (p) => nav.startRoute(p.place_id || "", p.language || "en", p.last_passed || "", String(p.same_person || "").toLowerCase() === "yes", p.start_at || ""),
      step_done: (p) => nav.stepDone(p.step),
      update_position: (p) => nav.updatePosition(p.at || "", p.facing || ""),
      route_status: () => nav.status(),
      cancel_route: () => nav.cancel(),
      request_human: async (p) => {
        let sent = false;
        try { sent = (await send("/api/operator", { reason: p.reason || "", visitor_name: "", language: p.language || "en" })).ok; } catch (e) { /* offline */ }
        return { status: "ok", alerted: sent,
          say: (sent ? "An organiser has been alerted on the screen. " : "The screen is offline, nobody was alerted. ") +
            `Tell the visitor: for a person, ${textFor(profile.operator.where, "en")}. The operator stays stopped.` };
      },
    };
    show();
    return Object.fromEntries(Object.entries(tools).map(([k, fn]) => [k, tool(k, fn)]));
  }

  const api = { normalize, ratio, openNow, Directory, makeClientTools };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Oasis = api;
})(typeof window !== "undefined" ? window : globalThis);
