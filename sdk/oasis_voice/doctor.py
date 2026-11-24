"""`python3 -m oasis_voice doctor`: check everything the robot needs, in one go."""

import importlib
import json
import sys
import urllib.request


def _ok(msg):
    print(f"  OK    {msg}")
    return True


def _bad(msg, fix):
    print(f"  FIX   {msg}\n        -> {fix}")
    return False


def _try_import(name):
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _get(url, timeout=6):
    with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
        return r.status, r.read()


def run(profile, agent_id, env, robot=True):
    results = []
    print("\nOasis Voice doctor\n")

    v = sys.version_info
    results.append(_ok(f"Python {v.major}.{v.minor}") if v >= (3, 8) else
                   _bad(f"Python {v.major}.{v.minor} is too old", "Use Python 3.8 or newer"))

    results.append(_ok("websocket-client installed") if _try_import("websocket") else
                   _bad("websocket-client missing", "pip3 install websocket-client"))

    if robot:
        results.append(_ok("numpy installed") if _try_import("numpy") else
                       _bad("numpy missing", "pip3 install numpy"))
        results.append(_ok("ROS 2 (rclpy) found") if _try_import("rclpy") else
                       _bad("ROS 2 not found", "source /opt/ros/humble/setup.bash"))
        results.append(_ok("AimDK messages found") if _try_import("aimdk_msgs") else
                       _bad("AimDK messages not found", "source <aimdk path>/install/setup.bash (ask the MangoBot engineer)"))

    results.append(_ok(f"profile OK: {profile['bot']['name']}, {len(profile['places'])} places"))
    results.append(_ok(f"agent ID {agent_id}") if agent_id else
                   _bad("no agent ID", "Check sdk/state/<bot>.json, or export ELEVENLABS_AGENT_ID=..."))

    try:
        _get("https://api.elevenlabs.io/v1/models", timeout=8)
        results.append(_ok("internet: ElevenLabs reachable"))
    except urllib.error.HTTPError:
        results.append(_ok("internet: ElevenLabs reachable"))  # 401 still means we got there
    except Exception as e:
        results.append(_bad(f"cannot reach ElevenLabs ({e})", "No internet in the container: tell the MangoBot engineer"))

    url = env.get("WEBAPP_URL", "").rstrip("/")
    if not url:
        results.append(_bad("WEBAPP_URL not set",
                            "Set it in config.env. Directions still work; check-in, route and operator need it"))
    else:
        try:
            status, body = _get(url + "/health", timeout=70)  # free hosting may need a minute to wake up
            ok = status == 200 and json.loads(body or b"{}").get("ok")
            results.append(_ok(f"reception screen reachable: {url}") if ok else
                           _bad(f"reception screen answered strangely ({status})", "Open the URL in a browser"))
        except Exception as e:
            results.append(_bad(f"reception screen not reachable ({e})", "Check WEBAPP_URL, or open it in a browser to wake it"))

    good = sum(1 for r in results if r)
    print(f"\n{good}/{len(results)} checks passed." + ("" if good == len(results) else " Fix the lines marked FIX."))
    return good == len(results)
