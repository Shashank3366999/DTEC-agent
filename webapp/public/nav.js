// Browser copy of sdk/oasis_voice/navigator.py (blind navigation). Keep both identical: webapp/test/parity.mjs.
// Needs oasis.js first.
(function (root) {
  const STEP_METRES = 0.7, STRAIGHT = 25, AROUND = 135;
  const turnAngle = (a, b) => ((((b - a + 540) % 360) + 360) % 360) - 180;
  const r6 = (x) => Math.round(x * 1e6) / 1e6;
  const pairs = (list) => list.slice(1).map((b, i) => [list[i], b]);
  const strip = (s) => String(s ?? "").trim();

  class Navigator {
    constructor(profile) {
      this.profile = profile;
      this.lines = profile.visitor_lines;
      this.directory = new root.Oasis.Directory(profile);
      this.nodes = {};
      this.near = {};
      for (const n of profile.floor.nodes) { this.nodes[n.id] = n; this.near[n.id] = new Set(); }
      for (const [a, b] of profile.floor.edges) { this.near[a].add(b); this.near[b].add(a); }
      this.nameLangs = new Set(profile.places.flatMap((p) => Object.keys(p.names || {})));
      this.placeAt = {};
      for (const p of profile.places) if (p.node && !this.placeAt[p.node]) this.placeAt[p.node] = p;
      this.reset();
    }

    reset() {
      const s = this.profile.floor.start;
      this.at = s.node; this.heading = s.heading; this.source = "start";
      this.route = null; this.pending = null; this.stepId = 0;
      return { status: "reset" };
    }

    visitorLine(kind, lang, values) {
      const t = this.lines[kind];
      return (t[lang] || t.en).replace(/\{(\w+)\}/g, (_, k) => values[k]);
    }

    // ---- geometry
    bearing(a, b) {
      const p = this.nodes[a], q = this.nodes[b];
      return (((Math.atan2(q.x - p.x, q.y - p.y) * 180) / Math.PI) % 360 + 360) % 360;
    }
    dist(a, b) {
      const p = this.nodes[a], q = this.nodes[b];
      return Math.sqrt((q.x - p.x) ** 2 + (q.y - p.y) ** 2);
    }
    sortedNear(k) { return [...this.near[k]].sort(); }
    shortest(start, goal) {
      const cost = { [start]: 0 }, back = {}, todo = new Set([start]), done = new Set();
      while (todo.size) {
        const k = [...todo].sort((a, b) => r6(cost[a]) - r6(cost[b]) || (a < b ? -1 : 1))[0];
        todo.delete(k);
        done.add(k);
        if (k === goal) {
          const path = [k];
          while (path[0] !== start) path.unshift(back[path[0]]);
          return [cost[k], path];
        }
        for (const m of this.sortedNear(k)) {
          const c = cost[k] + this.dist(k, m);
          if (!done.has(m) && c < (cost[m] ?? Infinity) - 1e-9) { cost[m] = c; back[m] = k; todo.add(m); }
        }
      }
      return [Infinity, []];
    }

    // ---- words
    placeName(place, lang) {
      const n = place.names || {};
      return (n[lang] && n[lang].length ? n[lang] : n.en)[0];
    }
    nodeName(id) {
      return this.placeAt[id] ? "the " + this.placeName(this.placeAt[id], "en") : this.nodes[id].name;
    }
    side(id, heading) {
      const f = (this.placeAt[id] || {}).faces;
      if (f === undefined || f === null) return "";
      const t = turnAngle(heading, f);
      if (Math.abs(t) <= 45) return "straight ahead";
      if (Math.abs(t) >= AROUND) return "behind you";
      return t < 0 ? "on your left" : "on your right";
    }
    leg(chain, before, midway, final) {
      const heading = this.bearing(chain[0], chain[1]);
      const t = before === null ? 0 : turnAngle(before, heading), a = Math.abs(t);
      let head;
      if (before === null) head = `Turn to face ${this.nodeName(chain[1])}, then walk straight`;
      else if (a <= STRAIGHT) head = midway ? "Keep walking straight" : "Walk straight";
      else if (a >= AROUND) head = "Turn around, then walk " + (midway ? "back" : "straight");
      else head = `Turn ${a <= 60 ? "slightly " : ""}${t < 0 ? "left" : "right"}, then walk straight`;
      const metres = pairs(chain).reduce((s, [x, y]) => s + this.dist(x, y), 0);
      if (!midway) {
        const n = Math.max(1, Math.floor(metres / STEP_METRES + 0.5));
        head += ` about ${n} step${n === 1 ? "" : "s"}`;
      }
      const via = chain.slice(1, -1).filter((k) => this.placeAt[k]);
      const show = via.length > 1 ? [via[0], via[via.length - 1]] : via;
      const passed = show.map((k) => `${this.nodeName(k)} ${this.side(k, heading)}`.trim());
      let text = `${head}${passed.length ? ", past " + passed.join(" and ") : ""}, and stop at ${this.nodeName(chain[chain.length - 1])}.`;
      const side = final ? this.side(chain[chain.length - 1], heading) : "";
      if (side) text += ` It is ${side}.`;
      return { chain, heading, before, midway, final, text };
    }
    legs(path, before, midway) {
      const groups = [[path[0], path[1]]];
      for (const [a, b] of pairs(path).slice(1)) {
        const g = groups[groups.length - 1];
        if (Math.abs(turnAngle(this.bearing(g[g.length - 2], g[g.length - 1]), this.bearing(a, b))) <= STRAIGHT) g.push(b);
        else groups.push([a, b]);
      }
      return groups.map((g, i) => {
        const l = this.leg(g, before, midway && i === 0, i === groups.length - 1);
        before = this.bearing(g[g.length - 2], g[g.length - 1]);
        return l;
      });
    }

    // ---- planning
    planFromNode(node, heading, goal) { return this.legs(this.shortest(node, goal)[1], heading, false); }
    planBetween(a, b, goal) {
      const half = this.dist(a, b) / 2;
      const [ahead, pa] = this.shortest(b, goal), [behind, pb] = this.shortest(a, goal);
      const path = half + ahead <= half + behind + 1e-9 ? [a, ...pa] : [b, ...pb];
      return this.legs(path, this.bearing(a, b), true);
    }
    resolve(words) {
      words = strip(words);
      if (Object.hasOwn(this.nodes, words)) return words;
      if (Object.hasOwn(this.directory.places, words)) return this.directory.places[words].node ?? null;
      const q = root.Oasis.normalize(words);
      const hits = Object.keys(this.nodes).filter((k) => this.nodes[k].name && q.includes(root.Oasis.normalize(this.nodes[k].name).replace("the ", "")));
      if (q && hits.length === 1) return hits[0];
      const found = this.directory.lookup(words, "en");
      return found.status === "found" ? this.directory.places[found.place_id].node ?? null : null;
    }
    legNow() { return this.route.legs[this.route.i]; }
    issue(status) { this.stepId++; this.at = null; return this.step(status); }
    step(status) {
      const r = this.route, place = this.directory.places[r.place_id];
      return { status, step: this.stepId, steps_left: r.legs.length - r.i, destination: this.placeName(place, "en"),
        visitor_language: r.language, say_operator: "Operator: " + this.legNow().text, say_in_order: ["Operator: " + this.legNow().text] };
    }

    // ---- what the agent can do
    find(query, language = "en") {
      const lang = this.directory.lang(language);
      const scores = this.directory.match(query);
      const byName = scores.size > 0 && Math.max(...scores.values()) >= 6 && this.nameLangs.has(String(language || "").toLowerCase().slice(0, 2));
      const out = this.directory.lookup(query, lang);
      if (out.status === "found") {
        const place = this.directory.places[out.place_id];
        if (place.members) return this.group(place, lang, byName);
        const name = this.placeName(place, lang);
        if (byName) return { status: "found", place_id: place.id, name, say: "Call start_route now." };
        return { status: "ask_first", place_id: place.id, name, say_in_order: [this.visitorLine("confirm", lang, { place: name })],
          say: "They did not name a place, so this is a guess. Say the question and wait. Call start_route only after they say yes." };
      }
      if (out.status === "ambiguous") {
        return { status: "ambiguous", options: out.options.map((o) => ({ place_id: o.place_id, name: o.name })), say: "Ask ONE short question naming these options." };
      }
      if (!this.nameLangs.has(String(language || "").toLowerCase().slice(0, 2))) {
        return { status: "retry_in_english", say: "Place names are stored in English only for this language. Call find_place again NOW with the request translated into English (e.g. 'conference room'). Do not say anything in between." };
      }
      return { status: "not_found", say: "This place is not on this floor's map. Say so, offer the places you know or a person (request_human). Do not guess." };
    }
    group(place, lang, byName) {
      const chain = this.route ? this.legNow().chain : null;
      const here = this.at || (chain ? chain[chain.length - 1] : null);
      const members = place.members.map((m) => this.directory.places[m]);
      let best = members[0];
      if (here) for (const m of members) if (r6(this.shortest(here, m.node)[0]) < r6(this.shortest(here, best.node)[0])) best = m;
      return { status: "group", name: this.placeName(place, lang),
        options: members.map((m) => ({ place_id: m.id, name: this.placeName(m, lang) })), nearest: best.id,
        say: "Ask ONE short question: " + (byName ? "" : "will this do, and ") + "which one, or the nearest? Wait for the answer, then call start_route." };
    }
    startRoute(placeId, language = "en", lastPassed = "", samePerson = false, startAt = "") {
      const lang = String(language || "en").toLowerCase().slice(0, 2);
      const place = Object.hasOwn(this.directory.places, placeId) ? this.directory.places[placeId] : null;
      if (!place) return { status: "error", say: "Unknown place_id. Call find_place first." };
      if (place.members) return this.group(place, this.directory.lang(lang), true);
      const goal = place.node, old = this.route;
      let legs = null;
      let told = null;
      if (startAt) {
        told = this.resolve(startAt);
        if (told === null) return this.unknownSpot();
        if (old && old.place_id === placeId) return this.updatePosition(told);
        const chain = old ? this.legNow().chain : [];
        if (chain.includes(told)) this.heading = told === chain[0] ? this.legNow().before : this.legNow().heading;
        else if (told !== this.at) this.heading = null;
        this.at = told; this.source = "told";
      }
      if (old && told) legs = null;
      else if (old) {
        const leg = this.legNow();
        if (old.place_id === placeId) return { ...this.step("already_going"), say: "You are already going there. Do not repeat the step unless asked." };
        const chain = leg.chain, known = this.resolve(lastPassed);
        let plans = null;
        if (known !== null && known === chain[chain.length - 1]) { this.at = known; this.heading = leg.heading; }
        else if (chain.includes(known)) { const i = chain.indexOf(known); plans = [this.planBetween(chain[i], chain[i + 1], goal)]; }
        else plans = pairs(chain).map(([a, b]) => this.planBetween(a, b, goal));
        if (plans && new Set(plans.map((p) => p[0].heading + "|" + p[0].chain[p[0].chain.length - 1])).size > 1) {
          const behind = chain.slice(0, -1);
          return { status: "need_position", options: behind.map((k) => ({ last_passed: k, name: this.nodeName(k) })),
            say_operator: "Operator: please pause. What is the last place you passed?",
            say_in_order: ["Operator: please pause. What is the last place you passed?"],
            say: "Say this to the operator, then call start_route again with last_passed." };
        }
        if (plans) {
          const len = (p) => p[0].chain.length;
          legs = plans.reduce((m, p) => (len(p) > len(m) ? p : m));
          legs[0].text = plans.reduce((m, p) => (len(p) < len(m) ? p : m))[0].text;
        }
      } else if (!this.at) return this.needPosition();

      let changed = {};
      if (old) {
        const oldPlace = this.directory.places[old.place_id], ol = this.directory.lang(old.language);
        const keep = samePerson ? this.pending : this.pending || { place_id: old.place_id, language: old.language };
        this.pending = keep && keep.place_id === placeId ? null : keep;
        changed = { changed_from: this.placeName(oldPlace, "en"), first_visitor_language: old.language,
          say_first_visitor: samePerson ? "" : this.visitorLine("changed", old.language, { new: this.placeName(place, ol), old: this.placeName(oldPlace, ol) }) };
      } else if (this.pending && this.pending.place_id === placeId) this.pending = null;

      if (legs === null) {
        if (this.at === goal) {
          this.route = null;
          const out = { ...this.arrived(place, lang), ...changed };
          if (old && !samePerson) out.say_in_order.splice(1, 0, changed.say_first_visitor);
          return out;
        }
        legs = this.planFromNode(this.at, this.heading, goal);
      }
      this.route = { place_id: placeId, language: lang, legs, i: 0 };
      const out = this.issue(old ? "changed" : "started");
      if (old) out.say_operator = `Operator: change of plan, please pause. New destination: the ${this.placeName(place, "en")}. ` + this.legNow().text;
      out.say_visitor = this.visitorLine("start", lang, { place: this.placeName(place, this.directory.lang(lang)) });
      out.say_in_order = old
        ? ["Operator: please pause.", ...(samePerson ? [] : [changed.say_first_visitor]), out.say_visitor, `Operator: New destination: the ${this.placeName(place, "en")}. ` + this.legNow().text]
        : [out.say_visitor, out.say_operator];
      return Object.assign(out, changed);
    }
    stepDone(step = 0) {
      if (!this.route) return { status: "no_route", say: "Nobody is being guided. Ask the visitor where they want to go." };
      if (parseInt(step, 10) !== this.stepId) return { ...this.step("same_step"), say: "That step was already counted. This is the current one." };
      return this.finishLeg("counted");
    }
    finishLeg(source) {
      const leg = this.legNow();
      this.at = leg.chain[leg.chain.length - 1]; this.heading = leg.heading; this.source = source;
      this.route.i++;
      if (this.route.i < this.route.legs.length) return this.issue("next_step");
      const place = this.directory.places[this.route.place_id], lang = this.route.language;
      this.route = null;
      return this.arrived(place, lang);
    }
    arrived(place, lang) {
      const out = { status: "arrived", destination: this.placeName(place, "en"), visitor_language: lang,
        say_operator: "Operator: we have arrived, please stop here.",
        say_visitor: this.visitorLine("arrived", lang, { place: this.placeName(place, this.directory.lang(lang)) }) };
      out.say_in_order = [out.say_operator, out.say_visitor];
      if (this.pending && this.pending.place_id !== place.id) {
        const p = this.directory.places[this.pending.place_id];
        out.offer_next = { place_id: p.id, name: this.placeName(p, "en"), visitor_language: this.pending.language };
      }
      return out;
    }
    needPosition() {
      return { status: "need_position", options: [],
        say_operator: "Operator: please pause. What is right next to the robot?",
        say: "Ask the operator or someone nearby, then call start_route again with start_at. Do not guess." };
    }
    unknownSpot() {
      return { status: "not_found", options: Object.keys(this.nodes).sort().map((k) => this.nodeName(k)),
        say: "That spot is not on the map. Ask for something else that is close to the robot." };
    }
    updatePosition(at, facing = "", source = "told") {
      const node = this.resolve(at);
      if (node === null) return this.unknownSpot();
      const look = this.resolve(facing), leg = this.route ? this.legNow() : null;
      const told = look && look !== node ? this.bearing(node, look) : null;
      if (leg && leg.chain.includes(node) && (told === null || Math.abs(turnAngle(told, leg.heading)) <= 45)) {
        this.source = source;
        const i = leg.chain.indexOf(node);
        if (i === leg.chain.length - 1) return this.finishLeg(source);
        this.at = null;
        if (i === 0 && told === null && !leg.midway) return this.step("on_track");
        this.route.legs[this.route.i] = this.leg(leg.chain.slice(i), leg.heading, true, leg.final);
        return this.step("on_track");
      }
      const heading = told !== null ? told : node === this.at ? this.heading : null;
      this.at = node; this.heading = heading; this.source = source;
      if (!this.route) return { status: "located", at: this.nodeName(node) };
      const place = this.directory.places[this.route.place_id];
      if (node === place.node) { const lang = this.route.language; this.route = null; return this.arrived(place, lang); }
      this.route.legs = this.planFromNode(node, heading, place.node);
      this.route.i = 0;
      return this.issue("rerouted");
    }
    status() {
      return this.route ? this.step("walking") : { status: "standing", at: this.at ? this.nodeName(this.at) : "unknown" };
    }
    cancel() {
      const was = this.route !== null;
      if (was) this.heading = null;
      this.route = this.pending = null;
      return { status: "cancelled", position_known: !was, say_operator: "Operator: please stop here, the trip is over.",
        say: "Tell the visitor the trip is stopped." + (was ? " Before the next trip, ask where the robot is and call update_position." : "") };
    }
    snapshot() {
      const leg = this.route ? this.legNow() : null, place = this.route ? this.directory.places[this.route.place_id] : null;
      const path = [];
      if (leg) for (const l of this.route.legs.slice(this.route.i)) path.push(...(path.length ? l.chain.slice(1) : l.chain));
      return { walking: !!leg, at: this.at, between: leg ? leg.chain.slice(0, 2) : null, heading: leg ? leg.heading : this.heading,
        source: this.source, destination: place ? this.placeName(place, "en") : "", destination_node: place ? place.node : "", path,
        step: this.stepId, steps_left: leg ? this.route.legs.length - this.route.i : 0, instruction: leg ? leg.text : "",
        visitor_language: leg ? this.route.language : "",
        pending: this.pending ? this.placeName(this.directory.places[this.pending.place_id], "en") : "" };
    }
  }
  root.OasisNav = { Navigator };
})(typeof window !== "undefined" ? window : globalThis);
