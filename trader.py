"""Offers from OTHER TEAMS, judged every tick by bz/trade.py. Only structure is read: what the offer gives and wants.

    python3 trader.py                 # SHADOW: prints and logs what it would do, sends nothing
    python3 trader.py --live          # LIVE on team offers addressed to us: accepts clear wins, answers the rest with a counter
    python3 trader.py --live --live-boards   # ALSO accepts clear wins from the public boards (40 P cap, read from the log)
    python3 trader.py --once          # one pass, then stop
    touch logs/trader.pause           # LIVE stops acting at once (it keeps logging); delete the file to resume

Scope: teams only. Dealer offers (Abuela, El Chato, Pilar) belong to the dealer scripts and are ignored (bz/trade.py).
Values come from the game (page bonus included), never from our formula.
Safety: one accept per tick and a 2-tick pause after it; a card in one of our open offers is never offered or handed over
again; we never sell below the best bid seen for that card in the last 60 ticks; at most 3 real counters outstanding,
lowball probes rationed to one per maker per 30 ticks. Every counter, accept and settlement goes to logs/trader*.jsonl.
"""
import argparse
import fcntl
import json
import os
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log
from bz.state import State
from bz.quoter import Quoter
from bz.trade import GameValues, anchor, cost, counter_body, is_lowball, judge, wanted_refs

PAUSE = os.path.join(log.LOG_DIR, "trader.pause")
ACCEPTS = os.path.join(log.LOG_DIR, "trader_accept.jsonl")
COUNTER_TICKS = 20      # how long our counter stays open
MAX_OUTSTANDING = 3     # real counters; lowball probes do not use these slots
MAKER_COOLDOWN = 10     # ticks before we counter the same maker about the same cards again
LOWBALL_COOLDOWN = 30   # a bid under half their ask is a probe: at most one per maker this often
BOARD_BUDGET = 40       # primas we may spend accepting public-board offers (cash + fee), counted from the log
BID_MEMORY = 60         # ticks a bid for a card is remembered: we never sell that card below it


def spent_on_boards() -> int:
    """What earlier accepts from the public boards already cost, read from the log so a restart cannot reset the cap."""
    total = 0
    if os.path.exists(ACCEPTS):
        for line in open(ACCEPTS, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("source") == "board":
                total += cost(e)
    return total


def venue_fees(b) -> dict:
    return {v["venue"]: (v.get("fee_bps", 0), v.get("fee_per_card", 0)) for v in b.venues().get("venues", [])}


def single_card_bid(o: dict):
    """(card, cash) when an offer pays cash for exactly one card, else None: what someone is willing to pay for it."""
    give, want = o.get("give") or {}, o.get("want") or {}
    refs = wanted_refs(o)
    if give.get("cash") and len(refs) == 1 and not give.get("assets") and not want.get("cash"):
        return refs[0], int(give["cash"])
    return None


def refs_of(o: dict) -> set:
    g = o.get("give") or {}
    return {a.get("ref") for a in g.get("assets") or []} | set(wanted_refs(o))


def settlement_for(b, me_id: str, refs: set, since: int):
    """The feed's settlement of our deal with these cards, or None. Our cash alone cannot tell: another session spends it."""
    for e in b.feed(limit=300).get("events", []):
        p = e.get("payload") or {}
        if e.get("type") == "settlement" and me_id in p.get("parties", []) and p.get("tick", 0) >= since \
                and refs & {i.get("ref") for i in p.get("items", [])}:
            return p
    return None


def check_outcomes(b, me_id: str, tick: int, sent: dict, open_ids: set) -> None:
    """A counter that is no longer open either settled or expired: the feed's settlements say which."""
    pending = [k for k, s in sent.items() if s["outcome"] is None and s["offer_id"] not in open_ids and tick > s["tick"]]
    for k in pending:
        s = sent[k]
        hit = settlement_for(b, me_id, set(s["refs"]), s["tick"])
        s["outcome"] = "accepted" if hit else "expired"
        log.event("trader_outcome", incoming=k, counter=s["offer_id"], maker=s["maker"], price=s["price"],
                  outcome=s["outcome"], settled_price=hit.get("price") if hit else None, tick=tick, opened=s["tick"])
        log.say(f"[t{tick}] counter {s['offer_id']} to {s['maker']} at {s['price']}: {s['outcome'].upper()}"
                + (f" (settled at {hit.get('price')})" if hit else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="act on team offers addressed to us: accept clear wins, send counters")
    ap.add_argument("--live-boards", action="store_true", help="with --live: also accept clear wins from the public boards")
    ap.add_argument("--budget", type=int, default=BOARD_BUDGET, help="most we spend on public-board accepts (cash + fee)")
    ap.add_argument("--cancel-stale-bids", action="store_true",
                    help="with --live: cancel our open bid for a card we already hold (off: only warn)")
    ap.add_argument("--quotes", action="store_true",
                    help="keep standing bids for missing page cards and asks for spares (bz/quoter.py); posts only with --live")
    ap.add_argument("--quote-budget", type=int, default=180, help="most cash our standing bids may promise at once")
    ap.add_argument("--notify", action="store_true", help="macOS notifications for STOP, WIN, PAGE and FOREIGN alerts")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-boards", dest="boards", action="store_false", help="do not scan the public boards")
    args = ap.parse_args()
    os.makedirs(log.LOG_DIR, exist_ok=True)
    lock = open(os.path.join(log.LOG_DIR, "trader.lock"), "w")
    try:  # a second trader on the same key could accept twice
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another trader.py is already running (logs/trader.lock)")
    b = connect()
    st, fees, fees_at, seen = State(b), {}, -999, set()
    active, boards_at, cool_until = [], -999, 0
    sent = {}       # incoming offer id -> our counter
    last_low = {}   # maker -> tick of our last lowball probe
    bids = {}       # card -> [(tick, cash)] bids seen from anyone
    check = None    # (decision, offer, tick) of the last accept, to read its settlement
    value_cache, holdings = {}, None
    quoter = Quoter(b, args.quote_budget, notify=args.notify) if args.quotes else None
    log.say(f"trader: {'LIVE' if args.live else 'shadow'}" + (f" + quotes (budget {args.quote_budget} P)" if quoter else "")
            + (f" + boards (budget {args.budget} P, {spent_on_boards()} P already spent)" if args.live and args.live_boards else ""))
    while True:
        try:
            tick = b.clock()["tick"]
            st.refresh()
            me_id = st.me["id"]
            if tick - fees_at >= 20:
                fees, fees_at = venue_fees(b), tick
            now_holdings = tuple(sorted(a["id"] for a in st.me["assets"]))
            if now_holdings != holdings:  # what one more copy is worth changes with what we hold
                value_cache, holdings = {}, now_holdings
            values, by_ref, missing = GameValues(b, st.me["assets"], value_cache), st.by_ref(), st.missing()
            mine = b.my_offers().get("offers") or []
            ours_open = [o for o in mine if o.get("maker") == me_id and o.get("status") == "open"]
            reserved = {a["id"] for o in ours_open for a in (o.get("give") or {}).get("assets") or []}
            # our open bids (whoever posted them: a script or a person on our key) promise cash and ask for cards
            bids_open = [o for o in ours_open if (o.get("give") or {}).get("cash") and wanted_refs(o)]
            committed = sum(int(o["give"]["cash"]) for o in bids_open)  # every bid promises cash, counters included
            # only PUBLIC bids (no "to") are standing bids for missing cards. A counter to one team may be a
            # deliberate bid for a second copy below its value: it is neither pending nor stale.
            public_bids = [o for o in bids_open if not o.get("to")]
            pending = {r for o in public_bids for r in wanted_refs(o)}
            free_cash = max(0, st.cash - committed)
            stale = [o for o in public_bids if any(r in by_ref for r in wanted_refs(o))]
            for o in stale:  # we got the card another way: if this bid fills, we pay for a duplicate worth ~25 %
                key = ("stale", o["id"])
                if key not in seen:
                    seen.add(key)
                    log.event("trader_stale_bid", tick=tick, offer=o["id"], cards=wanted_refs(o), cash=o["give"]["cash"])
                    log.say(f"[t{tick}] STALE BID {o['id']}: {o['give']['cash']} P for {wanted_refs(o)}, which we already hold"
                            + ("" if args.cancel_stale_bids else " (cancel it by hand, or run with --cancel-stale-bids)"))
            todo = [(o, "to_us") for o in mine if o.get("to") == me_id]
            if args.boards:
                if tick - boards_at >= 10:  # which boards hold offers: look at all of them now and then
                    active = [v for v in fees if b.board(v).get("offers")]
                    boards_at = tick
                for v in active:
                    todo += [(o, "board") for o in b.board(v).get("offers") or [] if not o.get("to")]
            for o, _ in todo:  # remember what people pay for each card
                bid = single_card_bid(o)
                if bid and o.get("maker") != me_id:
                    bids.setdefault(bid[0], []).append((tick, bid[1]))

            def best_bid(ref):
                return max((p for t, p in bids.get(ref, []) if tick - t <= BID_MEMORY), default=0)

            decisions = []
            for o, source in todo:
                if o.get("status") != "open":
                    continue
                d = judge(o, values, by_ref, free_cash, fees, missing, me_id, reserved, pending)
                sale = single_card_bid(o)
                if d["action"] == "accept" and sale and sale[1] < best_bid(sale[0]):  # someone recently paid more
                    d = {**d, "action": "counter", "counter_cash": best_bid(sale[0]),
                         "why": f"{sale[1]} is below the {best_bid(sale[0])} P bid seen for {sale[0]}"}
                decisions.append((o, source, d))
                key = (d["offer"], d["action"], d.get("surplus"))
                if key not in seen and (source == "to_us" or d["action"] in ("accept", "counter", "human")):
                    seen.add(key)
                    log.event("trader", tick=tick, expires=o.get("expires_tick"), live=args.live, source=source, **d)
                    if source == "to_us" or d["action"] in ("accept", "human"):
                        log.say(f"[t{tick}] {source} offer {d['offer']} on {d['venue']} from {d['maker']}: "
                                f"{d['action'].upper()} · {d['why']}")

            check_outcomes(b, me_id, tick, sent, {o["id"] for o in mine if o.get("maker") == me_id})
            if check and tick >= check[2] + 2:  # the accept has settled: what did the game record?
                w, o, t0 = check
                p = settlement_for(b, me_id, refs_of(o), t0)
                log.event("trader_settlement", offer=w["offer"], expected_cash=w["cash_out"] or w["cash_in"],
                          expected_fee=w["fee"], found=bool(p), price=(p or {}).get("price"), fee=(p or {}).get("fee"), tick=tick)
                log.say(f"[t{tick}] settlement of offer {w['offer']}: "
                        + (f"price {p.get('price')}, fee {p.get('fee')}" if p else "NOT FOUND (refused or taken by someone else?)"))
                check = None
            acting = args.live and not os.path.exists(PAUSE)
            if args.live and not acting and tick % 10 == 0:
                log.say("trader: paused (logs/trader.pause)")
            if quoter:
                try:
                    quoter.step(tick, st, mine, values, best_bid, settlement_for, PAUSE, acting)
                except BazaarError as e:
                    quoter.guard.error(tick, e.code)
                    log.say(f"quoter: {e}")
                acting = args.live and not os.path.exists(PAUSE)  # a guard stop pauses everything at once
            if acting:
                if args.cancel_stale_bids:
                    for o in stale:
                        try:
                            b.cancel(o["id"])
                            log.event("trader_cancel", tick=tick, offer=o["id"], cards=wanted_refs(o), why="stale bid")
                            log.say(f"[t{tick}] CANCELLED stale bid {o['id']} for {wanted_refs(o)}")
                        except BazaarError as e:
                            log.say(f"[t{tick}] cancel {o['id']} refused: {e}")
                if tick >= cool_until:
                    left = args.budget - spent_on_boards()
                    pool = [x for x in decisions if x[2]["action"] == "accept"
                            and (x[1] == "to_us" or (args.live_boards and cost(x[2]) <= left))]
                    if pool:
                        o, source, w = max(pool, key=lambda x: x[2]["surplus"])
                        b.accept(w["offer"], assets=w["assets"] or None)
                        cool_until, check = tick + 2, (w, o, tick)
                        reserved |= set(w["gives"])
                        log.event("trader_accept", tick=tick, source=source, **w)
                        log.say(f"[t{tick}] ACCEPTED offer {w['offer']} from {w['maker']} (+{w['surplus']} P, "
                                f"spends up to {cost(w)} P)")
                outstanding = sum(1 for s in sent.values() if s["outcome"] is None and not s.get("low"))
                for o, source, d in decisions:
                    if source != "to_us" or d["action"] != "counter" or o["id"] in sent:
                        continue
                    if set(d.get("gives") or []) & reserved:  # handed over or offered elsewhere since judge() ran
                        continue
                    sale = single_card_bid(o)
                    p = anchor(d, best_bid=best_bid(sale[0]) if sale else 0)
                    low = bool(p) and is_lowball(d, p)
                    if low and tick - last_low.get(o["maker"], -999) < LOWBALL_COOLDOWN:
                        continue
                    if not low and outstanding >= MAX_OUTSTANDING:
                        continue
                    cards = tuple(sorted(refs_of(o)))
                    if any(s["maker"] == o["maker"] and s["cards"] == cards and tick - s["tick"] < MAKER_COOLDOWN
                           for s in sent.values()):
                        continue
                    body = counter_body(o, d, p) if p else None
                    if not body:
                        continue
                    entry = {"maker": o["maker"], "cards": cards, "refs": list(refs_of(o)), "tick": tick, "price": p,
                             "low": low}
                    try:
                        res = b.list_offer(body["give"], body["want"], venue=o.get("venue"), to=o["maker"],
                                           expires_in_ticks=COUNTER_TICKS)
                    except BazaarError as e:  # asset locked by another offer, not owner any more, ...
                        log.say(f"[t{tick}] counter to {o['maker']} refused: {e}")
                        sent[o["id"]] = {**entry, "offer_id": -1, "outcome": "refused"}
                        continue
                    offer_id = (res.get("offer") or res).get("id")
                    sent[o["id"]] = {**entry, "offer_id": offer_id, "outcome": None}
                    reserved |= set(body["give"].get("assets") or [])
                    if low:
                        last_low[o["maker"]] = tick
                    else:
                        outstanding += 1
                    log.event("trader_counter", tick=tick, incoming=o["id"], counter=offer_id, maker=o["maker"], price=p,
                              their=d["cash_in"] or d["cash_out"], clearing=d["counter_cash"],
                              best_bid=best_bid(sale[0]) if sale else None, body=body)
                    log.say(f"[t{tick}] COUNTER to {o['maker']}: {p} P (they offered {d['cash_in'] or d['cash_out']}, "
                            f"our clearing price {d['counter_cash']}) · offer {offer_id}")
            if args.once:
                log.say(f"{len(decisions)} offers judged")
                return
            b.wait_tick()
        except BazaarError as e:
            log.say(f"trader: {e}")
            time.sleep(3)
        except Exception as e:  # never die on one odd offer
            log.say(f"trader: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
