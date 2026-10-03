"""Tells a person what the trader does, without being asked. READ-ONLY: it reads logs/, it never trades.

    python3 trader_notify.py                 # Mac notification at once for trades, failures and alerts; a digest every 15 min
    python3 trader_notify.py --digest 30     # digest every 30 minutes
    python3 trader_notify.py --quiet-routine # no digest when nothing happened

At once:   a trade that settled, a counter accepted, a bid or ask filled (Hecho); a failure, a blocked accept, a guard stop
           (Fallo); a page, a hands-off lead, a stale bid (Aviso); the trader without a heartbeat for 2 minutes.
Digest:    what it did since the last digest: actions, trades, expiries, failures, cash, alive or not.
Same lines on the screen. Data: bz/activity.py, the same timeline as the dashboard panel "Actividad del agente".
"""
import argparse
import subprocess
import time

from bz import activity, log

NOW_STATUSES = ("ok", "fail", "blocked", "alert")
MAX_AT_ONCE = 4  # more than this in one poll: one notification that counts them


def notify(title: str, text: str) -> None:
    text = text.replace('"', "'").replace("\\", "/")[:200]
    try:
        subprocess.run(["osascript", "-e", f'display notification "{text}" with title "{title}"'], timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def digest_text(items: list, health: dict, minutes: float) -> str:
    c = activity.summary(items)
    alive = "alive" if health.get("alive") else f"NO HEARTBEAT ({health.get('age')} s)"
    state = "paused" if health.get("paused") else "stopped by guard" if health.get("stopped") else alive
    return (f"Last {minutes:g} min: {c.get('info', 0)} actions, {c.get('ok', 0)} trades, {c.get('expired', 0)} expired, "
            f"{c.get('fail', 0) + c.get('blocked', 0)} failures · cash {health.get('cash')} P · trader {state}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", type=float, default=15, help="minutes between digests (0: none)")
    ap.add_argument("--every", type=float, default=20, help="seconds between reads of the logs")
    ap.add_argument("--quiet-routine", action="store_true", help="skip a digest when nothing happened")
    args = ap.parse_args()
    seen = {i["key"] for i in activity.timeline()}  # no replay of the past
    last_digest, dead_told = time.time(), False
    log.say(f"trader_notify: read-only; {len(seen)} past items skipped; digest every {args.digest:g} min")
    while True:
        try:
            items = activity.timeline(since_ts=time.time() - 3600)
            new = [i for i in items if i["key"] not in seen]
            seen |= {i["key"] for i in new}
            loud = [i for i in new if i["status"] in NOW_STATUSES]
            for i in new:
                log.say(f"[t{i['tick']}] {i['status'].upper():8} {i['en']}")
            if len(loud) > MAX_AT_ONCE:
                notify("Bazaar trader", f"{len(loud)} events: " + "; ".join(i["en"][:40] for i in loud[:3]))
            else:
                for i in loud:
                    notify({"ok": "Bazaar trader · DONE", "fail": "Bazaar trader · FAILED", "blocked": "Bazaar trader · BLOCKED",
                            "alert": "Bazaar trader · ALERT"}[i["status"]], i["en"])
            h = activity.health()
            if not h["alive"] and not dead_told:
                notify("Bazaar trader · NO HEARTBEAT", f"no heartbeat for {h['age']} s: is trader.py running?")
                log.say(f"NO HEARTBEAT for {h['age']} s")
                dead_told = True
            elif h["alive"]:
                dead_told = False
            if args.digest and time.time() - last_digest >= args.digest * 60:
                window = activity.timeline(since_ts=last_digest)
                if window or not args.quiet_routine:
                    text = digest_text(window, h, args.digest)
                    notify("Bazaar trader · digest", text)
                    log.say("DIGEST " + text)
                last_digest = time.time()
        except Exception as e:  # never die
            log.say(f"trader_notify: unexpected {type(e).__name__}: {e}")
        time.sleep(args.every)


if __name__ == "__main__":
    main()
