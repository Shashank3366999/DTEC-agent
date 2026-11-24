"""Run our success criteria as ElevenLabs agent tests (they appear in the dashboard under Tests).

  python3 -m oasis_voice eltest            create the tests once (ids saved in state/), run them, print the results
  python3 -m oasis_voice eltest --new      recreate them (after editing tests/elevenlabs_tests.json)
"""

import json
import os
import time

from .builder import ElevenLabs, SDK_DIR, _hash, load_state, save_state

TESTS_FILE = os.path.join(SDK_DIR, "tests", "elevenlabs_tests.json")


def _history(chat):
    out = []
    t = 0
    for turn in chat:
        role, message = turn[0], turn[1]
        item = {"role": role, "time_in_call_secs": t, "message": message}
        if len(turn) > 2:
            item["tool_calls"] = []
            item["tool_results"] = []
            for i, (name, params, result) in enumerate(turn[2]):
                rid = f"call_{t}_{i}"
                item["tool_calls"].append({"request_id": rid, "tool_name": name, "params_as_json": json.dumps(params, ensure_ascii=False),
                                           "tool_has_been_called": True, "type": "client"})
                item["tool_results"].append({"request_id": rid, "tool_name": name, "result_value": result, "is_error": False,
                                             "tool_has_been_called": True, "type": "client"})
        out.append(item)
        t += 5
    return out


def _body(test, tool_ids):
    name = test["name"]
    if test["type"] == "llm":
        return {"type": "llm", "name": name, "chat_history": _history(test["chat"]),
                "success_condition": test["success"],
                "success_examples": [{"response": r, "type": "success"} for r in test.get("ok", [])],
                "failure_examples": [{"response": r, "type": "failure"} for r in test.get("bad", [])]}
    tool = test["tool"]
    if tool not in tool_ids:
        raise SystemExit(f"test {name!r}: tool {tool} is not in state (run build first)")
    return {"type": "tool", "name": name, "chat_history": _history(test["chat"]),
            "tool_call_parameters": {
                "referenced_tool": {"id": tool_ids[tool], "type": "client"},
                "verify_absence": bool(test.get("absent")),
                "parameters": [{"path": k, "eval": v} for k, v in test.get("params", {}).items()]}}


def run(profile, api_key, new=False, log=print, repeat=1):
    api = ElevenLabs(api_key, False, log)
    bot_id = profile["bot"]["id"]
    state = load_state(bot_id)
    if not state.get("agent_id"):
        raise SystemExit("Build the agent first.")
    tool_ids = {k: v["id"] for k, v in state.get("tools", {}).items()}
    with open(TESTS_FILE, encoding="utf-8") as f:
        tests = json.load(f)["tests"]
    saved = {} if new else state.get("eltests", {})
    ids = []
    for t in tests:
        body = _body(t, tool_ids)
        h = _hash(body)
        if saved.get(t["name"], {}).get("hash") == h:
            ids.append(saved[t["name"]]["id"])
            continue
        out = api.call("POST", "/v1/convai/agent-testing/create", body)
        saved[t["name"]] = {"id": out["id"], "hash": h}
        ids.append(out["id"])
        log(f"created test: {t['name']}")
    save_state(bot_id, {**state, "eltests": saved})

    log(f"Running {len(ids)} tests on {state['agent_id']}…")
    inv = api.call("POST", f"/v1/convai/agents/{state['agent_id']}/run-tests", {"tests": [{"test_id": i} for i in ids], "repeat_count": repeat})
    for _ in range(60):
        time.sleep(5)
        inv = api.call("GET", f"/v1/convai/test-invocations/{inv['id']}")
        if all(r["status"] != "pending" for r in inv["test_runs"]):
            break
    passed = 0
    by_name = {}
    for r in inv["test_runs"]:
        ok = r["status"] == "passed"
        passed += ok
        name = (r.get("metadata") or {}).get("test_name", r["test_id"])
        by_name.setdefault(name, []).append(ok)
        if repeat > 1:
            continue
        log(f"  {'PASS' if ok else r['status'].upper():7} {name}")
        if not ok:
            cr = r.get("condition_result") or {}
            log("          " + str((cr.get("rationale") or {}).get("summary", ""))[:300])
            log("          agent said: " + str((r.get("agent_responses") or [{}])[-1].get("message", ""))[:300])
    if repeat > 1:
        for name, oks in by_name.items():
            log(f"  {sum(oks)}/{len(oks)}  {name}")
    log(f"\n{passed}/{len(inv['test_runs'])} ElevenLabs tests passed. Dashboard: elevenlabs.io/app/agents/tests")
    return passed == len(inv["test_runs"])
