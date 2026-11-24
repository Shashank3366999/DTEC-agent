"""Check the floor map without the agent: print all routes, or play the operator by typing."""

from .navigator import Navigator


def routes(profile):
    start = Navigator(profile)
    print(f"Start: {start.node_name(start.at)}, heading {start.heading}"
          + ("   (DEMO LAYOUT)" if profile["floor"].get("demo") else ""))
    for place in profile["places"]:
        if not place.get("node"):
            continue
        nav = Navigator(profile)
        out = nav.start_route(place["id"], "en")
        print(f"\n{nav.place_name(place, 'en')}")
        while out["status"] in ("started", "next_step"):
            print("  " + out["say_operator"])
            out = nav.step_done(out["step"])
        print("  " + out["say_operator"])


def walk(profile, text, lang):
    nav = Navigator(profile)
    print("Type: go <place> | done | at <place> [facing <place>] | say again | cancel | quit\n")
    step, waiting = 0, None
    line = f"go {text}" if text else input("> ").strip()
    while line not in ("quit", "q", ""):
        word, _, rest = line.partition(" ")
        if word == "go":
            found = nav.find(rest, lang)
            place_id = found.get("place_id") or found.get("nearest")
            waiting = place_id
            out = nav.start_route(place_id, lang) if place_id else found
        elif word == "passed" and waiting:
            out = nav.start_route(waiting, lang, rest)
        elif word == "done":
            out = nav.step_done(step)
        elif word == "at":
            at, _, facing = rest.partition(" facing ")
            out = nav.update_position(at, facing)
        elif word == "cancel":
            out = nav.cancel()
        else:
            out = nav.status()
        step = out.get("step", step)
        for key in ("say_operator", "say_first_visitor", "say_visitor"):
            if out.get(key):
                print(f"  [{key[4:]}] {out[key]}")
        if not out.get("say_operator"):
            print("  ", out)
        if out["status"] == "need_position" and out.get("options"):
            print("   type: passed " + " | passed ".join(o["last_passed"] for o in out["options"]))
        if out["status"] == "ambiguous":
            print("   type: go " + " | go ".join(o["name"] for o in out["options"]))
        line = input("> ").strip()
