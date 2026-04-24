#!/usr/bin/env python3
"""
AI Conversation Regression Runner for Spartan Shield-Saver

Usage from Backend folder while Flask is running:
    python test_ai_conversation_suite.py --dataset ai_conversation_dataset_large.json

Optional:
    python test_ai_conversation_suite.py --base-url http://127.0.0.1:5000 --username test_ai_user --password testpass

The runner creates/logs into a test user, clears chat before each scenario,
sends every turn to /api/ai/chat, and validates broad response expectations.
"""
import argparse, json, re, sys, time, uuid
from pathlib import Path
from typing import Any, Dict, List
try:
    import requests
except ImportError:
    print("Missing dependency: requests. Install it with: pip install requests")
    sys.exit(1)


def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9$.'\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains(text: str, phrase: str) -> bool:
    return norm(phrase) in norm(text)


def post_json(session: requests.Session, url: str, payload: Dict[str, Any]) -> requests.Response:
    return session.post(url, json=payload, timeout=20)


def ensure_user(session: requests.Session, base_url: str, username: str, password: str) -> None:
    # Try create; ignore duplicate failures.
    session.post(f"{base_url}/api/users/", json={
        "name": "AI Regression Test User",
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
    }, timeout=20)
    r = session.post(f"{base_url}/api/users/login", json={"username": username, "password": password}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Login failed ({r.status_code}): {r.text}")


def clear_chat(session: requests.Session, base_url: str) -> None:
    session.post(f"{base_url}/api/ai/clear-chat", json={}, timeout=20)


def get_reply(resp_json: Dict[str, Any]) -> str:
    for key in ("reply", "message", "response", "text"):
        if isinstance(resp_json.get(key), str):
            return resp_json[key]
    return json.dumps(resp_json, ensure_ascii=False)


def validate_turn(reply: str, turn: Dict[str, Any], global_bad: List[str]) -> List[str]:
    failures=[]
    for bad in global_bad + turn.get("must_not_include", []):
        if bad and contains(reply, bad):
            failures.append(f"must_not_include matched: {bad!r}")
    required=turn.get("must_include", [])
    for req in required:
        if req and not contains(reply, req):
            failures.append(f"missing required phrase: {req!r}")
    # Optional regex checks.
    for pattern in turn.get("must_match_regex", []):
        if not re.search(pattern, reply, flags=re.I):
            failures.append(f"regex not matched: {pattern}")
    return failures


def run_suite(args: argparse.Namespace) -> int:
    dataset=json.loads(Path(args.dataset).read_text(encoding='utf-8'))
    scenarios=dataset.get('scenarios', [])
    global_bad=dataset.get('global_must_not_include', [])
    session=requests.Session()
    username=args.username or f"ai_test_{uuid.uuid4().hex[:8]}"
    password=args.password
    ensure_user(session, args.base_url.rstrip('/'), username, password)

    results=[]; failed=0; total_turns=0
    for idx, scenario in enumerate(scenarios, start=1):
        if args.limit and idx > args.limit:
            break
        clear_chat(session, args.base_url.rstrip('/'))
        scenario_failures=[]
        if not args.quiet:
            print(f"\n[{idx}/{len(scenarios)}] {scenario.get('name')} ({scenario.get('category')})")
        for tnum, turn in enumerate(scenario.get('turns', []), start=1):
            total_turns += 1
            user_msg=turn.get('user','')
            try:
                r=post_json(session, f"{args.base_url.rstrip('/')}/api/ai/chat", {"message": user_msg})
                try: data=r.json()
                except Exception: data={"reply": r.text}
                reply=get_reply(data)
                turn_failures=[]
                if r.status_code != 200:
                    turn_failures.append(f"HTTP {r.status_code}: {r.text[:250]}")
                turn_failures += validate_turn(reply, turn, global_bad)
            except Exception as e:
                reply=""; turn_failures=[f"request error: {e}"]
            if turn_failures:
                scenario_failures.append({"turn":tnum,"user":user_msg,"reply":reply,"failures":turn_failures})
                if not args.quiet:
                    print(f"  FAIL turn {tnum}: {user_msg}")
                    print(f"    reply: {reply[:300]}")
                    for f in turn_failures: print(f"    - {f}")
            elif not args.quiet:
                print(f"  PASS turn {tnum}: {user_msg[:80]}")
            if args.delay: time.sleep(args.delay)
        if scenario_failures: failed += 1
        results.append({"scenario":scenario.get('name'),"category":scenario.get('category'),"failures":scenario_failures})

    report={
        "dataset": str(args.dataset),
        "base_url": args.base_url,
        "scenarios_run": len(results),
        "total_turns": total_turns,
        "scenarios_failed": failed,
        "scenarios_passed": len(results)-failed,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"\nSummary: {len(results)-failed}/{len(results)} scenarios passed; {failed} failed. Turns run: {total_turns}.")
    print(f"Detailed report saved to: {args.output}")
    return 1 if failed else 0


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset', default='ai_conversation_dataset_large.json')
    p.add_argument('--base-url', default='http://127.0.0.1:5000')
    p.add_argument('--username', default=None)
    p.add_argument('--password', default='testpass123')
    p.add_argument('--output', default='ai_conversation_test_results.json')
    p.add_argument('--limit', type=int, default=0, help='Run only the first N scenarios')
    p.add_argument('--delay', type=float, default=0.0, help='Delay between turns')
    p.add_argument('--quiet', action='store_true')
    args=p.parse_args()
    raise SystemExit(run_suite(args))

if __name__ == '__main__':
    main()
