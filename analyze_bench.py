"""What the Market Test's traders do, from the book broker.py records (logs/bench/book.jsonl). Read only, no network.

    python3 analyze_bench.py                 # every session recorded
    python3 analyze_bench.py --json out.json # the per-trader table too

For each trader (a bench offer id like "b12-7": run b12, trader 7) it rebuilds the quote over time and when it left, and
whether it left matched (its id shows up in the book's settlements) or not. Then per session:

  relax    how far a trader moved its quote towards the other side per tick (asks fall, bids rise), in P and in % of
           its first quote; "firm" traders never moved
  life     ticks between its first and last appearance; whether impatient traders relax faster
  missed   traders that left unmatched although a quote on the other side of their run had crossed theirs at some point
           while both were in the book: gains the stall-like broker lost by timing (a smarter broker could have paired
           them). Those that never met a crossing quote are the gains only a limit-estimating broker could reach.
"""
import argparse
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_LOG = os.path.join(HERE, "logs", "bench", "book.jsonl")


def load(path: str = BOOK_LOG) -> list:
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def side_quote(o: dict) -> tuple:
    """("ask", price) for a bench seller (wants cash), ("bid", price) for a bench buyer (gives cash)."""
    want, give = (o.get("want") or {}).get("cash") or 0, (o.get("give") or {}).get("cash") or 0
    return ("ask", want) if want else ("bid", give)


def sessions(rows: list) -> list:
    """Split the log into Market Test sessions: runs of rows with bench offers, a gap of 3+ ticks starts a new one."""
    out, cur, last = [], [], None
    for r in rows:
        if not r.get("bench_offers"):
            continue
        if cur and r["tick"] - last >= 3:
            out.append(cur)
            cur = []
        cur.append(r)
        last = r["tick"]
    if cur:
        out.append(cur)
    return out


def traders(session: list) -> dict:
    """id -> {run, side, quotes [(tick, price)], first, last, matched}."""
    t, settled = {}, set()
    for r in session:
        blob = json.dumps(r.get("settlements") or [])
        for o in r["bench_offers"]:
            side, price = side_quote(o)
            x = t.setdefault(o["id"], {"run": o["id"].split("-")[0], "side": side, "quotes": [], "first": r["tick"]})
            if not x["quotes"] or x["quotes"][-1][1] != price:
                x["quotes"].append((r["tick"], price))
            x["last"] = r["tick"]
        settled |= {i for i in t if f'"{i}"' in blob}
    for i, x in t.items():
        x["matched"] = i in settled
    return t


def met_crossing(x: dict, others: list) -> bool:
    """Did a quote on the other side of x's run cross x's quote at a tick when both were in the book?"""
    def at(y, tick):  # y's quote at a tick, None when y was not in the book
        if not (y["first"] <= tick <= y["last"]):
            return None
        q = [p for tk, p in y["quotes"] if tk <= tick]
        return q[-1] if q else None
    for tick in range(x["first"], x["last"] + 1):
        mine = at(x, tick)
        for y in others:
            theirs = at(y, tick)
            if mine is None or theirs is None:
                continue
            ask, bid = (mine, theirs) if x["side"] == "ask" else (theirs, mine)
            if bid >= ask:
                return True
    return False


def summarize(t: dict) -> dict:
    by_run = defaultdict(list)
    for x in t.values():
        by_run[x["run"]].append(x)
    rows = []
    for x in t.values():
        first, final = x["quotes"][0][1], x["quotes"][-1][1]
        moved = (first - final) if x["side"] == "ask" else (final - first)  # towards the other side: positive
        life = x["last"] - x["first"] + 1
        others = [y for y in by_run[x["run"]] if y["side"] != x["side"]]
        rows.append({**x, "life": life, "moved": moved, "relax_per_tick": moved / life,
                     "relax_pct": moved / first if first else 0.0, "firm": moved == 0,
                     "met_cross": met_crossing(x, others)})
    n = len(rows) or 1
    unmatched = [r for r in rows if not r["matched"]]
    return {
        "traders": len(rows), "runs": len(by_run),
        "asks": sum(r["side"] == "ask" for r in rows), "bids": sum(r["side"] == "bid" for r in rows),
        "matched": sum(r["matched"] for r in rows), "firm_share": round(sum(r["firm"] for r in rows) / n, 2),
        "mean_life": round(sum(r["life"] for r in rows) / n, 1),
        "mean_relax_pct": round(sum(r["relax_pct"] for r in rows) / n, 3),
        "left_unmatched_after_cross": sum(r["met_cross"] for r in unmatched),
        "left_unmatched_never_crossed": sum(not r["met_cross"] for r in unmatched),
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=BOOK_LOG)
    ap.add_argument("--json", default=None, help="write every session's per-trader table here")
    args = ap.parse_args()
    out = []
    for i, s in enumerate(sessions(load(args.log)), 1):
        sm = summarize(traders(s))
        out.append({"session": i, "ticks": [s[0]["tick"], s[-1]["tick"]], **sm})
        print(f"session {i} · ticks {s[0]['tick']}-{s[-1]['tick']} · {sm['traders']} traders in {sm['runs']} runs "
              f"({sm['asks']} asks, {sm['bids']} bids)")
        print(f"  matched {sm['matched']} · firm {sm['firm_share']:.0%} · life {sm['mean_life']} ticks · "
              f"relax {sm['mean_relax_pct']:.1%} of the first quote")
        print(f"  left unmatched: {sm['left_unmatched_after_cross']} after meeting a crossing quote (timing), "
              f"{sm['left_unmatched_never_crossed']} never crossed (hidden limits)")
    if not out:
        print("no Market Test recorded yet (logs/bench/book.jsonl has no bench offers)")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
