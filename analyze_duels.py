"""Read the split test: finished duels grouped by the opening share we used (logs/duels.jsonl records it as `arm`).

    python3 analyze_duels.py            # all finished duels
    python3 analyze_duels.py --since 300   # only duels with an id above 300 (e.g. the scored session)

Per arm: duels, deals, deal rate, mean result / limit (the result is our surplus after the pie shrank, so dividing by
our limit makes a 30 P duel and a 130 P duel comparable), mean rounds. Few duels per arm: read a direction, not a proof.
"""
import argparse
import json
import os
import statistics

from bz import log
from bz.duel import days_weight, inside, surplus


def arms_from_log(path: str) -> dict:
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("arm") is not None and e.get("duel") is not None:
                out.setdefault(int(e["duel"]), e["arm"])
    return out


def summarize(duels: list, arm_of: dict) -> dict:
    """arm -> stats. A duel with no logged arm is grouped under None. `live` duels are skipped."""
    groups = {}
    for d in duels:
        if d.get("status") not in ("deal", "no_deal"):
            continue
        groups.setdefault(arm_of.get(int(d["duel"])), []).append(d)
    out = {}
    for arm, ds in groups.items():
        deals = [d for d in ds if d["status"] == "deal" and d.get("result") is not None]
        ratios = [d["result"] / d["your_limit"] for d in deals if d.get("your_limit")]
        out[arm] = {"duels": len(ds), "deals": len(deals), "deal_rate": round(len(deals) / len(ds), 2),
                    "result_over_limit": round(statistics.mean(ratios), 3) if ratios else None,
                    "mean_rounds": round(statistics.mean(d.get("rounds") or 0 for d in deals), 1) if deals else None}
    return out


SWITCH_AT = 2   # avoidable no-deals that send us back to --policy v1


def avoidable_no_deals(duels: list, grace: int = 2) -> list:
    """No-deals that did not have to be: the duel ended with no deal although the rival made at least one offer inside our
    limit with U >= 1 (U = price surplus + w x day, w from days_meaning). Silent rivals and rivals that never came inside
    our limit are not avoidable. An offer made less than `grace` ticks before the deadline does not count: an accept at a gap
    of 2 ticks settled in Duels I (duel 2486) but a gap of 1 is untested, so such an offer may not have been answerable. Returns [{"duel", "tick", "price", "days", "u"}] with the best such offer of each duel."""
    out = []
    for d in duels:
        if d.get("status") != "no_deal":
            continue
        two = "days" in (d.get("issues") or [])
        w = days_weight(d)[0] if two else 0.0
        best = None
        for m in d.get("messages") or []:
            if m.get("from") == "you" or m.get("price") is None:
                continue
            if d.get("deadline_tick") is not None and m["tick"] > d["deadline_tick"] - grace:
                continue
            u = surplus(d["role"], d["your_limit"], m["price"]) + (w * (m.get("days") or 0) if two and w else 0.0)
            if inside(d["role"], d["your_limit"], m["price"]) and u >= 1 and (best is None or u > best["u"]):
                best = {"duel": d["duel"], "tick": m["tick"], "price": m["price"], "days": m.get("days"), "u": round(u, 1)}
        if best:
            out.append(best)
    return out


def main() -> None:
    from agent import connect
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=0)
    args = ap.parse_args()
    duels = [d for d in connect().duels(done=True).get("duels", []) if int(d["duel"]) > args.since]
    arm_of = arms_from_log(os.path.join(log.LOG_DIR, "duels.jsonl"))
    # buyers and sellers differ (practice: 0.14 vs 0.23 of the limit), so compare arms inside each role
    for label, subset in (("all", duels), ("buyer", [d for d in duels if d["role"] == "buyer"]),
                          ("seller", [d for d in duels if d["role"] == "seller"])):
        for arm, s in sorted(summarize(subset, arm_of).items(), key=lambda kv: (kv[0] is None, kv[0])):
            print(f"{label:6} arm {arm}: {s}")
    av = avoidable_no_deals(duels)
    print(f"avoidable no-deals: {len(av)} {[(a['duel'], a['price'], a['days'], a['u']) for a in av]}"
          + (f"  -> SWITCH to --policy v1 (rule: {SWITCH_AT} or more)" if len(av) >= SWITCH_AT else f"  (switch at {SWITCH_AT})"))


if __name__ == "__main__":
    main()
