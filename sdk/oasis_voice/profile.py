"""Load and check a bot profile (a JSON data file)."""

import json
import os

REQUIRED_TOP = ("bot", "languages", "greeting", "operator", "places")


class ProfileError(ValueError):
    pass


def load_profile(path):
    with open(path, encoding="utf-8") as f:
        try:
            profile = json.load(f)
        except json.JSONDecodeError as e:
            raise ProfileError(f"{path}: not valid JSON ({e})") from e
    problems = validate(profile)
    if problems:
        raise ProfileError(f"{path}:\n  - " + "\n  - ".join(problems))
    profile["_path"] = os.path.abspath(path)
    return profile


def validate(p):
    problems = []
    for key in REQUIRED_TOP:
        if key not in p:
            problems.append(f"missing '{key}'")
    if problems:
        return problems

    bot = p["bot"]
    for key in ("id", "name", "role", "location"):
        if not bot.get(key):
            problems.append(f"bot.{key} is required")

    langs = [p["languages"].get("default", "")] + list(p["languages"].get("others", []))
    for lang in langs:
        if lang not in p["greeting"]:
            problems.append(f"greeting.{lang} is missing")

    ids = set()
    for i, place in enumerate(p["places"]):
        pid = place.get("id")
        where = f"places[{i}] ({pid or 'no id'})"
        if not pid:
            problems.append(f"{where}: id is required")
        elif pid in ids:
            problems.append(f"{where}: duplicate id")
        ids.add(pid)
        names = place.get("names", {})
        if not names.get("en"):
            problems.append(f"{where}: names.en needs at least one name")
        directions = place.get("directions", {})
        if directions and not isinstance(directions.get("en", []), list):
            problems.append(f"{where}: directions.en must be a list of steps")
        hours = place.get("hours")
        if hours and hours != "24h" and not _hours_ok(hours):
            problems.append(f"{where}: hours must be '24h' or 'HH:MM-HH:MM', got {hours!r}")
    return problems


def _hours_ok(text):
    try:
        a, b = text.split("-")
        for t in (a, b):
            h, m = t.split(":")
            if not (0 <= int(h) <= 24 and 0 <= int(m) < 60):
                return False
        return True
    except ValueError:
        return False


def text_for(value, lang, fallback="en"):
    """Pick the language version of a {"en": ..., "ar": ...} value."""
    if isinstance(value, dict):
        return value.get(lang) or value.get(fallback) or ""
    return value or ""
