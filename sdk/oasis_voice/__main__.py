"""Command line for the Oasis Voice SDK.

  python3 -m oasis_voice validate              check the profile data file
  python3 -m oasis_voice ask "where is the bank" [--lang ar]
                                               test the deterministic directory (offline)
  python3 -m oasis_voice prompt                print the agent instructions made from the profile
  python3 -m oasis_voice build [--dry-run]     create/update the ElevenLabs agent (needs ELEVENLABS_API_KEY)
  python3 -m oasis_voice chat [--say "..."]    text chat with the agent, tools run locally
  python3 -m oasis_voice doctor [--laptop]     check everything the robot needs
  python3 -m oasis_voice bridge                run on the robot (needs ROS 2 + AimDK)

Every command takes --profile PATH (default: profiles/dtec_navigator.json).
Settings are read from a .env file in the repo root or the current folder.
"""

import argparse
import json
import os
import sys

from . import __version__
from .profile import ProfileError, load_profile

SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PROFILE = os.path.join(SDK_DIR, "profiles", "dtec_navigator.json")
SETTINGS = ("ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID", "WEBAPP_URL", "TOOL_SECRET")


def load_settings():
    env = {}
    for path in (os.path.join(os.path.dirname(SDK_DIR), ".env"), os.path.join(SDK_DIR, ".env"), ".env"):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
    for k in SETTINGS:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def agent_id_for(profile, env):
    if env.get("ELEVENLABS_AGENT_ID"):
        return env["ELEVENLABS_AGENT_ID"]
    from .builder import load_state
    return load_state(profile["bot"]["id"]).get("agent_id", "")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oasis_voice", description=f"Oasis Voice SDK {__version__}")
    ap.add_argument("command", choices=["validate", "ask", "prompt", "build", "chat", "bridge", "doctor"])
    ap.add_argument("text", nargs="?", default="", help="for 'ask': what the visitor said")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--new", action="store_true", help="for 'build': make a new agent instead of updating")
    ap.add_argument("--say", action="append", help="for 'chat': send these messages, then exit")
    ap.add_argument("--laptop", action="store_true", help="for 'doctor': skip the robot-only checks")
    args = ap.parse_args(argv)

    try:
        profile = load_profile(args.profile)
    except (ProfileError, OSError) as e:
        sys.exit(f"Profile problem: {e}")
    env = load_settings()

    if args.command == "validate":
        print(f"OK: {profile['bot']['name']} · {len(profile['places'])} places · "
              f"languages {[profile['languages']['default']] + profile['languages'].get('others', [])}")
        return

    if args.command == "ask":
        from .directory import Directory
        print(json.dumps(Directory(profile).lookup(args.text, args.lang), ensure_ascii=False, indent=2))
        return

    if args.command == "prompt":
        from .prompt import build_prompt
        print(build_prompt(profile))
        return

    if args.command == "build":
        from .builder import BuildError, build
        key = env.get("ELEVENLABS_API_KEY", "")
        if not key and not args.dry_run:
            sys.exit("Put ELEVENLABS_API_KEY=... in the .env file (copy .env.example). Never paste it in a chat.")
        try:
            agent_id = build(profile, key, dry_run=args.dry_run, new=args.new)
        except BuildError as e:
            sys.exit(str(e))
        print(f"\nDone. Agent ID: {agent_id}")
        return

    if args.command == "doctor":
        from .doctor import run as doctor
        sys.exit(0 if doctor(profile, agent_id_for(profile, env), env, robot=not args.laptop) else 1)

    from .actions import ToolRouter
    router = ToolRouter(profile, env.get("WEBAPP_URL", ""), env.get("TOOL_SECRET", ""))
    agent_id = agent_id_for(profile, env)
    if not agent_id:
        sys.exit("No agent yet. Run: python3 -m oasis_voice build")

    if args.command == "chat":
        from .chat import run
        run(agent_id, router, args.say)
    elif args.command == "bridge":
        from .bridge import run
        run(agent_id, env.get("ELEVENLABS_API_KEY", "") if os.environ.get("PRIVATE_AGENT") == "1" else "", router)


if __name__ == "__main__":
    main()
