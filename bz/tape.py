"""The tape: every trade between teams (and with the dealers) as it settles, read from the public feed. Pure functions;
market_watch.py feeds them. READ-ONLY.

Why: the trader only judges offers. Nobody was watching what really trades, where, at what price and between whom. The
tape gives a price reference per card from REAL trades (Saturday: commons and uncommons settle near 0.8 of book price, rares
near 0.97; 68 % of team trades and 88 % of the volume were on El Rastro).
"""
import statistics


def trade_of(event: dict, book: dict, rarity_of: dict):
    """A settlement event -> {"id","tick","kind","persona","venue","parties","price","fee","cards","ratio"} or None.
    kind is "team" for a trade between teams, "dealer" for a trade with a dealer. ratio = price / book price of the card
    when exactly one card changed hands (None for packs and bundles)."""
    if event.get("type") != "settlement":
        return None
    p = event.get("payload") or {}
    if p.get("kind") not in (None, "trade"):
        return None
    cards = [{"ref": i.get("ref"), "rarity": i.get("rarity") or rarity_of.get(i.get("ref")), "frm": i.get("frm"), "to": i.get("to"),
              "kind": i.get("kind")} for i in p.get("items") or []]
    price = p.get("price")
    ratio = None
    if len(cards) == 1 and cards[0]["kind"] == "card" and price and book.get(cards[0]["rarity"]):
        ratio = round(price / book[cards[0]["rarity"]], 2)
    return {"id": event.get("id"), "tick": p.get("tick", event.get("tick")), "settlement": p.get("settlement"),
            "kind": "dealer" if p.get("persona") else "team", "persona": p.get("persona"), "venue": p.get("venue"),
            "parties": p.get("parties") or [], "price": price, "fee": p.get("fee") or 0, "cards": cards, "ratio": ratio}


def reference_price(trades: list, ref: str, now_tick: int, window: int = 300, n: int = 5):
    """Median price of the last n TEAM trades of one card within `window` ticks, or None. Single-card trades only."""
    xs = [t for t in trades if t["kind"] == "team" and len(t["cards"]) == 1 and t["cards"][0]["ref"] == ref and t["price"]
          and 0 <= now_tick - t["tick"] <= window]
    xs = sorted(xs, key=lambda t: t["tick"])[-n:]
    return statistics.median(t["price"] for t in xs) if xs else None


def alerts_for(trade: dict, needs: set, spares: set, value_of) -> list:
    """Notes on one trade for what we do: a card we still need that traded (what we could have gained), a card we hold a
    spare of that traded (what our asks should be). value_of(ref) -> what one more copy is worth to us, or None."""
    out = []
    if trade["kind"] != "team" or len(trade["cards"]) != 1 or not trade["price"]:
        return out
    ref = trade["cards"][0]["ref"]
    v = value_of(ref) if (ref in needs or ref in spares) else None
    if ref in needs and v is not None:
        out.append(("TAPE-NEED", f"{ref} (we need it) traded at {trade['price']} P on {trade['venue']}: our value {v:.1f}, "
                                 f"gain about {v - trade['price']:+.1f} P"))
    if ref in spares and v is not None:
        out.append(("TAPE-SPARE", f"{ref} (we hold a spare) traded at {trade['price']} P on {trade['venue']}: a spare is worth "
                                  f"{v:.1f} to us"))
    return out


def summarize(trades: list, since_tick: int = 0) -> dict:
    """Aggregates for the report: per venue, per rarity (price / book), per card, per team, per dealer."""
    ts = [t for t in trades if t["tick"] >= since_tick]
    venues, rar, cards, buyers, sellers, dealers = {}, {}, {}, {}, {}, {}
    for t in ts:
        if t["kind"] == "dealer":
            d = dealers.setdefault(t["persona"], [0, 0])
            d[0] += 1
            d[1] += t["price"] or 0
            continue
        v = venues.setdefault(t["venue"], [0, 0])
        v[0] += 1
        v[1] += t["price"] or 0
        if t["ratio"] is not None:
            rar.setdefault(t["cards"][0]["rarity"], []).append(t["ratio"])
        for c in t["cards"]:
            cards.setdefault(c["ref"], []).append(t["price"])
            if c["to"]:
                buyers[c["to"]] = buyers.get(c["to"], 0) + 1
            if c["frm"]:
                sellers[c["frm"]] = sellers.get(c["frm"], 0) + 1
    return {"team_trades": sum(v[0] for v in venues.values()), "dealer_trades": sum(v[0] for v in dealers.values()),
            "venues": dict(sorted(venues.items(), key=lambda kv: -kv[1][0])),
            "rarity_ratio": {k: (round(statistics.median(v), 2), len(v)) for k, v in rar.items()},
            "cards": dict(sorted(cards.items(), key=lambda kv: -len(kv[1]))),
            "buyers": dict(sorted(buyers.items(), key=lambda kv: -kv[1])), "sellers": dict(sorted(sellers.items(), key=lambda kv: -kv[1])),
            "dealers": dealers}
