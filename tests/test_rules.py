"""The two basic rules, tried on thousands of random cases. python3 tests/test_rules.py

  1. Never offer more than the other side already asks (buying), never ask less than it already bids (selling).
  2. Never accept below our limit / what the thing is worth to us (a deal there loses points).

Covers the dealer haggle (bz/haggle.py), the offers other teams make us (bz/trade.py judge/anchor/counter_body)
and the duels (bz/duel.py). Random but seeded: a failure prints the case that broke the rule.
"""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bz.log as L  # noqa: E402

L.LOG_DIR = tempfile.mkdtemp()
import bz.haggle as H  # noqa: E402
from bz.duel import decide, inside, surplus  # noqa: E402
from bz.price import Valuer  # noqa: E402
from bz.trade import anchor, counter_body, judge  # noqa: E402

H._wait = lambda b: b.wait_tick()  # no sleeping


# ---------------------------------------------------------------- dealer haggle

class FakeDealer:
    """A dealer with a standing offer. It records every price we send next to the price it had posted at that moment."""

    def __init__(s, rng, side):
        s.rng, s.side = rng, side
        buy = side == "buy"
        s.ask = rng.randint(8, 40) if buy else rng.randint(2, 30)
        s.floor = s.ask - rng.randint(0, 15) if buy else s.ask + rng.randint(0, 15)  # the secret limit
        s.floor = max(1, s.floor)
        s.pat, s.msgs, s.status, s.offers, s.last_ours, s.sent = rng.randint(2, 10), 0, "open", [], None, []
        s._post(s.ask)

    def _post(s, p, final=False):
        for o in s.offers:
            o["status"] = "withdrawn"
        leg = {"cash": p}
        s.offers.append({"id": len(s.offers) + 1, "maker": "d", "status": "open", "final": final,
                         "want": leg if s.side == "buy" else {}, "give": leg if s.side == "sell" else {}})

    def wait_tick(s):
        if s.status == "accepting":
            s.status = "deal"

    def my_threads(s, status=None): return {"threads": []}
    def open_thread(s, w, topic=None): return {"id": 7}
    def thread(s, tid): return {"status": s.status, "standing_offers": s.offers, "messages": []}
    def close_thread(s, tid): s.status = "closed"

    def accept(s, oid):
        s.status = "accepting"
        s.accepted = next(o for o in s.offers if o["id"] == oid)

    def say(s, tid, text, price):
        buy = s.side == "buy"
        s.sent.append((price, s.ask))
        s.msgs += 1
        if (buy and price >= s.floor) or (not buy and price <= s.floor):  # it takes our offer when it reaches its limit
            s.status, s.accepted = "accepting", None
            return
        if s.last_ours is not None:
            step = abs(price - s.last_ours)
            s.ask = max(s.floor, s.ask - max(1, step // 2)) if buy else min(s.floor, s.ask + max(1, step // 2))
        s.last_ours = price
        s._post(s.ask, final=s.msgs >= s.pat)


def check_haggle(seed: int):
    rng = random.Random(seed)
    side = rng.choice(["buy", "sell"])
    d = FakeDealer(rng, side)
    buy = side == "buy"
    limit = rng.randint(3, 45)
    opening = rng.randint(1, 45)
    kw = {}
    if rng.random() < .5:
        kw = dict(target=rng.randint(5, 40), accept_at=rng.randint(5, 40), patience=rng.randint(2, 9))
    first_ask = d.ask
    r = H.haggle(d, "d", {}, side, opening, limit, **kw)
    ctx = f"seed {seed}: {side} limit {limit} opening {opening} {kw} dealer ask {first_ask} floor {d.floor} -> {r}"
    for p in r["ours"]:  # rule 2 on every price we send
        assert (p <= limit) if buy else (p >= limit), "we offered beyond our own limit. " + ctx
    for price, posted in d.sent:  # rule 1
        assert (price < posted) if buy else (price > posted), f"we offered {price} while it had {posted} posted. " + ctx
    if r["status"] == "deal":
        assert (r["price"] <= limit) if buy else (r["price"] >= limit), "deal outside our limit. " + ctx
    return r


# ---------------------------------------------------------------- offers from other teams

RAR = {"common": {"book": 10}, "uncommon": {"book": 25}, "rare": {"book": 70}}
CARDS = [(f"{s}-{i:02d}", r) for s in ("LAV", "MAL", "LAT") for i, r in enumerate(["common"] * 5 + ["uncommon"] * 3 + ["rare"] * 2, 1)]
CATALOG = {"rarities": RAR, "values": {"copy_marginals": [1.0, 0.25, 0.1]}, "packs": [],
           "sets": [{"id": s, "released": True, "cards": [{"id": c, "rarity": r, "page": True} for c, r in CARDS if c.startswith(s)]}
                    for s in ("LAV", "MAL", "LAT")]}


def check_judge(seed: int):
    rng = random.Random(seed)
    aff = {s: rng.choice([.5, .9, 1.1, 1.6]) for s in ("LAV", "MAL", "LAT")}
    held, by_ref, nid = {}, {}, 1
    for ref, _ in rng.sample(CARDS, rng.randint(2, 14)):
        for _ in range(rng.choice([1, 1, 2, 3])):
            by_ref.setdefault(ref, []).append({"id": nid, "kind": "card", "ref": ref})
            nid += 1
    held = {ref: len(c) for ref, c in by_ref.items()}
    v = Valuer(CATALOG, aff, held)
    for ref in by_ref:
        by_ref[ref].sort(key=lambda a: -v.card_value(ref, 0))
    cash = rng.randint(0, 300)
    fees = {"rastro": (500, 1), "v": (0, 0)}

    def asset(ref): return {"id": 1000 + rng.randint(0, 9999), "kind": "card", "ref": ref, "rarity": "common"}
    mine = [a for c in by_ref.values() for a in c]
    give = {"cash": rng.choice([0, 0, rng.randint(1, 80)]), "assets": [asset(rng.choice(CARDS)[0]) for _ in range(rng.choice([0, 1, 2]))], "types": []}
    want = {"cash": rng.choice([0, 0, rng.randint(1, 80)]), "assets": [], "types": []}
    for _ in range(rng.choice([0, 1, 2])):
        if rng.random() < .5 and mine:
            a = rng.choice(mine)
            want["assets"].append({"id": a["id"], "kind": "card", "ref": a["ref"]})
        else:
            want["types"].append("card:" + rng.choice(CARDS)[0])
    offer = {"id": seed, "maker": "other", "venue": rng.choice(list(fees)), "status": "open", "give": give, "want": want}
    d = judge(offer, v, by_ref, cash, fees, {}, "me")
    ctx = f"seed {seed}: {d} offer {offer}"
    if d["action"] == "accept":
        assert d["cash_out"] <= cash, "accepts an offer we cannot pay. " + ctx
        assert abs(d["got"] + d["cash_in"] - d["lost"] - d["cash_out"] - d["fee"] - d["surplus"]) < 0.11, "surplus does not add up. " + ctx
        assert d["surplus"] >= d["margin"] >= 2.0, "accepts below the margin. " + ctx
        assert d["surplus"] > 0, "accepts a loss. " + ctx
    if d["action"] == "counter":
        p = anchor(d)
        if p is not None:
            body = counter_body(offer, d, p)
            if body is None:
                return "counter (none sent)"
            if d["cash_in"] and not d["cash_out"]:  # we sell: never ask below what clears our margin, nor below their bid
                assert p >= d["counter_cash"] and p >= d["cash_in"], "counter asks too little. " + ctx
                assert d["lost"] + d["fee"] + 2 <= p + 1e-9 or d["lost"] + 2 <= p, "counter sells below value + margin. " + ctx
            if d["cash_out"] and not d["cash_in"]:  # we buy: never bid above what clears our margin, nor above their ask
                assert p <= d["counter_cash"] and p <= d["cash_out"], "counter bids too much. " + ctx
                assert d["got"] - p >= 2 - 1e-9, "counter pays more than it is worth. " + ctx
            if body and "cash" in body["give"]:
                assert body["give"]["cash"] <= cash, "counter promises cash we do not have. " + ctx
    return d["action"]


# ---------------------------------------------------------------- duels

def check_duel(seed: int):
    rng = random.Random(seed)
    role = rng.choice(["buyer", "seller"])
    limit = rng.randint(20, 200)
    two = rng.random() < .4
    deadline = 130
    tick = rng.randint(100, 129)
    msgs, t = [], 100
    # a rival that opens far from our limit and moves toward it, sometimes past it
    price = limit * rng.uniform(.6, 1.4)
    for _ in range(rng.randint(0, 6)):
        msgs.append({"tick": t, "from": "rival", "price": round(price), "days": rng.randint(0, 10) if two else None, "text": ""})
        if rng.random() < .6:
            msgs.append({"tick": t, "from": "you", "price": round(limit * rng.uniform(.3, 1.5)), "days": rng.randint(0, 10) if two else None, "text": ""})
        price += (limit - price) * rng.uniform(.05, .4) * (1 if role == "buyer" else 1)
        t += 1
    his = [m for m in msgs if m["from"] != "you"]
    d = {"duel": 1, "role": role, "your_limit": limit, "decay_per_round": rng.choice([.06, .08, .1]), "deadline_tick": deadline,
         "issues": ["price", "days"] if two else ["price"], "your_days_weight": rng.uniform(.1, 2) if two else None,
         "days_meaning": rng.choice(["gain per day", "cost per day delayed"]), "messages": msgs,
         "rival_offer": {"price": his[-1]["price"], "days": his[-1]["days"], "tick": tick} if his and rng.random() < .8 else None}
    a = decide(d, tick, beta=rng.choice([1.5, 2, 3]), rounds_budget=rng.randint(2, 5), open_frac=rng.choice([.25, .45]))
    ctx = f"seed {seed}: {role} limit {limit} -> {a} duel {d}"
    if a["action"] == "offer":
        p = a["price"]
        assert inside(role, limit, p), "we offered beyond our limit. " + ctx
        assert p >= 1 and (a["days"] is None or 0 <= a["days"] <= 10), "bad price or day. " + ctx
        theirs = d["rival_offer"]
        if theirs and theirs.get("price") is not None and not two:  # rule 1, price only
            assert (p < theirs["price"]) if role == "buyer" else (p > theirs["price"]) or inside(role, limit, theirs["price"]) is False, \
                "we offered more than he already asks / less than he bids. " + ctx
    if a["action"] == "accept":
        r = d["rival_offer"]
        assert r and inside(role, limit, r["price"]), "accepts outside our limit. " + ctx
        if not two:  # with a day in play, closing exactly at the limit can pay through the day (U >= 1): by design
            assert surplus(role, limit, r["price"]) > 0, "accepts a deal worth nothing. " + ctx
    return a["action"]


def run(name, fn, n):
    counts = {}
    for seed in range(n):
        out = fn(seed)
        key = out["status"] if isinstance(out, dict) else out
        counts[key] = counts.get(key, 0) + 1
    print(f"ok {name}: {n} random cases, outcomes {counts}")


if __name__ == "__main__":
    run("haggle", check_haggle, 3000)
    run("judge", check_judge, 5000)
    run("duel", check_duel, 3000)
