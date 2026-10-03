"""The tape of ALL markets: every trade between teams, and with the dealers, as it settles. READ-ONLY.

    python3 market_watch.py              # runs until stopped; logs/market_tape.jsonl; one line per trade on the screen
    python3 market_watch.py --report     # last 3 hours: trades and volume per venue, price / book per rarity, who buys and sells
    python3 market_watch.py --report --hours 6

Source: the public feed (settlements), every few ticks, so no trade is missed (the feed holds about 20 ticks). Alerts:
  TAPE-NEED   a card we still need just traded between teams: the price it fetched and what we could have gained
  TAPE-SPARE  a card we hold a spare of just traded: what a spare really sells for
Venue announcements that carry other teams' market data ("Radar", "price guide") are saved to logs/market_intel.jsonl.
"""
import argparse
import json
import os
import statistics
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log
from bz.state import State
from bz.tape import alerts_for, reference_price, summarize, trade_of

TAPE = os.path.join(log.LOG_DIR, "market_tape.jsonl")
POLL_TICKS = 4
INTEL_WORDS = ("radar", "price guide", "most wanted")


def load_tape() -> list:
    rows = []
    if os.path.exists(TAPE):
        for line in open(TAPE, encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def report(hours: float) -> None:
    trades = load_tape()
    if not trades:
        print("no trades recorded yet (is market_watch.py running?)")
        return
    now = max(t["ts"] for t in trades)
    ts = [t for t in trades if now - t["ts"] <= hours * 3600]
    if not ts:
        print("no trades in this window")
        return
    s = summarize(ts)
    print(f"MARKET TAPE · last {hours:g} h · {s['team_trades']} team trades, {s['dealer_trades']} dealer trades")
    vol = sum(v[1] for v in s["venues"].values()) or 1
    print("Venues (trades, volume P, share of volume): " + "; ".join(
        f"{k} {v[0]} / {v[1]} P / {100 * v[1] / vol:.0f} %" for k, v in list(s["venues"].items())[:6]))
    print("Price / book per rarity (median, n): " + ", ".join(f"{k} {v[0]} (n={v[1]})" for k, v in s["rarity_ratio"].items()))
    print("Most traded cards: " + ", ".join(f"{k} x{len(v)} (median {statistics.median(v):.0f} P)" for k, v in list(s["cards"].items())[:6]))
    print("Buyers: " + ", ".join(f"{k} {n}" for k, n in list(s["buyers"].items())[:6]) + " | Sellers: " +
          ", ".join(f"{k} {n}" for k, n in list(s["sellers"].items())[:6]))
    if s["dealers"]:
        print("Dealers (trades, P): " + ", ".join(f"{k} {v[0]} / {v[1]}" for k, v in s["dealers"].items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report(args.hours)
    os.makedirs(log.LOG_DIR, exist_ok=True)
    b = connect()
    st = State(b)
    cat = st.catalog
    book = {r: v["book"] for r, v in cat["rarities"].items()}
    rarity_of = {c["id"]: c["rarity"] for s in cat["sets"] for c in s["cards"]}
    known = load_tape()
    last_id = max((t.get("id") or 0 for t in known), default=0)
    trades = list(known)
    next_poll, refreshed, vcache = 0, -999, {}
    log.say(f"market_watch: read-only; logs/market_tape.jsonl; {len(known)} trades already recorded, last event id {last_id}")
    while True:
        try:
            tick = b.clock()["tick"]
            if tick >= next_poll:
                next_poll = tick + POLL_TICKS
                if tick - refreshed >= 20:
                    st.refresh()
                    refreshed, vcache = tick, {}
                needs = {r for refs in st.missing().values() for r in refs}
                spares = {a["ref"] for a in st.spares()}

                def value_of(ref):
                    if ref not in vcache:
                        try:
                            vcache[ref] = float(b.value(ref)["your_value"])
                        except (BazaarError, KeyError, ValueError):
                            vcache[ref] = None
                    return vcache[ref]

                events = sorted((e for e in b.feed(limit=500).get("events", []) if e["id"] > last_id), key=lambda e: e["id"])
                for e in events:
                    last_id = max(last_id, e["id"])
                    if e["type"] == "venue.announcement":
                        text = (e.get("payload") or {}).get("text", "")
                        if any(w in text.lower() for w in INTEL_WORDS):
                            log.event("market_intel", tick=e["tick"], venue=(e["payload"] or {}).get("venue"), text=text[:600])
                        continue
                    t = trade_of(e, book, rarity_of)
                    if not t:
                        continue
                    t["ts"] = time.time()
                    trades.append(t)
                    with open(TAPE, "a", encoding="utf-8") as f:
                        f.write(json.dumps(t, ensure_ascii=False) + "\n")
                    c0 = t["cards"][0] if t["cards"] else {}
                    ref_p = reference_price(trades[:-1], c0.get("ref"), t["tick"]) if len(t["cards"]) == 1 else None
                    log.say(f"[t{t['tick']}] {t['kind'].upper():6} {t['venue'] or t['persona']:7} {'→'.join(t['parties'])} "
                            + ", ".join(f"{c['ref']}" for c in t["cards"]) + f" {t['price']} P"
                            + (f" ({t['ratio']} of book)" if t["ratio"] is not None else "")
                            + (f" · earlier median {ref_p:.0f}" if ref_p else "") + (f" · fee {t['fee']}" if t["fee"] else ""))
                    for level, text in alerts_for(t, needs, spares, value_of):
                        log.event("alerts", level=level, text=text)
                        log.say(f"ALERT {level}: {text}")
            if args.once:
                return
            b.wait_tick()
        except BazaarError as e:
            log.say(f"market_watch: {e}")
            time.sleep(3)
        except Exception as e:  # never die
            log.say(f"market_watch: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
