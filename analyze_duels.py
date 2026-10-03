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


if __name__ == "__main__":
    main()
