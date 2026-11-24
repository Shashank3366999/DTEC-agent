"""Deterministic place directory.

The agent never invents a location: it calls `lookup_place`, and this module
answers from the profile data only. Same input -> same answer, every time.

  found      exactly one place matches     -> name, steps, walking time, open now?, tip
  ambiguous  several places match          -> options, the agent asks which one
  not_found  nothing matches               -> the agent says it doesn't know, offers the operator
"""

import datetime as _dt
import difflib
import re
import unicodedata

from .profile import text_for

DUBAI = _dt.timezone(_dt.timedelta(hours=4))  # UAE has no daylight saving time
MAX_OPTIONS = 4

_AR_FOLD = str.maketrans({"ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي", "ٱ": "ا", "ـ": ""})
_EN_STOP = {"the", "a", "an", "to", "is", "where", "please", "find", "go", "i", "want", "need", "how", "do", "get"}


def normalize(text):
    """Lowercase, drop accents and Arabic diacritics, fold Arabic letter variants."""
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")  # é->e, أ->ا, harakat gone
    text = text.translate(_AR_FOLD)
    text = re.sub(r"[^\w\s]", " ", text)
    words = []
    for w in text.split():
        if len(w) > 3 and w.startswith("ال"):  # Arabic definite article
            w = w[2:]
        words.append(w)
    return " ".join(words)


def _contains(haystack, needle):
    return f" {needle} " in f" {haystack} "


def _fuzzy(query_words, alias):
    """Best similarity between the alias and any same-length word window of the query."""
    n = len(alias.split())
    best = 0.0
    for i in range(0, max(1, len(query_words) - n + 1)):
        window = " ".join(query_words[i:i + n])
        best = max(best, difflib.SequenceMatcher(None, window, alias).ratio())
    return best


def dubai_now():
    return _dt.datetime.now(DUBAI)


def open_now(hours, now=None):
    """True/False for 'HH:MM-HH:MM' or '24h'; None when hours are unknown."""
    if not hours:
        return None
    if hours == "24h":
        return True
    now = now or dubai_now()
    start, end = hours.split("-")
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    s, e, t = sh * 60 + sm, eh * 60 + em, now.hour * 60 + now.minute
    if e == 0:
        e = 24 * 60
    if s <= e:
        return s <= t < e
    return t >= s or t < e  # overnight, e.g. 20:00-02:00


class Directory:
    def __init__(self, profile):
        self.profile = profile
        self.places = {p["id"]: p for p in profile["places"]}
        self._index = []  # (place_id, normalized phrase, kind)
        for p in profile["places"]:
            for lang_names in p.get("names", {}).values():
                for name in lang_names:
                    self._index.append((p["id"], normalize(name), "name"))
            for lang_kw in p.get("keywords", {}).values():
                for kw in lang_kw:
                    self._index.append((p["id"], normalize(kw), "keyword"))

    # ------------------------------------------------------------------ matching
    def match(self, query):
        """Return {place_id: score}. Names beat keywords; longer names beat shorter."""
        q = normalize(query)
        words = [w for w in q.split() if w not in _EN_STOP] or q.split()
        q_clean = " ".join(words)
        scores = {}
        for pid, phrase, kind in self._index:
            if not phrase:
                continue
            n = len(phrase.split())
            score = 0
            if _contains(q, phrase) or _contains(q_clean, phrase):
                score = (10 if kind == "name" else 3) + n
            elif kind == "name" and len(phrase) >= 5 and _fuzzy(words, phrase) >= 0.82:
                score = 6 + n  # close enough: handles small speech-to-text mistakes
            if score > scores.get(pid, 0):
                scores[pid] = score
        return scores

    def lookup(self, query="", language="en", place_id=""):
        lang = "ar" if str(language).lower().startswith("ar") else "en"
        if place_id and place_id in self.places:
            return self._found(self.places[place_id], lang)

        scores = self.match(query)
        if not scores:
            return {
                "status": "not_found",
                "query": query,
                "say": "You don't have this place. Say you don't know, and offer to call the operator "
                       "or send the visitor to the reception desk. Do not guess.",
            }
        top = max(scores.values())
        best = [pid for pid, s in scores.items() if s == top]
        if top >= 6:  # a name matched: names win over keyword-only matches
            if len(best) == 1:
                return self._found(self.places[best[0]], lang)
            candidates = best
        else:  # keyword-only matches, e.g. "bank", "mosque", "coffee"
            candidates = [pid for pid, s in scores.items() if s >= 3]
            if len(candidates) == 1:
                return self._found(self.places[candidates[0]], lang)
        candidates.sort(key=lambda pid: (self.places[pid].get("outside", False),
                                         self.places[pid].get("walk_minutes") or 99))
        options = [
            {"place_id": pid,
             "name": self._name(self.places[pid], lang),
             "where": text_for(self.places[pid].get("where"), lang)}
            for pid in candidates[:MAX_OPTIONS]
        ]
        return {
            "status": "ambiguous",
            "query": query,
            "options": options,
            "say": "Several places match. Ask ONE short question naming the options, then call "
                   "lookup_place again with the chosen place_id.",
        }

    # ------------------------------------------------------------------ helpers
    def _name(self, place, lang):
        names = place.get("names", {})
        return (names.get(lang) or names.get("en"))[0]

    def _found(self, place, lang, now=None):
        steps = place.get("directions", {})
        steps_lang = steps.get(lang) or steps.get("en") or []
        translated = lang != "en" and not steps.get(lang) and bool(steps.get("en"))
        is_open = open_now(place.get("hours"), now)
        result = {
            "status": "found",
            "place_id": place["id"],
            "name": self._name(place, lang),
            "where": text_for(place.get("where"), lang),
            "steps": steps_lang,
            "walk_minutes": place.get("walk_minutes"),
            "outside_building": bool(place.get("outside")),
            "hours": place.get("hours") or "unknown",
            "open_now": is_open,
            "tip": text_for(place.get("tip"), lang),
            "can_check_in": bool(place.get("check_in")),
            "maps_query": place.get("maps_query", ""),
            "example_data": bool(place.get("demo")),
            "say": "Give the steps briefly in the visitor's language."
                   + (" Translate the steps faithfully, do not add anything." if translated else "")
                   + (" It is CLOSED now: say so first." if is_open is False else "")
                   + (" Mention the tip only if it helps." if place.get("tip") else "")
                   + (" No steps are known: give the 'where' text and offer to send a map link."
                      if not steps_lang else ""),
        }
        return result

    def all_names(self):
        """Every place name, for the speech-to-text keyword list."""
        out = []
        for p in self.profile["places"]:
            for names in p.get("names", {}).values():
                out.extend(names)
        return out
