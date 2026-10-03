"""Standing quotes: bids for the page cards we miss, asks for our spares. Pure functions; trader.py posts them.

Why (Saturday, see TRADES.md): our standing bids gave 17.5 of our 24.2 neg_points, because other teams accepted them
(they pay the fee) and neg_points grows by the value we gain at our private values. Team trades settle near 0.8 of book
for commons and uncommons, 0.93-0.97 for rares (feed log, ticks 223-424).

Price rules, every price checked against the game's value (page bonus included):
  bid   min(our value - margin, max(market reference, best bid seen from others + 1))
  ask   max(spare value + margin, market reference)
Priority: cards of the page closest to completion first (a complete page adds 25 % of its total value, once), then by
expected gain per primas. Never a bid for a card we hold, already bid for (by anyone on our key), or cannot afford
within the cap. Never an ask for anything but a spare copy (a second copy is worth ~25 % to us).
"""
import math

MARKET = {"common": 0.8, "uncommon": 0.8, "rare": 0.97}  # median team-trade price / book, Saturday feed
MIN_SURPLUS = 2.0
MIN_SHARE = 0.10
CLOSE = 3  # a page this many cards from complete or fewer gets its bids first
FLOOR = 0.5  # lowest team-trade price / book seen on Saturday: a bid below it would almost never fill
RARE_FLOOR = 0.9  # rare and epic bids below 0.9 x book: 0 filled of 199 in the whole market (feed, ticks 230-1420)


def margin(value: float) -> float:
    return max(MIN_SURPLUS, MIN_SHARE * value)


def bid_price(value: float, book: int, rarity: str, best_other: int = 0):
    """None when no price both clears our margin and is at least 1."""
    ref = round(MARKET.get(rarity, 0.8) * book)
    top = math.floor(value - margin(value))
    p = min(top, max(ref, best_other + 1 if best_other else 0))
    low = RARE_FLOOR if rarity in ("rare", "epic") else FLOOR
    return p if p >= 1 and p >= low * book else None


def ask_price(spare_value: float, book: int, rarity: str) -> int:
    return max(math.ceil(spare_value + margin(spare_value)), round(MARKET.get(rarity, 0.8) * book))


def plan(missing: dict, pages: list, spares: list, value_of, rarity_of, book: dict, best_other: dict,
         pending: set, budget: int, max_quotes: int = 12) -> list:
    """Quotes we want open now, best first.

    missing: set -> page cards we lack. pages: [{"set", "have", "of"}]. spares: our spare copies (asset dicts with ref
    and your_value). value_of(ref): the game's value of one more copy. best_other: ref -> best bid by another team.
    pending: cards already asked for by an open bid on our key. budget: cash our new bids may promise.
    Returns [{"side": "bid"|"ask", "ref", "price", "value", "gain", "asset"?}].
    """
    left = {p["set"]: p["of"] - p["have"] for p in pages}
    bids = []
    for s, refs in missing.items():
        for ref in refs:
            if ref in pending:
                continue
            r = rarity_of(ref)
            v = value_of(ref)
            p = bid_price(v, book[r], r, best_other.get(ref, 0))
            if p is None:
                continue
            gain = v - p
            if gain < margin(v):
                continue
            bids.append({"side": "bid", "ref": ref, "price": p, "value": round(v, 1), "gain": round(gain, 1),
                         "set": s, "left": left.get(s, 99), "ratio": round(p / book[r], 2)})
    # a page 3 cards or fewer from complete comes first (its bonus is in reach), then the best gain per primas promised
    bids.sort(key=lambda q: (0 if q["left"] <= CLOSE else 1, q["left"] if q["left"] <= CLOSE else 0, -q["gain"] / q["price"]))
    out, spent = [], 0
    for q in bids:
        if spent + q["price"] > budget:
            continue
        out.append(q)
        spent += q["price"]
    for a in spares:
        r = rarity_of(a["ref"])
        v = float(a.get("your_value") or 0)
        p = ask_price(v, book[r], r)
        out.append({"side": "ask", "ref": a["ref"], "price": p, "value": v, "gain": round(p - v, 1), "asset": a["id"],
                    "ratio": round(p / book[r], 2)})
    return out[:max_quotes]


def free_spares(by_ref: dict, listed_ids: set) -> list:
    """Copies we may offer for sale. A card is a spare only beyond the FIRST copy, and a copy already in an open offer
    (ours or anyone's on our key) counts as sold: with 2 copies and 1 already listed there is no spare left. Offering the
    other copy too could sell both and break a page (RET-01, RET-08, SAL-02 at tick 1041). Lowest value first, ties by id."""
    out = []
    for ref, copies in by_ref.items():
        cap = len(copies) - 1 - sum(1 for a in copies if a["id"] in listed_ids)
        if cap <= 0:
            continue
        free = sorted((a for a in copies if a["id"] not in listed_ids), key=lambda a: (a.get("your_value") or 0, a["id"]))
        out.extend(free[:cap])
    return out
