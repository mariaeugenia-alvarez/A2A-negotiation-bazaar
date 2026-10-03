"""Judge one offer made to us, by structure only: what we receive, what we give, the venue fee, and what the
difference is worth at our private values. The words around an offer are never read.

The maker's `give` is what we receive and the maker's `want` is what we hand over. The side that accepts pays the
venue fee (bazaar_sdk.open_thread). A card's value is bz.price.Valuer: book x our set multiplier x copy factor.

Actions
  accept   surplus clears the margin
  counter  a cash price exists that would clear it (suggested in counter_cash)
  ignore   we cannot do it (not the owner, not enough cash) or there is nothing to gain
  human    something we cannot value yet: a pack, a card type, or a card that completes a page (the page bonus is
           not in your_value and we have not measured it)
"""
import math

MIN_SURPLUS = 2.0   # primas: below this a deal is noise
MIN_SHARE = 0.10    # share of what we put in (cards given + cash paid) we keep as profit
HOUSE_FEE = (500, 1)  # El Rastro: 5 % + 1 P per card, assumed for a venue we have not seen


def fee_for(fees: dict, venue, cash: int, cards: int) -> int:
    bps, per_card = fees.get(venue) or HOUSE_FEE
    return math.ceil(bps * cash / 10000) + per_card * cards


ANCHOR = 0.15  # open a counter this share beyond the other side's price (never inside our clearing price)


def anchor(d: dict, share: float = ANCHOR):
    """Where a counter opens. judge() gives the price that only just clears our margin; we open beyond it, because
    the other side usually moves toward us. Selling: at least the clearing price and 15 % above their bid.
    Buying: at most the clearing price and 15 % below their ask. None when judge() found no counter."""
    low = d.get("counter_cash")
    if low is None:
        return None
    if d["cash_in"] and not d["cash_out"]:
        return max(low, math.ceil(d["cash_in"] * (1 + share)))
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
    """The structured offer we send back: {"give": ..., "want": ...}, or None when we cannot build one."""
    if d["cash_in"] and not d["cash_out"] and d.get("gives"):  # they would pay us: we sell the card(s) they asked for
        return {"give": {"assets": d["gives"]}, "want": {"cash": int(price)}}
    refs = [a["ref"] for a in (offer.get("give") or {}).get("assets") or []]
    if d["cash_out"] and not d["cash_in"] and refs:  # they ask cash for cards: we bid for those cards
        return {"give": {"cash": int(price)}, "want": {"cards": refs}}
    return None


def judge(offer: dict, valuer, by_ref: dict, cash: int, fees: dict, missing: dict, me_id: str) -> dict:
    out = {"offer": offer.get("id"), "maker": offer.get("maker"), "venue": offer.get("venue")}
    if offer.get("maker") == me_id or offer.get("status", "open") != "open":
        return {**out, "action": "ignore", "why": "not an open offer from someone else"}
    give, want = offer.get("give") or {}, offer.get("want") or {}
    owned = {ref: len(copies) for ref, copies in by_ref.items()}
    chosen, named, lost, cards_out = [], [], 0.0, 0

    for a in want.get("assets") or []:  # a named copy of ours
        ref = a.get("ref")
        mine = next((x for x in by_ref.get(ref, []) if x["id"] == a.get("id")), None)
        if a.get("kind") != "card" or mine is None:
            return {**out, "action": "ignore", "why": f"we do not hold asset {a.get('id')}"}
        lost += valuer.card_value(ref, owned=owned[ref] - 1)
        owned[ref] -= 1
        cards_out += 1
        named.append(mine["id"])
    for t in want.get("types") or []:  # any copy of a card: we hand over the least valuable one
        kind, _, ref = t.partition(":")
        if kind != "card":
            return {**out, "action": "human", "why": f"asks for a type we cannot value: {t}"}
        spare = [x for x in by_ref.get(ref, []) if x["id"] not in chosen]
        if not spare or owned.get(ref, 0) < 1:
            return {**out, "action": "ignore", "why": f"we hold no {ref}"}
        chosen.append(spare[-1]["id"])  # by_ref lists the most valuable copy first
        lost += valuer.card_value(ref, owned=owned[ref] - 1)
        owned[ref] -= 1
        cards_out += 1

    got, cards_in = 0.0, 0
    if give.get("types"):
        return {**out, "action": "human", "why": "offers a type we cannot value"}
    for a in give.get("assets") or []:
        ref = a.get("ref")
        if a.get("kind") != "card" or ref not in valuer.cards:
            return {**out, "action": "human", "why": f"offers {a.get('kind')} {ref}: not valued yet"}
        s = valuer.cards[ref]["set"]
        if len(missing.get(s, [])) == 1 and ref in missing[s]:
            return {**out, "action": "human", "why": f"{ref} completes the {s} page: bonus not measured"}
        got += valuer.card_value(ref, owned=owned.get(ref, 0))
        owned[ref] = owned.get(ref, 0) + 1
        cards_in += 1

    cash_in, cash_out = int(give.get("cash") or 0), int(want.get("cash") or 0)
    if cash_out > cash:
        return {**out, "action": "ignore", "why": f"costs {cash_out} P, we hold {cash}"}
    fee = fee_for(fees, offer.get("venue"), max(cash_in, cash_out), cards_in + cards_out)
    surplus = got + cash_in - lost - cash_out - fee
    margin = max(MIN_SURPLUS, MIN_SHARE * (lost + cash_out))
    res = {**out, "got": round(got, 1), "lost": round(lost, 1), "cash_in": cash_in, "cash_out": cash_out, "fee": fee,
           "surplus": round(surplus, 1), "margin": round(margin, 1), "assets": chosen, "gives": named + chosen,
           "counter_cash": None}
    if surplus >= margin:
        return {**res, "action": "accept", "why": f"+{surplus:.1f} P of value after a {fee} P fee"}
    if cash_out and not cash_in:  # we would pay: the most that still clears the margin
        top = math.floor(cash_out + surplus - margin)
        if top >= 1:
            return {**res, "action": "counter", "counter_cash": top, "why": f"pay at most {top}, not {cash_out}"}
    if cash_in and not cash_out:  # we would be paid: the least that still clears it
        low = math.ceil(cash_in + margin - surplus)
        return {**res, "action": "counter", "counter_cash": low, "why": f"ask at least {low}, not {cash_in}"}
    return {**res, "action": "ignore", "why": f"{surplus:+.1f} P of value, margin {margin:.1f}"}
