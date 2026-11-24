"""Blind navigation: plan a route on one floor and talk a human operator along it, one step at a time.

The robot is walked by an operator who only follows our words. The AI never works out the way itself:
it calls these methods and speaks the lines they return. Everything here is deterministic, so the same
map + the same events always give the same words.

Map       profile["floor"]: nodes (x, y in metres), edges, and the robot's start node + heading.
Heading   degrees clockwise, 0 = +y ("map north").
Position  counted from the start, corrected by the operator/visitor (update_position) or a camera marker.
Leg       one straight walk = one instruction. "chain" is the list of nodes on it, first to last.

If the destination changes while the robot is between two nodes, we plan from that spot. If the right
instruction depends on which part of the leg the robot is on, we return need_position (one question)
instead of guessing.

The browser copy is webapp/public/nav.js, kept identical by webapp/test/parity.mjs.
"""

import math

from .directory import Directory, normalize

STRAIGHT = 25   # a bend smaller than this is still "straight"
AROUND = 135    # a bend bigger than this is "turn around"

VISITOR_LINES = {
    "confirm": {
        "en": "Shall I take you to the {place}?",
        "ar": "أوصلك إلى {place}؟",
        "hi": "क्या मैं आपको {place} ले चलूँ?",
        "es": "¿Le llevo a {place}?", "fr": "Je vous emmène à {place} ?", "de": "Soll ich Sie zu {place} bringen?",
        "ru": "Проводить вас: {place}?", "pt": "Levo-o até {place}?", "tr": "Sizi {place} yerine götüreyim mi?",
        "zh": "我带您去{place}吗？", "ur": "کیا میں آپ کو {place} لے چلوں؟",
    },
    "start": {
        "en": "Okay, we're going to the {place}. Please walk with us.",
        "ar": "تمام، بنروح إلى {place}. تفضّل امشِ معنا.",
        "hi": "ठीक है, हम {place} जा रहे हैं। कृपया हमारे साथ चलिए।",
        "es": "De acuerdo, vamos a {place}. Camine con nosotros, por favor.",
        "fr": "D'accord, nous allons à {place}. Suivez-nous, s'il vous plaît.",
        "de": "Gut, wir gehen zu {place}. Bitte kommen Sie mit.",
        "ru": "Хорошо, идём: {place}. Пожалуйста, идите с нами.",
        "pt": "Certo, vamos até {place}. Venha connosco, por favor.",
        "tr": "Tamam, {place} yerine gidiyoruz. Lütfen bizimle yürüyün.",
        "zh": "好的，我们去{place}。请跟我们走。",
        "ur": "ٹھیک ہے، ہم {place} جا رہے ہیں۔ براہِ کرم ہمارے ساتھ چلیں۔",
    },
    "arrived": {
        "en": "We've arrived: this is the {place}.",
        "ar": "وصلنا: هذي {place}.",
        "hi": "हम पहुँच गए हैं: यह {place} है।",
        "es": "Hemos llegado: esto es {place}.", "fr": "Nous sommes arrivés : voici {place}.",
        "de": "Wir sind da: das ist {place}.", "ru": "Мы на месте: это {place}.",
        "pt": "Chegámos: aqui é {place}.", "tr": "Geldik: burası {place}.",
        "zh": "我们到了：这里是{place}。", "ur": "ہم پہنچ گئے: یہ {place} ہے۔",
    },
    "changed": {
        "en": "A quick change: we're going to the {new} first. I can take you to the {old} after that.",
        "ar": "تغيّرت الوجهة: بنروح أول إلى {new}، وبعدها أقدر أوصلك إلى {old}.",
        "hi": "थोड़ा बदलाव है: हम पहले {new} जा रहे हैं। उसके बाद मैं आपको {old} ले चलूँगा।",
        "es": "Un cambio: primero vamos a {new}. Después le llevo a {old}.",
        "fr": "Petit changement : nous allons d'abord à {new}. Ensuite je vous emmène à {old}.",
        "de": "Kurze Änderung: wir gehen zuerst zu {new}. Danach bringe ich Sie zu {old}.",
        "ru": "Небольшое изменение: сначала {new}. Потом я провожу вас: {old}.",
        "pt": "Uma mudança: primeiro vamos a {new}. Depois levo-o a {old}.",
        "tr": "Küçük bir değişiklik: önce {new} yerine gidiyoruz. Sonra sizi {old} yerine götürürüm.",
        "zh": "稍作调整：我们先去{new}，之后我再带您去{old}。",
        "ur": "ایک تبدیلی: پہلے ہم {new} جا رہے ہیں۔ اس کے بعد میں آپ کو {old} لے چلوں گا۔",
    },
}


def visitor_line(kind, lang, **values):
    lines = VISITOR_LINES[kind]
    return lines.get(lang, lines["en"]).format(**values)


def turn_angle(old, new):
    """Signed turn in degrees, -180..180. Negative = left."""
    return (new - old + 540) % 360 - 180


def check_floor(p):
    """Problems in profile['floor'] (used by profile.validate)."""
    problems = []
    floor = p["floor"]
    nodes = {}
    for n in floor.get("nodes", []):
        if n.get("id") in nodes:
            problems.append(f"floor: duplicate node {n.get('id')}")
        if not n.get("id") or not isinstance(n.get("x"), (int, float)) or not isinstance(n.get("y"), (int, float)):
            problems.append(f"floor node {n.get('id')}: needs id, x and y")
        nodes[n.get("id")] = n
    near = {k: set() for k in nodes}
    for e in floor.get("edges", []):
        if len(e) != 2 or e[0] not in nodes or e[1] not in nodes:
            problems.append(f"floor edge {e}: both ends must be known nodes")
            continue
        if (nodes[e[0]].get("x"), nodes[e[0]].get("y")) == (nodes[e[1]].get("x"), nodes[e[1]].get("y")):
            problems.append(f"floor edge {e}: both ends are at the same spot")
        near[e[0]].add(e[1])
        near[e[1]].add(e[0])
    start = floor.get("start", {})
    if start.get("node") not in nodes:
        problems.append("floor.start.node must be a known node")
    else:
        seen, todo = set(), [start["node"]]
        while todo:
            k = todo.pop()
            if k not in seen:
                seen.add(k)
                todo.extend(near[k])
        lost = sorted(str(k) for k in set(nodes) - seen)
        if lost:
            problems.append(f"floor: no way to reach {', '.join(lost)} from the start")
    if not isinstance(start.get("heading"), (int, float)):
        problems.append("floor.start.heading must be a number (0 = map north, 90 = east)")
    ids = {x.get("id") for x in p["places"]}
    for x in p["places"]:
        if x.get("members"):
            for m in x["members"]:
                if m not in ids:
                    problems.append(f"place {x['id']}: unknown member {m}")
        elif x.get("node") not in nodes:
            problems.append(f"place {x.get('id')}: needs a node from the floor map (or members)")
    used = {x.get("node") for x in p["places"]}
    for k, n in nodes.items():
        if k not in used and not n.get("name"):
            problems.append(f"floor node {k}: needs a name the operator can recognise")
    return problems


class Navigator:
    def __init__(self, profile):
        self.profile = profile
        self.directory = Directory(profile)
        floor = profile["floor"]
        self.nodes = {n["id"]: n for n in floor["nodes"]}
        self.near = {k: set() for k in self.nodes}
        for a, b in floor["edges"]:
            self.near[a].add(b)
            self.near[b].add(a)
        self.name_langs = {k for p in profile["places"] for k in p.get("names", {})}
        self.place_at = {}
        for p in profile["places"]:
            if p.get("node") and p["node"] not in self.place_at:
                self.place_at[p["node"]] = p
        self.reset()

    def reset(self):
        start = self.profile["floor"]["start"]
        self.at = start["node"]          # None while walking a leg or lost
        self.heading = start["heading"]  # None when unknown
        self.source = "start"            # start | counted | told | marker
        self.route = None                # {"place_id", "language", "legs", "i"}
        self.pending = None              # the destination we left when it changed
        self.step_id = 0                 # number of the instruction now being followed
        return {"status": "reset"}

    # ---------------------------------------------------------------- geometry
    def bearing(self, a, b):
        p, q = self.nodes[a], self.nodes[b]
        return math.degrees(math.atan2(q["x"] - p["x"], q["y"] - p["y"])) % 360

    def dist(self, a, b):
        p, q = self.nodes[a], self.nodes[b]
        return math.sqrt((q["x"] - p["x"]) ** 2 + (q["y"] - p["y"]) ** 2)

    def shortest(self, start, goal):
        """(metres, [nodes]) by Dijkstra; ties go to the alphabetically first node."""
        cost, back, todo, done = {start: 0.0}, {}, {start}, set()
        while todo:
            k = min(todo, key=lambda n: (round(cost[n], 6), n))
            todo.discard(k)
            done.add(k)
            if k == goal:
                path = [k]
                while path[0] != start:
                    path.insert(0, back[path[0]])
                return cost[k], path
            for m in sorted(self.near[k]):
                c = cost[k] + self.dist(k, m)
                if m not in done and c < cost.get(m, math.inf) - 1e-9:
                    cost[m], back[m] = c, k
                    todo.add(m)
        return math.inf, []

    # ---------------------------------------------------------------- words
    def place_name(self, place, lang):
        names = place.get("names", {})
        return (names.get(lang) or names.get("en"))[0]

    def node_name(self, node_id):
        if node_id in self.place_at:
            return "the " + self.place_name(self.place_at[node_id], "en")
        return self.nodes[node_id]["name"]

    def _side(self, node_id, heading):
        """Where a place is for someone who stands at its node and looks along `heading`."""
        faces = self.place_at.get(node_id, {}).get("faces")
        if faces is None:
            return ""
        t = turn_angle(heading, faces)
        if abs(t) <= 45:
            return "straight ahead"
        if abs(t) >= AROUND:
            return "behind you"
        return "on your left" if t < 0 else "on your right"

    def _leg(self, chain, before, midway, final):
        heading = self.bearing(chain[0], chain[1])
        t = 0 if before is None else turn_angle(before, heading)
        if before is None:  # we know the spot but not which way the robot looks: use a landmark, not left or right
            head = f"Turn to face {self.node_name(chain[1])}, then walk straight"
        elif abs(t) <= STRAIGHT:
            head = "Keep walking straight" if midway else "Walk straight"
        elif abs(t) >= AROUND:
            head = "Turn around, then walk " + ("back" if midway else "straight")
        else:
            size = "slightly " if abs(t) <= 60 else ""
            head = f"Turn {size}{'left' if t < 0 else 'right'}, then walk straight"
        metres = sum(self.dist(a, b) for a, b in zip(chain, chain[1:]))
        if not midway:  # midway we don't know exactly how far is left, so only use landmarks
            m = max(1, math.floor(metres + 0.5))
            head += f" about {m} metre{'' if m == 1 else 's'}"
        via = [k for k in chain[1:-1] if k in self.place_at]
        passed = [f"{self.node_name(k)} {self._side(k, heading)}".strip() for k in (via[:1] + via[1:][-1:])]
        past = f", past {' and '.join(passed)}" if passed else ""
        text = f"{head}{past}, and stop at {self.node_name(chain[-1])}."
        side = self._side(chain[-1], heading) if final else ""
        if side:
            text += f" It is {side}."
        return {"chain": chain, "heading": heading, "before": before, "midway": midway, "final": final, "text": text}

    def _legs(self, path, before, midway):
        """Split a path into straight legs."""
        groups = [[path[0], path[1]]]
        for a, b in zip(path[1:], path[2:]):
            g = groups[-1]
            if abs(turn_angle(self.bearing(g[-2], g[-1]), self.bearing(a, b))) <= STRAIGHT:
                g.append(b)
            else:
                groups.append([a, b])
        legs = []
        for i, g in enumerate(groups):
            legs.append(self._leg(g, before, midway and i == 0, i == len(groups) - 1))
            before = self.bearing(g[-2], g[-1])
        return legs

    # ---------------------------------------------------------------- planning
    def _plan_from_node(self, node, heading, goal):
        return self._legs(self.shortest(node, goal)[1], heading, False)

    def _plan_between(self, a, b, goal):
        """The robot is somewhere between a and b, walking towards b."""
        half = self.dist(a, b) / 2
        ahead, path_ahead = self.shortest(b, goal)
        behind, path_behind = self.shortest(a, goal)
        path = [a] + path_ahead if half + ahead <= half + behind + 1e-9 else [b] + path_behind
        return self._legs(path, self.bearing(a, b), True)

    def _resolve(self, words):
        """A node from a node id, a place id, or what someone said ("I see the kitchen")."""
        words = str(words or "").strip()
        if words in self.nodes:
            return words
        place = self.directory.places.get(words)
        if place:
            return place.get("node")
        q = normalize(words)
        hits = [k for k, n in self.nodes.items() if n.get("name") and normalize(n["name"]).replace("the ", "", 1) in q]
        if q and len(hits) == 1:
            return hits[0]
        found = self.directory.lookup(words, "en")
        if found["status"] == "found":
            return self.directory.places[found["place_id"]].get("node")
        return None

    def _leg_now(self):
        return self.route["legs"][self.route["i"]]

    def _issue(self, status):
        """Hand out the current leg as a numbered instruction."""
        self.step_id += 1
        self.at = None
        return self._step(status)

    def _step(self, status):
        r = self.route
        place = self.directory.places[r["place_id"]]
        return {
            "status": status,
            "step": self.step_id,
            "steps_left": len(r["legs"]) - r["i"],
            "destination": self.place_name(place, "en"),
            "visitor_language": r["language"],
            "say_operator": "Operator: " + self._leg_now()["text"],
            "say_in_order": ["Operator: " + self._leg_now()["text"]],
        }

    # ---------------------------------------------------------------- what the agent can do
    def find(self, query, language="en"):
        """Understand a request. Never starts walking."""
        lang = self.directory.lang(language)
        scores = self.directory.match(query)
        by_name = bool(scores) and max(scores.values()) >= 6
        if str(language or "").lower()[:2] not in self.name_langs:
            by_name = False  # the request was translated by the AI, so always confirm before walking
        out = self.directory.lookup(query, lang)
        if out["status"] == "found":
            place = self.directory.places[out["place_id"]]
            if place.get("members"):
                return self._group(place, lang, by_name)
            name = self.place_name(place, lang)
            if by_name:
                return {"status": "found", "place_id": place["id"], "name": name, "say": "Call start_route now."}
            return {"status": "ask_first", "place_id": place["id"], "name": name,
                    "say_in_order": [visitor_line("confirm", lang, place=name)],
                    "say": "They did not name a place, so this is a guess. Say the question and wait. "
                           "Call start_route only after they say yes."}
        if out["status"] == "ambiguous":
            return {"status": "ambiguous",
                    "options": [{"place_id": o["place_id"], "name": o["name"]} for o in out["options"]],
                    "say": "Ask ONE short question naming these options."}
        if str(language or "").lower()[:2] not in self.name_langs:
            return {"status": "retry_in_english",
                    "say": "Place names are stored in English only for this language. Call find_place again NOW with the "
                           "request translated into English (e.g. 'conference room'). Do not say anything in between."}
        return {"status": "not_found",
                "say": "This place is not on this floor's map. Say so, offer the places you know or a person "
                       "(request_human). Do not guess."}

    def _group(self, place, lang, by_name):
        here = self.at or (self._leg_now()["chain"][-1] if self.route else None)
        members = [self.directory.places[m] for m in place["members"]]
        best = members[0]
        if here:
            best = min(members, key=lambda m: (round(self.shortest(here, m["node"])[0], 6), members.index(m)))
        return {
            "status": "group", "name": self.place_name(place, lang),
            "options": [{"place_id": m["id"], "name": self.place_name(m, lang)} for m in members],
            "nearest": best["id"],
            "say": "Ask ONE short question: " + ("will this do, and " if not by_name else "") + "which one, or the nearest? "
                   "Wait for the answer, then call start_route.",
        }

    def start_route(self, place_id, language="en", last_passed="", same_person=False, start_at=""):
        """Start, or change destination on the way. start_at: where somebody says the robot is right now."""
        lang = str(language or "en").lower()[:2]
        place = self.directory.places.get(place_id)
        if not place:
            return {"status": "error", "say": "Unknown place_id. Call find_place first."}
        if place.get("members"):
            return self._group(place, self.directory.lang(lang), True)
        goal = place["node"]
        old = self.route

        told = None
        if start_at:
            told = self._resolve(start_at)
            if told is None:
                return self._unknown_spot()
            if old and old["place_id"] == place_id:
                return self.update_position(told)
            chain = self._leg_now()["chain"] if old else []
            if told in chain:
                self.heading = self._leg_now()["before"] if told == chain[0] else self._leg_now()["heading"]
            elif told != self.at:
                self.heading = None
            self.at, self.source = told, "told"

        if old and told:
            legs = None
        elif old:
            leg = self._leg_now()
            if old["place_id"] == place_id:
                return {**self._step("already_going"), "say": "You are already going there. Do not repeat the step unless asked."}
            chain = leg["chain"]
            known = self._resolve(last_passed)
            if known == chain[-1]:
                self.at, self.heading, plans = known, leg["heading"], None
            elif known in chain:
                i = chain.index(known)
                plans = [self._plan_between(chain[i], chain[i + 1], goal)]
            else:
                plans = [self._plan_between(a, b, goal) for a, b in zip(chain, chain[1:])]
            if plans and len({(p[0]["heading"], p[0]["chain"][-1]) for p in plans}) > 1:
                return {
                    "status": "need_position",
                    "options": [{"last_passed": k, "name": self.node_name(k)} for k in chain[:-1]],
                    "say_operator": "Operator: stop, please. What is the last place you passed?",
                    "say_in_order": ["Operator: stop, please. What is the last place you passed?"],
                    "say": "Say this to the operator, then call start_route again with last_passed.",
                }
            legs = None
            if plans:  # same walk wherever we are on the leg: only mention landmarks that are surely still ahead
                legs = max(plans, key=lambda p: len(p[0]["chain"]))
                legs[0]["text"] = min(plans, key=lambda p: len(p[0]["chain"]))[0]["text"]
        else:
            legs = None
            if not self.at:
                return self._need_position()

        changed = {}
        if old:
            old_place = self.directory.places[old["place_id"]]
            # keep the very first unfinished destination, unless it is where we are going now
            keep = self.pending or {"place_id": old["place_id"], "language": old["language"]}
            if same_person:  # one visitor changed their mind: forget the old place
                keep = self.pending
            self.pending = None if keep and keep["place_id"] == place_id else keep
            changed = {
                "changed_from": self.place_name(old_place, "en"),
                "first_visitor_language": old["language"],
                "say_first_visitor": "" if same_person else visitor_line(
                    "changed", old["language"],
                    new=self.place_name(place, self.directory.lang(old["language"])),
                    old=self.place_name(old_place, self.directory.lang(old["language"]))),
            }
        elif self.pending and self.pending["place_id"] == place_id:
            self.pending = None

        if legs is None:
            if self.at == goal:
                self.route = None
                out = {**self._arrived(place, lang), **changed}
                if changed and not same_person:
                    out["say_in_order"].insert(1, changed["say_first_visitor"])
                return out
            legs = self._plan_from_node(self.at, self.heading, goal)
        self.route = {"place_id": place_id, "language": lang, "legs": legs, "i": 0}
        out = self._issue("changed" if changed else "started")
        if changed:
            out["say_operator"] = (f"Operator: stop, please. New destination: the {self.place_name(place, 'en')}. "
                                   + self._leg_now()["text"])
        out["say_visitor"] = visitor_line("start", lang, place=self.place_name(place, self.directory.lang(lang)))
        out["say_in_order"] = [out["say_visitor"], out["say_operator"]]
        if changed:  # the robot is moving: the stop comes first, the new step last
            out["say_in_order"] = [
                "Operator: stop, please.", *([changed["say_first_visitor"]] if not same_person else []), out["say_visitor"],
                f"Operator: New destination: the {self.place_name(place, 'en')}. " + self._leg_now()["text"]]
        out.update(changed)
        return out

    def step_done(self, step=0):
        """The operator finished instruction number `step`."""
        if not self.route:
            return {"status": "no_route", "say": "Nobody is being guided. Ask the visitor where they want to go."}
        try:
            step = int(step)
        except (TypeError, ValueError):
            step = 0
        if step != self.step_id:  # the same "done" reported twice must not skip a step
            return {**self._step("same_step"), "say": "That step was already counted. This is the current one."}
        return self._finish_leg("counted")

    def _finish_leg(self, source):
        leg = self._leg_now()
        self.at, self.heading, self.source = leg["chain"][-1], leg["heading"], source
        self.route["i"] += 1
        if self.route["i"] < len(self.route["legs"]):
            return self._issue("next_step")
        place, lang = self.directory.places[self.route["place_id"]], self.route["language"]
        self.route = None
        return self._arrived(place, lang)

    def _arrived(self, place, lang):
        out = {
            "status": "arrived", "destination": self.place_name(place, "en"), "visitor_language": lang,
            "say_operator": "Operator: stop here, please. We have arrived.",
            "say_visitor": visitor_line("arrived", lang, place=self.place_name(place, self.directory.lang(lang))),
        }
        out["say_in_order"] = [out["say_operator"], out["say_visitor"]]
        if self.pending and self.pending["place_id"] != place["id"]:
            p = self.directory.places[self.pending["place_id"]]
            out["offer_next"] = {"place_id": p["id"], "name": self.place_name(p, "en"),
                                 "visitor_language": self.pending["language"]}
        return out

    def _need_position(self):
        return {
            "status": "need_position", "options": [],
            "say_operator": "Operator: stop, please. What is right next to the robot?",
            "say": "Ask the operator or someone nearby, then call start_route again with start_at. Do not guess.",
        }

    def _unknown_spot(self):
        return {"status": "not_found", "options": [self.node_name(k) for k in sorted(self.nodes)],
                "say": "That spot is not on the map. Ask for something else that is close to the robot."}

    def update_position(self, at, facing="", source="told"):
        """Someone (or the camera) says where the robot is."""
        node = self._resolve(at)
        if node is None:
            return self._unknown_spot()
        look = self._resolve(facing)
        leg = self._leg_now() if self.route else None
        told_heading = self.bearing(node, look) if look and look != node else None

        if leg and node in leg["chain"] and (told_heading is None or abs(turn_angle(told_heading, leg["heading"])) <= 45):
            self.source = source
            i = leg["chain"].index(node)
            if i == len(leg["chain"]) - 1:
                return self._finish_leg(source)
            if i == 0 and told_heading is None and not leg["midway"]:
                self.at = None
                return self._step("on_track")  # not moved yet: the step still stands
            rest = self._leg(leg["chain"][i:], leg["heading"], True, leg["final"])
            self.route["legs"][self.route["i"]] = rest
            self.at = None
            return self._step("on_track")

        if told_heading is not None:
            heading = told_heading
        elif node == self.at:
            heading = self.heading
        else:
            heading = None
        self.at, self.heading, self.source = node, heading, source
        if not self.route:
            return {"status": "located", "at": self.node_name(node)}
        goal = self.directory.places[self.route["place_id"]]["node"]
        if node == goal:
            place, lang = self.directory.places[self.route["place_id"]], self.route["language"]
            self.route = None
            return self._arrived(place, lang)
        self.route["legs"], self.route["i"] = self._plan_from_node(node, heading, goal), 0
        return self._issue("rerouted")

    def status(self):
        if self.route:
            return self._step("walking")
        return {"status": "standing", "at": self.node_name(self.at) if self.at else "unknown"}

    def cancel(self):
        """Stop guiding. Between two nodes we no longer know exactly where the robot is."""
        was_walking = self.route is not None
        if was_walking:
            self.heading = None
        self.route = self.pending = None
        return {"status": "cancelled", "position_known": not was_walking,
                "say_operator": "Operator: stop here, please.",
                "say": "Tell the visitor the trip is stopped." +
                       (" Before the next trip, ask where the robot is and call update_position." if was_walking else "")}

    def snapshot(self):
        """For the screen."""
        leg = self._leg_now() if self.route else None
        place = self.directory.places[self.route["place_id"]] if self.route else None
        path = []
        if leg:
            for item in self.route["legs"][self.route["i"]:]:
                path += item["chain"] if not path else item["chain"][1:]
        return {
            "walking": leg is not None,
            "at": self.at, "between": leg["chain"][:2] if leg else None,
            "heading": leg["heading"] if leg else self.heading,
            "source": self.source,
            "destination": self.place_name(place, "en") if place else "",
            "destination_node": place["node"] if place else "",
            "path": path,
            "step": self.step_id, "steps_left": len(self.route["legs"]) - self.route["i"] if leg else 0,
            "instruction": leg["text"] if leg else "",
            "visitor_language": self.route["language"] if leg else "",
            "pending": self.place_name(self.directory.places[self.pending["place_id"]], "en") if self.pending else "",
        }
