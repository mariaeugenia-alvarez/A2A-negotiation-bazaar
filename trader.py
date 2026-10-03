"""Offers made to us, judged every tick by bz/trade.py. Only structure is read: what the offer gives and wants.

    python3 trader.py                 # SHADOW: prints and logs what it would do, sends nothing
    python3 trader.py --live          # LIVE on offers addressed to us: accepts clear wins, answers the rest with a counter
    python3 trader.py --live --live-boards   # ALSO accepts clear wins from the public boards (off by default)
    python3 trader.py --once          # one pass, then stop
    touch logs/trader.pause           # LIVE stops acting at once (it keeps logging); delete the file to resume

Safety: one accept per tick and a 2-tick pause after it (an accept settles on the next tick, so our holdings lag),
ownership and cash are rechecked every tick, one counter per incoming offer, at most 3 counters outstanding, at most
one counter per maker and card per 10 ticks. Public boards are scanned and logged in shadow.
Every counter and every outcome (accepted, or expired) goes to logs/trader.jsonl, so the next rules come from data.
"""
import argparse
import fcntl
import json
import os
import sys
import time

from agent import connect
from bazaar_sdk import BazaarError
from bz import log, price
from bz.state import State
from bz.trade import anchor, cost, counter_body, is_lowball, judge

PAUSE = os.path.join(log.LOG_DIR, "trader.pause")
ACCEPTS = os.path.join(log.LOG_DIR, "trader_accept.jsonl")
COUNTER_TICKS = 20      # how long our counter stays open
MAX_OUTSTANDING = 3     # real counters; lowball probes do not use these slots
MAKER_COOLDOWN = 10     # ticks before we counter the same maker about the same cards again
LOWBALL_COOLDOWN = 30   # a bid under half their ask is a probe: at most one per maker this often
BOARD_BUDGET = 40       # primas we may spend accepting public-board offers (cash + fee), counted from the log


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


def check_outcomes(b, me_id: str, tick: int, sent: dict, open_ids: set) -> None:
    """A counter that is no longer open either settled or expired: the feed's settlements say which."""
    pending = [k for k, s in sent.items() if s["outcome"] is None and s["offer_id"] not in open_ids and tick > s["tick"]]
    if not pending:
        return
    settled = [e["payload"] for e in b.feed(limit=200).get("events", []) if e["type"] == "settlement"]
    for k in pending:
        s = sent[k]
        hit = next((p for p in settled if me_id in p.get("parties", []) and s["maker"] in p.get("parties", [])
                    and p.get("tick", 0) >= s["tick"]), None)
        s["outcome"] = "accepted" if hit else "expired"
        log.event("trader_outcome", incoming=k, counter=s["offer_id"], maker=s["maker"], price=s["price"],
                  outcome=s["outcome"], settled_price=hit.get("price") if hit else None, tick=tick, opened=s["tick"])
        log.say(f"[t{tick}] counter {s['offer_id']} to {s['maker']} at {s['price']}: {s['outcome'].upper()}"
                + (f" (settled at {hit.get('price')})" if hit else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="act on offers addressed to us: accept clear wins, send counters")
    ap.add_argument("--live-boards", action="store_true", help="with --live: also accept clear wins from the public boards")
    ap.add_argument("--budget", type=int, default=BOARD_BUDGET, help="most we spend on public-board accepts (cash + fee)")
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
    sent = {}  # incoming offer id -> our counter
    last_low = {}  # maker -> tick of our last lowball probe
    check = None   # (offer, cash before, tick) of the last accept: its cash change shows who paid the venue fee
    log.say(f"trader: {'LIVE' if args.live else 'shadow'}"
            + (f" + boards (budget {args.budget} P, {spent_on_boards()} P already spent)" if args.live and args.live_boards else ""))
    while True:
        try:
            tick = b.clock()["tick"]
            st.refresh()
            me_id = st.me["id"]
            if tick - fees_at >= 20:
                fees, fees_at = venue_fees(b), tick
            valuer, by_ref, missing = price.from_state(st), st.by_ref(), st.missing()
            mine = b.my_offers().get("offers") or []
            todo = [(o, "to_us") for o in mine if o.get("to") == me_id]
            if args.boards:
                if tick - boards_at >= 10:  # which boards hold offers: look at all of them now and then
                    active = [v for v in fees if b.board(v).get("offers")]
                    boards_at = tick
                for v in active:
                    todo += [(o, "board") for o in b.board(v).get("offers") or [] if not o.get("to")]
            decisions = []
            for o, source in todo:
                if o.get("status") != "open":
                    continue
                d = judge(o, valuer, by_ref, st.cash, fees, missing, me_id)
                decisions.append((o, source, d))
                key = (d["offer"], d["action"], d.get("surplus"))
                if key not in seen and (source == "to_us" or d["action"] in ("accept", "counter", "human")):
                    seen.add(key)
                    log.event("trader", tick=tick, expires=o.get("expires_tick"), live=args.live, source=source, **d)
                    if source == "to_us" or d["action"] in ("accept", "human"):
                        log.say(f"[t{tick}] {source} offer {d['offer']} on {d['venue']} from {d['maker']}: "
                                f"{d['action'].upper()} · {d['why']}")

            check_outcomes(b, me_id, tick, sent, {o["id"] for o in mine if o.get("maker") == me_id})
            acting = args.live and not os.path.exists(PAUSE)
            if args.live and not acting and tick % 10 == 0:
                log.say("trader: paused (logs/trader.pause)")
            if acting:
                if check and tick >= check[2] + 2:  # the accept has settled: what did it really cost us?
                    log.event("trader_cash_check", offer=check[0]["offer"], expected_cash=check[0]["cash_out"],
                              expected_fee=check[0]["fee"], cash_before=check[1], cash_after=st.cash,
                              spent=check[1] - st.cash, tick=tick)
                    log.say(f"[t{tick}] cash check: offer {check[0]['offer']} cost {check[1] - st.cash} P "
                            f"(price {check[0]['cash_out']}, fee we expected {check[0]['fee']})")
                    check = None
                if tick >= cool_until:
                    left = args.budget - spent_on_boards()
                    pool = [x for x in decisions if x[2]["action"] == "accept"
                            and (x[1] == "to_us" or (args.live_boards and cost(x[2]) <= left))]
                    if pool:
                        o, source, w = max(pool, key=lambda x: x[2]["surplus"])
                        b.accept(w["offer"], assets=w["assets"] or None)
                        cool_until, check = tick + 2, (w, st.cash, tick)
                        log.event("trader_accept", tick=tick, source=source, cash_before=st.cash, **w)
                        log.say(f"[t{tick}] ACCEPTED offer {w['offer']} from {w['maker']} (+{w['surplus']} P, "
                                f"spends up to {cost(w)} P)")
                outstanding = sum(1 for s in sent.values() if s["outcome"] is None and not s.get("low"))
                for o, source, d in decisions:
                    if source != "to_us" or d["action"] != "counter" or o["id"] in sent:
                        continue
                    p0 = anchor(d)
                    low = bool(p0) and is_lowball(d, p0)
                    if low and tick - last_low.get(o["maker"], -999) < LOWBALL_COOLDOWN:
                        continue
                    if not low and outstanding >= MAX_OUTSTANDING:
                        continue
                    cards = tuple(sorted(a.get("ref", "") for a in (o["give"].get("assets") or [])) +
                                  sorted(t for t in (o["want"].get("types") or [])))
                    if any(s["maker"] == o["maker"] and s["cards"] == cards and tick - s["tick"] < MAKER_COOLDOWN
                           for s in sent.values()):
                        continue
                    p = anchor(d)
                    body = counter_body(o, d, p) if p else None
                    if not body:
                        continue
                    try:
                        res = b.list_offer(body["give"], body["want"], venue=o.get("venue"), to=o["maker"],
                                           expires_in_ticks=COUNTER_TICKS)
                    except BazaarError as e:  # asset locked by another offer, not owner any more, ...
                        log.say(f"[t{tick}] counter to {o['maker']} refused: {e}")
                        sent[o["id"]] = {"offer_id": -1, "maker": o["maker"], "cards": cards, "tick": tick, "price": p,
                                         "outcome": "refused", "low": low}
                        continue
                    offer_id = (res.get("offer") or res).get("id")
                    sent[o["id"]] = {"offer_id": offer_id, "maker": o["maker"], "cards": cards, "tick": tick, "price": p,
                                     "outcome": None, "low": low}
                    if low:
                        last_low[o["maker"]] = tick
                    else:
                        outstanding += 1
                    log.event("trader_counter", tick=tick, incoming=o["id"], counter=offer_id, maker=o["maker"], price=p,
                              their=d["cash_in"] or d["cash_out"], clearing=d["counter_cash"], body=body)
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
