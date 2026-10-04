"""Supervisor for duels.py: keeps it running through every duel wave and restarts it when it goes quiet.

Why: in Duels I our agent sent nothing from tick 503 to 553. In that window we left in-limit offers unanswered
(2362: 129 vs our 148, 2368: 85 vs 93) and three duels had no message at all (2317, 2380, 2381): all scored 0.

    python3 duels_watch.py                      # supervise duels.py with its defaults
    python3 duels_watch.py -- --ab 0.45,0.25    # anything after -- goes to duels.py
    python3 duels_watch.py --silent 3           # restart when a live duel waits 3 ticks for us (default)

Every tick: if duels are live and duels.py is not running, start it. If a live duel has waited SILENT ticks for us
(the rival spoke last, or nobody spoke since it opened), alert and restart duels.py. If duels.py dies, restart it.
Run only ONE supervisor for our team, on one machine: two agents would talk twice in the same duel.
Alerts go to logs/alerts.jsonl (level DUEL_SILENT, DUEL_CRASH, DUEL_START) and to the screen.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log

HERE = os.path.dirname(os.path.abspath(__file__))


def last_decisions(path: str) -> dict:
    """duel id -> last tick duels.py logged a decision for it (a deliberate wait counts: the agent is alive)."""
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f.readlines()[-3000:]:
                try:
                    e = json.loads(line)
                    out[int(e["duel"])] = max(out.get(int(e["duel"]), -1), int(e["tick"]))
                except (ValueError, KeyError, TypeError):
                    continue
    return out


def waiting_on_us(duels: list, tick: int, silent: int, decided: dict = None, duel_ticks: int = 16) -> list:
    """Live duels where we owe a message: the rival spoke last, or nobody spoke, for at least `silent` ticks, and
    duels.py has not logged a decision for the duel in that time (v2 stays silent on purpose with self-conceders)."""
    out = []
    for d in duels:
        if d.get("status") != "live":
            continue
        if decided and tick - decided.get(int(d["duel"]), -999) < silent:
            continue
        msgs = [m for m in d.get("messages") or [] if m.get("price") is not None]
        if msgs and msgs[-1].get("from") == "you":
            continue  # our offer stands: the rival owes the next move
        since = msgs[-1]["tick"] if msgs else d.get("start_tick") or (d.get("deadline_tick", tick) - duel_ticks)
        if tick - since >= silent:
            out.append(d["duel"])
    return out


def alert(level: str, text: str) -> None:
    log.event("alerts", level=level, text=text)
    log.say(f"ALERT {level}: {text}")


def main() -> None:
    argv = sys.argv[1:]
    passthrough = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--silent", type=int, default=3, help="ticks a live duel may wait for us before a restart")
    args = ap.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    os.makedirs(log.LOG_DIR, exist_ok=True)
    lock = open(os.path.join(log.LOG_DIR, "duels_watch.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another duels_watch.py is already running (logs/duels_watch.lock)")
    b = connect()
    child, last_restart = None, -999
    # the duel length duels.py was given (Sunday: 12); a fresh duel with no message started deadline - duel_ticks ago
    duel_ticks = int(passthrough[passthrough.index("--duel-ticks") + 1]) if "--duel-ticks" in passthrough else 16
    log.say(f"duels_watch: supervising duels.py {' '.join(passthrough)} (restart after {args.silent} silent ticks)")
    while True:
        try:
            tick = b.clock()["tick"]
            live = [d for d in b.duels().get("duels", []) if d.get("status") == "live"]
            running = child is not None and child.poll() is None
            if child is not None and not running and child.returncode not in (0, None) and live:
                alert("DUEL_CRASH", f"duels.py exited with code {child.returncode} while {len(live)} duels are live")
            if live and not running:
                child = subprocess.Popen([sys.executable, os.path.join(HERE, "duels.py"), *passthrough], cwd=HERE)
                last_restart = tick
                alert("DUEL_START", f"duels.py started at tick {tick} for {len(live)} live duels")
            owed = waiting_on_us(live, tick, args.silent, last_decisions(os.path.join(log.LOG_DIR, "duels.jsonl")), duel_ticks)
            # at most one restart per 10 ticks: duels.py may also wait on purpose (our price already at our limit)
            if owed and running and tick - last_restart > max(args.silent, 10):
                alert("DUEL_SILENT", f"{len(owed)} live duels waited {args.silent}+ ticks for us {owed[:6]}: restarting duels.py")
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                child = subprocess.Popen([sys.executable, os.path.join(HERE, "duels.py"), *passthrough], cwd=HERE)
                last_restart = tick
            b.wait_tick()
        except BazaarError as e:
            log.say(f"duels_watch: {e}")
            time.sleep(3)
        except Exception as e:  # the supervisor must never die
            log.say(f"duels_watch: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
