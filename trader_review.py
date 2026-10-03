"""Review of the trader and of our rank over the last hours. READ-ONLY: it never changes, starts or stops anything.

    python3 trader_review.py                # last 2 hours
    python3 trader_review.py --hours 4
    python3 trader_review.py --logs DIR     # another logs folder (tests)

It reads logs/*.jsonl and logs/trader.heartbeat and prints a short report; the same text is appended to logs/review.md.
Every number comes from a log. Proposals are rules over those numbers, each with its evidence; at most 3; a person
approves any change to live behaviour.
"""
import argparse
import json
import math
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "logs")
STALE_HEARTBEAT = 180   # seconds without a heartbeat: the trader is not running
LOW_CASH = 30


def read_jsonl(path: str, since: float = 0.0) -> list:
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if float(e.get("ts") or 0) >= since:
                    out.append(e)
    return out


def analyze(logs: str, now: float, hours: float) -> dict:
    since = now - hours * 3600
    r = lambda name: read_jsonl(os.path.join(logs, name + ".jsonl"), since)  # noqa: E731
    d = {"hours": hours}
    # ---- health
    hb = {}
    try:
        hb = json.load(open(os.path.join(logs, "trader.heartbeat"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    pause = None
    if os.path.exists(os.path.join(logs, "trader.pause")):
        pause = open(os.path.join(logs, "trader.pause"), encoding="utf-8").read().strip() or "(empty)"
    alerts = r("alerts")
    lv = {}
    for a in alerts:
        lv[a.get("level")] = lv.get(a.get("level"), 0) + 1
    d["health"] = {"heartbeat_age": (now - hb["ts"]) if hb.get("ts") else None, "live": hb.get("live"), "acting": hb.get("acting"),
                   "stopped": hb.get("stopped"), "budget": hb.get("budget"), "pause": pause, "alerts": lv,
                   "stops": [a["text"] for a in alerts if a.get("level") == "STOP"][-2:],
                   "score_drops": [a["text"] for a in alerts if a.get("level") == "SCORE-DROP"][-2:]}
    # ---- score and the field
    sc = r("score")
    d["score"] = None
    if len(sc) >= 2:
        a, b = sc[0], sc[-1]
        d["score"] = {"from": a, "to": b, "cash_low_share": sum(1 for x in sc if (x.get("cash") or 0) < LOW_CASH) / len(sc)}
    elif sc:
        d["score"] = {"from": sc[0], "to": sc[0], "cash_low_share": 1.0 if (sc[0].get("cash") or 0) < LOW_CASH else 0.0}
    # ---- accepts, settlements
    acc = r("trader_accept")
    st = {s["offer"]: s for s in r("trader_settlement")}
    done = [st[a["offer"]] for a in acc if a["offer"] in st and st[a["offer"]].get("found")]
    d["accepts"] = {"n": len(acc), "cost": sum((a.get("cash_out") or 0) + (a.get("fee") or 0) for a in acc),
                    "planned": sum(a.get("surplus") or 0 for a in acc), "settled": len(done),
                    "not_found": sum(1 for a in acc if a["offer"] in st and not st[a["offer"]].get("found")),
                    "planned_settled": sum(s.get("planned_gain") or 0 for s in done),
                    "realized": sum(s.get("realized_gain") or 0 for s in done if s.get("realized_gain") is not None),
                    "best": max((a.get("surplus") or 0 for a in acc), default=0)}
    # ---- counters
    cs, oc = r("trader_counter"), r("trader_outcome")
    d["counters"] = {"sent": len(cs), "accepted": sum(1 for o in oc if o.get("outcome") == "accepted"),
                     "expired": sum(1 for o in oc if o.get("outcome") == "expired")}
    # ---- standing quotes
    q = r("quotes")
    posted = [e for e in q if e.get("event") == "posted"]
    filled = [e for e in q if e.get("event") == "filled"]
    bids_p = [e for e in posted if e.get("side") == "bid"]
    buckets = {}
    for e in bids_p:
        k = e.get("ratio")
        if k is None:
            continue
        b = "<0.6" if k < 0.6 else "0.6-0.8" if k < 0.8 else "0.8-1.0" if k < 1.0 else ">=1.0"
        buckets.setdefault(b, [0, 0])[0] += 1
    for e in filled:
        k = next((p.get("ratio") for p in posted if p.get("offer") == e.get("offer")), None)
        if k is not None and e.get("side") == "bid":
            b = "<0.6" if k < 0.6 else "0.6-0.8" if k < 0.8 else "0.8-1.0" if k < 1.0 else ">=1.0"
            buckets.setdefault(b, [0, 0])[1] += 1
    d["quotes"] = {"bids": len(bids_p), "asks": len(posted) - len(bids_p), "fills": len(filled),
                   "bid_fills": sum(1 for e in filled if e.get("side") == "bid"),
                   "ask_fills": sum(1 for e in filled if e.get("side") == "ask"),
                   "cancelled": sum(1 for e in q if e.get("event") == "cancelled"),
                   "expired": sum(1 for e in q if e.get("event") == "closed"), "by_ratio": buckets}
    # ---- accepts we could not take (unique offers)
    bl, seen = r("trader_blocked"), set()
    by = {}
    for e in bl:
        k = (e["offer"], e["reason"])
        if k in seen:
            continue
        seen.add(k)
        x = by.setdefault(e["reason"], {"n": 0, "surplus": 0.0, "cost": 0, "top": []})
        x["n"] += 1
        x["surplus"] += e.get("surplus") or 0
        x["cost"] += e.get("cost") or 0
        x["top"].append((e.get("surplus") or 0, e.get("cost") or 0, e.get("venue")))
    for x in by.values():
        x["top"] = sorted(x["top"], reverse=True)[:3]
    d["blocked"] = by
    # ---- signals
    sg = r("signals")
    d["signals"] = {"asks": len(sg), "drops": sum(1 for e in sg if e.get("kind") == "drop"),
                    "drops_clearing": sum(1 for e in sg if e.get("kind") == "drop" and e.get("clears")),
                    "crossings": sum(1 for e in sg if e.get("kind") == "cross"),
                    "clearing_asks": sum(1 for e in sg if e.get("clears")),
                    "best_cross": max((e.get("net") or 0 for e in sg if e.get("kind") == "cross"), default=0)}
    d["proposals"] = propose(d)
    return d


def propose(d: dict) -> list:
    """(priority, text, evidence) rules. A person approves any change to live behaviour."""
    p, h = [], d["health"]
    if h["heartbeat_age"] is None or h["heartbeat_age"] > STALE_HEARTBEAT:
        p.append((100, "The trader is not running (no heartbeat).", "restart it with the go-live command; check why it stopped"))
    if h["pause"]:
        p.append((95, f"The trader is paused: {h['pause']}", "a person must look, then delete logs/trader.pause (the guard resets itself)"))
    if h["score_drops"]:
        p.append((70, "neg_points fell with no trade of ours.", h["score_drops"][-1]))
    bl = d["blocked"]
    if bl.get("budget", {}).get("n", 0) >= 2 or bl.get("budget", {}).get("surplus", 0) >= 6:
        x = bl["budget"]
        p.append((80, f"Raise the board budget (now {h.get('budget') or 40} P per hour) by about {max(10, math.ceil(x['cost']))} P.",
                  f"{x['n']} clear wins blocked by the budget: +{x['surplus']:.1f} P of value for {x['cost']} P"))
    c = d["counters"]
    if c["sent"] >= 5 and c["accepted"] == 0:
        p.append((60, "Stop sending counters.", f"{c['sent']} sent, 0 accepted"))
    qd = d["quotes"]
    if qd["bids"] >= 8 and qd["bid_fills"] == 0:
        p.append((65, "Standing bids never fill: test a bid 10 % of book higher (still below value minus margin).",
                  f"{qd['bids']} bids posted, 0 filled"))
    s = d["score"]
    if s and s["cash_low_share"] >= 0.7:
        p.append((75, "Cash is the limit: no bids can be posted.", f"cash was under {LOW_CASH} P in {s['cash_low_share']:.0%} of readings"))
    a = d["accepts"]
    if a["settled"] >= 3 and a["planned_settled"] > 0 and a["realized"] < 0.8 * a["planned_settled"]:
        p.append((85, "Accepts settle worse than planned: check the fee model.",
                  f"planned +{a['planned_settled']:.1f} P, realized +{a['realized']:.1f} P over {a['settled']} accepts"))
    sg = d["signals"]
    if sg["crossings"]:
        p.append((55, "A crossing pair appeared: a person decides (two accepts, ask first).", f"{sg['crossings']} seen, best net +{sg['best_cross']} P"))
    if not p and a["n"] == 0 and not bl and sg["clearing_asks"] == 0:
        p.append((10, "Nothing to improve: no clear win appeared in this window.", "the market was quiet for our needs"))
    return sorted(p, reverse=True)[:3]


def render(d: dict) -> str:
    h, a, c, q = d["health"], d["accepts"], d["counters"], d["quotes"]
    L = [f"TRADER REVIEW · last {d['hours']:g} h"]
    age = h["heartbeat_age"]
    L.append("Health: " + (f"heartbeat {age:.0f} s ago, live={h['live']}, acting={h['acting']}, stopped={h['stopped']}" if age is not None
                           else "NO HEARTBEAT (the trader is not running)")
             + (f" · PAUSED: {h['pause']}" if h["pause"] else ""))
    if h["alerts"]:
        L.append("Alerts: " + ", ".join(f"{k} {v}" for k, v in sorted(h["alerts"].items())))
    s = d["score"]
    if s:
        f, t = s["from"], s["to"]
        gd = lambda k: (t.get(k) or 0) - (f.get(k) or 0)  # noqa: E731
        L.append(f"Rank {f.get('rank')} -> {t.get('rank')} · score {f.get('score')} -> {t.get('score')} · neg_points {f.get('neg_points')} -> "
                 f"{t.get('neg_points')} · duel_points {f.get('duel_points')} -> {t.get('duel_points')} · market {f.get('market')} -> {t.get('market')}")
        if f.get("median_neg") is not None and t.get("median_neg") is not None:
            L.append(f"Negotiating: ours {gd('negotiating'):+.2f}, field median {gd('median_neg'):+.2f}, leader {gd('leader_neg'):+.2f}")
        L.append(f"Cash {f.get('cash')} -> {t.get('cash')} (under {LOW_CASH} P in {s['cash_low_share']:.0%} of readings)")
    else:
        L.append("Score: no readings in this window (is observe.py running?)")
    L.append(f"Accepts: {a['n']} (cost {a['cost']} P, planned +{a['planned']:.1f}); settled {a['settled']}: planned +{a['planned_settled']:.1f}, "
             f"realized +{a['realized']:.1f}; not found {a['not_found']}")
    L.append(f"Counters: sent {c['sent']}, accepted {c['accepted']}, expired {c['expired']}")
    L.append(f"Quotes: bids {q['bids']} (filled {q['bid_fills']}), asks {q['asks']} (filled {q['ask_fills']}), cancelled {q['cancelled']}, expired {q['expired']}"
             + (" · bids by price/book: " + ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(q["by_ratio"].items())) if q["by_ratio"] else ""))
    if d["blocked"]:
        L.append("Missed (clear wins we could not take): " + "; ".join(
            f"{k}: {v['n']} offers, +{v['surplus']:.1f} P, cost {v['cost']} P" for k, v in sorted(d["blocked"].items())))
    sg = d["signals"]
    L.append(f"Signals: {sg['asks']} asks seen, {sg['drops']} price drops ({sg['drops_clearing']} clearing our rules), "
             f"{sg['clearing_asks']} asks clearing our rules, {sg['crossings']} crossings")
    if d["proposals"]:
        L.append("Proposals (a person approves any change):")
        for i, (pr, text, ev) in enumerate(d["proposals"], 1):
            L.append(f"  {i}. {text}  [{ev}]")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--logs", default=LOGS)
    args = ap.parse_args()
    now = time.time()
    text = render(analyze(args.logs, now, args.hours))
    print(text)
    try:
        with open(os.path.join(args.logs, "review.md"), "a", encoding="utf-8") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M', time.localtime(now))}\n```\n{text}\n```\n")
    except OSError:
        pass


if __name__ == "__main__":
    main()
