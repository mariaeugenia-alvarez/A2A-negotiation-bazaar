"""Judge one offer from another team, by structure only: what we receive, what we give, the venue fee, and what the
difference is worth at our private values. The words around an offer are never read.

The maker's `give` is what we receive and the maker's `want` is what we hand over.

Verified in play (Saturday, see TRADES.md):
  - the side that ACCEPTS pays the venue fee: we paid 9 + 2 P accepting an ask; we received a full 65 P when Team 13
    accepted our offer. So the fee counts against us only when we accept, never in a counter we post.
  - a complete page adds 25 % of the page's total value to every card of that page (Lavapies: LAV-01 16 -> 122).
    Values must come from the game (GameValues), not from our formula, or we would sell a page card far too cheap.
  - dealers (Abuela, El Chato, ...) are not ours: their offers reach us inside the dealer scripts' threads.

Actions
  accept   surplus clears the margin
  counter  a cash price exists that would clear it (suggested in counter_cash, the price for an offer WE post)
  ignore   not for us (a dealer, our own offer, a card already offered elsewhere), we cannot do it, or nothing to gain
  human    something we cannot value safely: a pack, a card type, several copies of one card, a page-completing card
"""
import math

MIN_SURPLUS = 2.0   # primas: below this a deal is noise
MIN_SHARE = 0.10    # share of what we put in (cards given + cash paid) we keep as profit
HOUSE_FEE = (500, 1)  # El Rastro: 5 % + 1 P per card, assumed for a venue we have not seen
DEALERS = {"abuela", "chato", "pilar"}  # dealer offers belong to the dealer scripts (agent.py / bz/haggle.py)


def fee_for(fees: dict, venue, cash: int, cards: int) -> int:
    bps, per_card = fees.get(venue) or HOUSE_FEE
    return math.ceil(bps * cash / 10000) + per_card * cards


class GameValues:
    """Values straight from the game, page bonus included. lose(asset): what giving that held copy costs us = its
    `your_value` in /api/me. gain(ref): what one more copy is worth = /api/me/value. Cached by the caller per holdings."""

    def __init__(self, b, assets: list, cache: dict = None):
        self.b, self.by_id = b, {a["id"]: a for a in assets}
        self.cache = {} if cache is None else cache

    def lose(self, asset: dict) -> float:
        return float(self.by_id[asset["id"]].get("your_value") or 0)

    def gain(self, ref: str) -> float:
        if ref not in self.cache:
            self.cache[ref] = float(self.b.value(ref)["your_value"])
        return self.cache[ref]


class FormulaValues:
    """Our formula (bz.price.Valuer), WITHOUT the page bonus. Kept for tests and simulations only."""

    def __init__(self, valuer, by_ref: dict):
        self.v, self.held = valuer, {ref: len(c) for ref, c in by_ref.items()}

    def lose(self, asset: dict) -> float:
        return self.v.card_value(asset["ref"], owned=self.held.get(asset["ref"], 1) - 1)

    def gain(self, ref: str) -> float:
        if ref not in self.v.cards:
            raise KeyError(ref)
        return self.v.card_value(ref, owned=self.held.get(ref, 0))


ANCHOR = 0.15  # open a counter this share beyond the other side's price (never inside our clearing price)


def anchor(d: dict, share: float = ANCHOR, best_bid: int = 0):
    """Where a counter opens. Selling: at least our clearing price, 15 % above their bid, and above the best bid anyone
    made for this card recently (MAL-10 went for 65 while bids of 70-82 had been seen). Buying: at most our clearing
    price and 15 % below their ask. None when judge() found no counter."""
    low = d.get("counter_cash")
    if low is None:
        return None
    if d["cash_in"] and not d["cash_out"]:
        return max(low, math.ceil(d["cash_in"] * (1 + share)), (best_bid + 1) if best_bid else 0)
    if d["cash_out"] and not d["cash_in"]:
        return max(1, min(low, math.floor(d["cash_out"] * (1 - share))))
    return None


def is_lowball(d: dict, price: int, share: float = 0.5) -> bool:
    """A bid for their card at under half their ask: a probe, not a real offer. Kept, but rationed (see trader.py)."""
    return bool(d["cash_out"]) and not d["cash_in"] and price < share * d["cash_out"]


def cost(d: dict) -> int:
    """Primas an accept spends if we are the accepter: the cash we pay plus the venue fee."""
    return int(d.get("cash_out") or 0) + int(d.get("fee") or 0)


def counter_body(offer: dict, d: dict, price: int):
    """The structured offer we send back: {"give": ..., "want": ...}, or None when we cannot build one.

    Only for plain cash-for-cards offers. In a swap (cards both ways, with or without cash) the clearing price in
    judge() counts the cards they give us, and a cash-only counter would drop them: we would sell below value."""
    if d["cash_in"] and not d["cash_out"] and d.get("gives") and not d.get("got"):  # they would pay us: we sell the card(s) they asked for
        return {"give": {"assets": d["gives"]}, "want": {"cash": int(price)}}
    refs = [a["ref"] for a in (offer.get("give") or {}).get("assets") or []]
    if d["cash_out"] and not d["cash_in"] and refs and not d.get("lost"):  # they ask cash for cards: we bid for those cards
        return {"give": {"cash": int(price)}, "want": {"cards": refs}}
    return None


def judge(offer: dict, values, by_ref: dict, cash: int, fees: dict, missing: dict, me_id: str,
          reserved=frozenset()) -> dict:
    """values: GameValues (live) or a bz.price.Valuer (wrapped in FormulaValues, for tests).
    reserved: asset ids already given in one of our open offers; they are never offered or handed over twice."""
    if hasattr(values, "card_value"):
        values = FormulaValues(values, by_ref)
    out = {"offer": offer.get("id"), "maker": offer.get("maker"), "venue": offer.get("venue")}
    if offer.get("maker") == me_id or offer.get("status", "open") != "open":
        return {**out, "action": "ignore", "why": "not an open offer from someone else"}
    if offer.get("maker") in DEALERS or offer.get("venue") is None:
        return {**out, "action": "ignore", "why": "a dealer's offer: the dealer scripts handle it"}
    give, want = offer.get("give") or {}, offer.get("want") or {}
    chosen, named, lost, cards_out, refs_out = [], [], 0.0, 0, []

    for a in want.get("assets") or []:  # a named copy of ours
        ref = a.get("ref")
        mine = next((x for x in by_ref.get(ref, []) if x["id"] == a.get("id")), None)
        if a.get("kind") != "card" or mine is None:
            return {**out, "action": "ignore", "why": f"we do not hold asset {a.get('id')}"}
        if mine["id"] in reserved:
            return {**out, "action": "ignore", "why": f"{ref} #{mine['id']} is already in another open offer of ours"}
        named.append(mine["id"])
        refs_out.append(ref)
    for t in want.get("types") or []:  # any copy of a card: we hand over the least valuable free copy
        kind, _, ref = t.partition(":")
        if kind != "card":
            return {**out, "action": "human", "why": f"asks for a type we cannot value: {t}"}
        free = [x for x in reversed(by_ref.get(ref, [])) if x["id"] not in chosen and x["id"] not in named
                and x["id"] not in reserved]
        if not free:
            why = f"we hold no free {ref}" + (" (our copy is in another open offer)" if by_ref.get(ref) else "")
            return {**out, "action": "ignore", "why": why}
        chosen.append(free[0]["id"])
        refs_out.append(ref)
    if len(set(refs_out)) < len(refs_out):
        return {**out, "action": "human", "why": "asks for several copies of one card: values interact"}
    for ref in refs_out:
        asset = next(x for x in by_ref[ref] if x["id"] in named + chosen)
        lost += values.lose(asset)
        cards_out += 1

    got, cards_in = 0.0, 0
    if give.get("types"):
        return {**out, "action": "human", "why": "offers a type we cannot value"}
    refs_in = [a.get("ref") for a in give.get("assets") or []]
    if len(set(refs_in)) < len(refs_in) or set(refs_in) & set(refs_out):
        return {**out, "action": "human", "why": "several copies of one card, or the same card both ways"}
    for a in give.get("assets") or []:
        ref = a.get("ref")
        if a.get("kind") != "card":
            return {**out, "action": "human", "why": f"offers {a.get('kind')} {ref}: not valued yet"}
        s = ref.split("-")[0]
        if len(missing.get(s, [])) == 1 and ref in missing[s]:
            return {**out, "action": "human", "why": f"{ref} completes the {s} page: decide by hand"}
        try:
            got += values.gain(ref)
        except Exception:  # unknown card, or the value call failed: never guess
            return {**out, "action": "human", "why": f"cannot value {ref}"}
        cards_in += 1

    cash_in, cash_out = int(give.get("cash") or 0), int(want.get("cash") or 0)
    if cash_out > cash:
        return {**out, "action": "ignore", "why": f"costs {cash_out} P, we hold {cash}"}
    fee = fee_for(fees, offer.get("venue"), max(cash_in, cash_out), cards_in + cards_out)  # ours only if WE accept
    surplus = got + cash_in - lost - cash_out - fee
    margin = max(MIN_SURPLUS, MIN_SHARE * (lost + cash_out))
    res = {**out, "got": round(got, 1), "lost": round(lost, 1), "cash_in": cash_in, "cash_out": cash_out, "fee": fee,
           "surplus": round(surplus, 1), "margin": round(margin, 1), "assets": chosen, "gives": named + chosen,
           "counter_cash": None}
    if surplus >= margin:
        return {**res, "action": "accept", "why": f"+{surplus:.1f} P of value after a {fee} P fee"}
    base = got - lost  # a counter is an offer WE post: they accept, so they pay the fee
    if cash_out and not cash_in:  # we would pay: the most that still clears the margin
        top = math.floor(base - margin)
        if top >= 1:
            return {**res, "action": "counter", "counter_cash": min(top, cash), "why": f"pay at most {top}, not {cash_out}"}
    if cash_in and not cash_out:  # we would be paid: the least that still clears it
        low = math.ceil(margin - base)
        return {**res, "action": "counter", "counter_cash": low, "why": f"ask at least {low}, not {cash_in}"}
    return {**res, "action": "ignore", "why": f"{surplus:+.1f} P of value, margin {margin:.1f}"}
