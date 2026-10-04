"""Offers from OTHER TEAMS, judged every tick by bz/trade.py. Only structure is read: what the offer gives and wants.

    python3 trader.py                 # SHADOW: prints and logs what it would do, sends nothing
    python3 trader.py --live          # LIVE on team offers addressed to us: accepts clear wins, answers the rest with a counter
    python3 trader.py --live --live-boards   # ALSO accepts clear wins from the public boards (40 P per hour, read from the log)
    python3 trader.py --once          # one pass, then stop
    touch logs/trader.pause           # LIVE stops acting at once (it keeps logging); delete the file to resume

Scope: teams only. Dealer offers (Abuela, El Chato, Pilar) belong to the dealer scripts and are ignored (bz/trade.py).
Values come from the game (page bonus included), never from our formula.
Cash: accepts are judged against our real cash. Standing bids and buying counters only promise cash, so they stop
CASH_FLOOR (15 P) short of it: that reserve is for accepts. Safety: one accept per tick and a 2-tick pause after it; a card in one of our open offers is never offered or handed over
again; we never sell below the best bid seen for that card in the last 60 ticks; at most 3 counters outstanding. Counters
that bid under half the other side's ask ("probes") are not sent: 0 of 6 worked on Saturday. Board accepts are capped at
--budget primas per hour of wall time. --earmark REF:AMOUNT (OFF by default) keeps that cash for buying a card by hand,
for example --earmark RET-09:60, until we hold the card; accepts costing 5 P or less and money coming in are never blocked.
Every timer below is in ticks at 30 s; it scales by 30 / tick seconds (Sunday ticks last 15 s).
Every counter, accept and settlement goes to logs/trader*.jsonl. The guard (bz/guard.py) sees our quotes AND our accepts.
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
from bz.boards import BoardScanner
from bz.guard import CASH_FLOOR, earmark_total, spend_allowed, tick_scale
from bz.state import State
from bz.quoter import Quoter
from bz.quotes import market_cap
from bz.trade import DEFAULT_GUARD, DEFAULT_PROTECT, GameValues, anchor, cost, counter_body, is_lowball, judge, wanted_refs

PAUSE = os.path.join(log.LOG_DIR, "trader.pause")
ACCEPTS = os.path.join(log.LOG_DIR, "trader_accept.jsonl")
COUNTER_TICKS = 20      # how long our counter stays open
MAX_OUTSTANDING = 3     # counters open at once
MAKER_COOLDOWN = 10     # ticks before we counter the same maker about the same cards again
BOARD_BUDGET = 40       # primas we may spend accepting public-board offers (cash + fee) per BUDGET_SECONDS
BUDGET_SECONDS = 3600
MAX_COUNTER_RATIO = 1.25  # a sell counter above this x their price: 0 of 22 accepted, 3 of 5 at or below (tick 1445)
BID_MEMORY = 60         # ticks a bid for a card is remembered: we never sell that card below it
HEARTBEAT = os.path.join(log.LOG_DIR, "trader.heartbeat")
GAME_PAUSED_SLEEP = 20  # seconds between clock reads while the game is paused (doors closed at night)
DEFAULT_HANDS_OFF = "none"  # cards a person buys by hand (no quote, accept or counter). RET-09 left this list on 2026-10-04
DEFAULT_TARGETS = "RET-09"  # cards the trader buys even though they complete a page: never over value - margin, never over
# the market cap. Thameur and Maru, 2026-10-04: the last card of El Retiro (worth 177 to us, market about 72)
DEFAULT_EARMARK = "none"  # off by default: nothing proves a completed page scores; switch on with --earmark RET-09:60


def parse_earmark(text: str) -> dict:
    """"RET-09:60,SAL-09:70" -> {"RET-09": 60, "SAL-09": 70}. Empty or "none" -> {}."""
    out = {}
    for part in (text or "").split(","):
        ref, _, amount = part.strip().partition(":")
        if ref and ref.lower() != "none" and amount.strip().isdigit():
            out[ref.strip()] = int(amount)
    return out


def spent_recent(tick: int, window: int, path: str = None) -> int:
    """What our accepts from the public boards cost in the last `window` ticks, read from the log so a restart cannot
    reset the cap."""
    path = path or ACCEPTS
    total = 0
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("source") == "board" and 0 <= tick - int(e.get("tick", -10**9)) <= window:
                total += cost(e)
    return total


def realized_gain(w: dict, p: dict):
    """(gain, spent) once the game's settlement `p` is known: the planned surplus corrected by what it really charged us.
    Net cash flow = (+price if we sell, -price if we buy, 0 for a swap) - the fee we paid as the accepter."""
    price = int((p or {}).get("price") or 0)
    fee = int((p or {}).get("fee") or 0)
    actual = (price if w["cash_in"] else -price if w["cash_out"] else 0) - fee
    expected = w["cash_in"] - w["cash_out"] - w["fee"]
    return w["surplus"] + (actual - expected), max(0, -actual)


def venue_fees(b) -> dict:
    return {v["venue"]: (v.get("fee_bps", 0), v.get("fee_per_card", 0)) for v in b.venues().get("venues", [])}


def single_card_bid(o: dict):
    """(card, cash) when an offer pays cash for exactly one card, else None: what someone is willing to pay for it."""
    give, want = o.get("give") or {}, o.get("want") or {}
    refs = wanted_refs(o)
    if give.get("cash") and len(refs) == 1 and not give.get("assets") and not want.get("cash"):
        return refs[0], int(give["cash"])
    return None


def parse_guard(text: str) -> dict:
    """'SAL:0.5,MAL:0.5' -> {"SAL": 0.5, "MAL": 0.5}; 'none' -> {}."""
    out = {}
    for part in (text or "").split(","):
        k, _, v = part.strip().partition(":")
        if k and k.lower() != "none" and v:
            out[k.strip()] = float(v)
    return out


def wanted_in(o: dict) -> list:
    """Cards an offer gives (what we would receive)."""
    return [a.get("ref") for a in (o.get("give") or {}).get("assets") or []]


def game_paused(clk: dict) -> bool:
    """The game clock does not move: paused, or the doors are closed (night)."""
    return bool(clk.get("paused")) or clk.get("doors") == "closed"


def complete_pages(missing: dict) -> set:
    """Sets whose page is complete in the live album."""
    return {s for s, refs in missing.items() if not refs}


def record_bids(bids: dict, offers: list, own_ids: set, me_id: str, tick: int) -> None:
    """Remember what OTHER teams pay for each card. The public board shows our own offers under a pseudonym, not under
    our team id: without own_ids our standing bid counts as another team's, and the quoter outbids itself by 1 P
    (SAL-06 went 20 -> 24, tick 1201-1281)."""
    for o in offers:
        bid = single_card_bid(o)
        if bid and o.get("maker") != me_id and o.get("id") not in own_ids:
            bids.setdefault(bid[0], []).append((tick, bid[1]))


def counter_too_far(d: dict, price) -> bool:
    """A sell counter far above their bid never closes (0 of 22 above 1.25 x their price): do not send it."""
    their = d.get("cash_in") or 0
    return bool(price and their and not d.get("cash_out") and price > MAX_COUNTER_RATIO * their)


def refs_of(o: dict) -> set:
    g = o.get("give") or {}
    return {a.get("ref") for a in g.get("assets") or []} | set(wanted_refs(o))


def settlement_for(b, me_id: str, refs: set, since: int, party: str = None):
    """The feed's settlement of our deal with these cards, or None. Our cash alone cannot tell: another session spends it.
    party: the other team must be this one (a counter to Team 13 is not settled by a sale to Team 7, tick 1057)."""
    for e in b.feed(limit=300).get("events", []):
        p = e.get("payload") or {}
        if e.get("type") == "settlement" and me_id in p.get("parties", []) and p.get("tick", 0) >= since \
                and refs & {i.get("ref") for i in p.get("items", [])} and (party is None or party in p.get("parties", [])):
            return p
    return None


def check_outcomes(b, me_id: str, tick: int, sent: dict, open_ids: set) -> None:
    """A counter that is no longer open either settled or expired: the feed's settlements say which."""
    pending = [k for k, s in sent.items() if s["outcome"] is None and s["offer_id"] not in open_ids and tick > s["tick"]]
    for k in pending:
        s = sent[k]
        hit = settlement_for(b, me_id, set(s["refs"]), s["tick"], party=s["maker"])
        s["outcome"] = "accepted" if hit else "expired"
        log.event("trader_outcome", incoming=k, counter=s["offer_id"], maker=s["maker"], price=s["price"],
                  outcome=s["outcome"], settled_price=hit.get("price") if hit else None, tick=tick, opened=s["tick"])
        log.say(f"[t{tick}] counter {s['offer_id']} to {s['maker']} at {s['price']}: {s['outcome'].upper()}"
                + (f" (settled at {hit.get('price')})" if hit else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="act on team offers addressed to us: accept clear wins, send counters")
    ap.add_argument("--live-boards", action="store_true", help="with --live: also accept clear wins from the public boards")
    ap.add_argument("--budget", type=int, default=BOARD_BUDGET, help="most we spend on public-board accepts (cash + fee) per hour")
    ap.add_argument("--hands-off", default=DEFAULT_HANDS_OFF,
                    help='cards a person buys by hand: the trader never quotes, accepts or counters them ("none" to clear)')
    ap.add_argument("--buy-targets", default=DEFAULT_TARGETS,
                    help='cards to buy even when they complete a page, at most the market cap ("none" to clear)')
    ap.add_argument("--protect-pages", default=",".join(sorted(DEFAULT_PROTECT)),
                    help='sets whose page we are completing: their cards never go, like a complete page ("none" to clear)')
    ap.add_argument("--guard-pages", default=",".join(f"{k}:{v}" for k, v in sorted(DEFAULT_GUARD.items())),
                    help='SET:SHARE,...: selling the only copy of a card of that page needs a gain of SHARE x its value ("none" to clear)')
    ap.add_argument("--earmark", default=DEFAULT_EARMARK,
                    help='cash kept for buying cards by hand, "REF:AMOUNT,..." or "none". It releases when we hold the card')
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
    book = {r: v["book"] for r, v in st.catalog["rarities"].items()}  # for the market cap of every buy
    rarity_of = {c["id"]: c["rarity"] for s_ in st.catalog["sets"] for c in s_["cards"]}

    def cap_of(asset: dict) -> int:
        """Market cap of one card; a card whose rarity we cannot find gets no cap (its value still limits the price)."""
        r = asset.get("rarity") or rarity_of.get(asset.get("ref"))
        return market_cap(r, book[r]) if r in book else 10 ** 6
    cool_until = 0
    sent = {}       # incoming offer id -> our counter
    earmark = parse_earmark(args.earmark)
    hands_off = {r.strip() for r in args.hands_off.split(",") if r.strip() and r.strip().lower() != "none"}
    protect = {r.strip() for r in args.protect_pages.split(",") if r.strip() and r.strip().lower() != "none"}
    guard = parse_guard(args.guard_pages)
    targets = {r.strip() for r in args.buy_targets.split(",") if r.strip() and r.strip().lower() != "none"} - hands_off
    complete_seen = None
    idle_told = False  # sets whose page is complete: a new one is announced once, and protected from then on
    scanner, blocked_seen = BoardScanner(), set()
    bids = {}       # card -> [(tick, cash)] bids seen from anyone
    check = None    # (decision, offer, tick) of the last accept, to read its settlement
    value_cache, holdings = {}, None
    quoter = Quoter(b, args.quote_budget, notify=args.notify, earmark=earmark, hands_off=hands_off) if args.quotes else None
    log.say(f"trader: {'LIVE' if args.live else 'shadow'}" + (f" + quotes (budget {args.quote_budget} P)" if quoter else "")
            + (f" + boards ({args.budget} P per hour)" if args.live and args.live_boards else "")
            + (f" · buy targets {sorted(targets)} (market cap)" if targets else "")
            + (f" · earmark {earmark}" if earmark else "") + (f" · hands-off {sorted(hands_off)}" if hands_off else ""))
    while True:
        try:
            clk = b.clock()
            tick = clk["tick"]
            if game_paused(clk):  # doors closed: wait_tick() returns at once, and a loop with no wait hits the rate limit
                if not idle_told:  # (5 refused calls in the same tick stop the guard, and it stays stopped at 09:00)
                    log.say(f"[t{tick}] trader: the game is paused (doors {clk.get('doors')}); idle until it resumes")
                    idle_told = True
                try:
                    with open(HEARTBEAT, "w", encoding="utf-8") as f:
                        json.dump({"tick": tick, "ts": time.time(), "live": args.live, "acting": False, "game_paused": True,
                                   "cash": st.cash, "stopped": bool(quoter and quoter.guard.stopped),
                                   "tick_seconds": clk.get("tick_seconds"), "budget": args.budget, "floor": CASH_FLOOR}, f)
                except OSError:
                    pass
                if args.once:
                    return
                time.sleep(GAME_PAUSED_SLEEP)
                continue
            if idle_told:
                log.say(f"[t{tick}] trader: the game resumed")
                idle_told = False
            scale = tick_scale(clk.get("tick_seconds"))
            window = round(BUDGET_SECONDS / float(clk.get("tick_seconds") or 30))
            if quoter:
                quoter.set_scale(scale)
            st.refresh()
            me_id = st.me["id"]
            if tick - fees_at >= 20:
                fees, fees_at = venue_fees(b), tick
            now_holdings = tuple(sorted(a["id"] for a in st.me["assets"]))
            if now_holdings != holdings:  # what one more copy is worth changes with what we hold
                value_cache, holdings = {}, now_holdings
            values, by_ref, missing = GameValues(b, st.me["assets"], value_cache), st.by_ref(), st.missing()
            done = complete_pages(missing)
            for s_ in sorted(done - (complete_seen or done)):  # a page completed while we run: tell, and it is untouchable now
                text = f"{s_} page COMPLETE: its cards are protected, the trader will never sell one (hard rule 2)"
                log.event("alerts", level="PAGE-DONE", text=text, tick=tick)
                log.say(f"[t{tick}] ALERT PAGE-DONE: {text}")
                if quoter:
                    quoter.alert("PAGE-DONE", text)
            if done != complete_seen:
                complete_seen = done
                try:
                    with open(os.path.join(log.LOG_DIR, "protected_pages.json"), "w", encoding="utf-8") as f:
                        json.dump({"tick": tick, "complete": sorted(done), "protected": sorted(done | protect),
                                   "guard": guard}, f)
                except OSError:
                    pass
            mine = b.my_offers().get("offers") or []
            ours_open = [o for o in mine if o.get("maker") == me_id and o.get("status") == "open"]
            reserved = {a["id"] for o in ours_open for a in (o.get("give") or {}).get("assets") or []}
            # our open bids (whoever posted them: a script or a person on our key) promise cash and ask for cards
            bids_open = [o for o in ours_open if (o.get("give") or {}).get("cash") and wanted_refs(o)]
            committed = sum(int(o["give"]["cash"]) for o in bids_open)  # every bid promises cash, counters included
            # only PUBLIC bids (no "to") are standing bids for missing cards. A counter to one team may be a
            # deliberate bid for a second copy below its value: it is neither pending nor stale.
            public_bids = [o for o in bids_open if not o.get("to")]
            # our OWN quotes never block an accept for the same card: the quoter cancels its bid when the card arrives
            # (and we cancel it right after an accept). Bids from anyone else on our key do block: they could fill too.
            own_ids = set(quoter.own) if quoter else set()
            foreign_bids = [o for o in public_bids if o["id"] not in own_ids]
            pending = {r for o in foreign_bids for r in wanted_refs(o)}
            free_cash = max(0, st.cash - committed)
            reserve = earmark_total(earmark, set(by_ref))  # cash kept for hand purchases; 0 once we hold the card
            stale = [o for o in foreign_bids if any(r in by_ref for r in wanted_refs(o))]
            for o in stale:  # we got the card another way: if this bid fills, we pay for a duplicate worth ~25 %
                key = ("stale", o["id"])
                if key not in seen:
                    seen.add(key)
                    log.event("trader_stale_bid", tick=tick, offer=o["id"], cards=wanted_refs(o), cash=o["give"]["cash"])
                    log.say(f"[t{tick}] STALE BID {o['id']}: {o['give']['cash']} P for {wanted_refs(o)}, which we already hold"
                            + ("" if args.cancel_stale_bids else " (cancel it by hand, or run with --cancel-stale-bids)"))
            todo = [(o, "to_us") for o in mine if o.get("to") == me_id]
            if args.boards:  # active boards every tick, the quiet ones a few per tick: no burst of 21 calls
                for v, offers in scanner.scan(lambda v: b.board(v).get("offers") or [], list(fees)).items():
                    todo += [(o, "board") for o in offers if not o.get("to")]
            our_ids = {o["id"] for o in ours_open}
            todo = [(o, s_) for o, s_ in todo if o["id"] not in our_ids]  # our own offers, seen on a board: never judge them
            record_bids(bids, [o for o, _ in todo], our_ids, me_id, tick)  # remember what other teams pay for each card

            def best_bid(ref):
                return max((p for t, p in bids.get(ref, []) if tick - t <= BID_MEMORY * scale), default=0)

            decisions, accepted_now = [], set()
            for o, source in todo:
                if o.get("status") != "open":
                    continue
                # accepts are certain gains: judge them against our real cash. Open bids and counters only PROMISE cash (they
                # fill 2-5 % of the time, and an unfunded fill just fails), so they must not block a sure accept.
                d = judge(o, values, by_ref, st.cash, fees, missing, me_id, reserved, pending, hands_off, protect, guard,
                          targets, cap_of)
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
                gain, spent = realized_gain(w, p) if p else (None, 0)
                log.event("trader_settlement", offer=w["offer"], expected_cash=w["cash_out"] or w["cash_in"],
                          expected_fee=w["fee"], found=bool(p), price=(p or {}).get("price"), fee=(p or {}).get("fee"), tick=tick,
                          planned_gain=w["surplus"], realized_gain=gain)
                if p and quoter:  # the guard checks our accepts too, not only the quoter's fills
                    quoter.guard.accept_result(tick, f"accept of offer {w['offer']}", gain, spent)
                log.say(f"[t{tick}] settlement of offer {w['offer']}: "
                        + (f"price {p.get('price')}, fee {p.get('fee')}" if p else "NOT FOUND (refused or taken by someone else?)"))
                check = None
            acting = args.live and not os.path.exists(PAUSE)
            if args.live and not acting and tick % 10 == 0:
                log.say("trader: paused (logs/trader.pause)")
            left = args.budget - spent_recent(tick, window)

            def block_reason(x):
                """Why an ACCEPT decision cannot be taken right now, or None. Logged, so the review can price what we missed."""
                o_, source_, d_ = x
                if not args.live:
                    return "shadow"
                if not acting:
                    return "paused"
                if tick < cool_until:
                    return "cooldown"
                if source_ == "board" and not args.live_boards:
                    return "boards_off"
                if source_ == "board" and cost(d_) > left and not (set(wanted_in(o_)) & targets):
                    return "budget"
                if not spend_allowed(d_["cash_out"] + d_["fee"] - d_["cash_in"], st.cash, reserve):
                    return "earmark"
                return None
            if quoter:
                try:
                    quoter.step(tick, st, mine, values, best_bid, settlement_for, PAUSE, acting)
                except BazaarError as e:
                    quoter.guard.error(tick, e.code)
                    log.event("trader_error", tick=tick, op="quoter step", error=str(e))
                    log.say(f"quoter: {e}")
                acting = args.live and not os.path.exists(PAUSE)  # a guard stop pauses everything at once
                free_cash = max(0, free_cash - quoter.last_posted_cash)  # bids posted this tick are promises too
            if acting:
                if args.cancel_stale_bids:
                    for o in stale:
                        try:
                            b.cancel(o["id"])
                            log.event("trader_cancel", tick=tick, offer=o["id"], cards=wanted_refs(o), why="stale bid")
                            log.say(f"[t{tick}] CANCELLED stale bid {o['id']} for {wanted_refs(o)}")
                        except BazaarError as e:
                            log.event("trader_error", tick=tick, op=f"cancel stale bid {o['id']}", error=str(e))
                            log.say(f"[t{tick}] cancel {o['id']} refused: {e}")
                if tick >= cool_until:
                    pool = [x for x in decisions if x[2]["action"] == "accept" and block_reason(x) is None]
                    if pool:
                        o, source, w = max(pool, key=lambda x: x[2]["surplus"])
                        b.accept(w["offer"], assets=w["assets"] or None)
                        cool_until, check = tick + 2, (w, o, tick)
                        accepted_now.add(w["offer"])
                        if quoter:
                            quoter.guard.own_trade(tick)
                            quoter.cancel_for(refs_of(o), tick, "card acquired by an accept")
                        reserved |= set(w["gives"])
                        log.event("trader_accept", tick=tick, source=source, **w)
                        log.say(f"[t{tick}] ACCEPTED offer {w['offer']} from {w['maker']} (+{w['surplus']} P, "
                                f"spends up to {cost(w)} P)")
                outstanding = sum(1 for s in sent.values() if s["outcome"] is None)
                for o, source, d in decisions:
                    if source != "to_us" or d["action"] != "counter" or o["id"] in sent:
                        continue
                    if set(d.get("gives") or []) & reserved:  # handed over or offered elsewhere since judge() ran
                        continue
                    sale = single_card_bid(o)
                    p = anchor(d, best_bid=best_bid(sale[0]) if sale else 0)
                    if counter_too_far(d, p):
                        continue
                    if p and is_lowball(d, p):  # a bid under half their ask: 0 of 6 worked on Saturday, so we skip it
                        continue
                    if outstanding >= MAX_OUTSTANDING:
                        continue
                    if p and d["cash_out"] and not d["cash_in"] and (free_cash - p < CASH_FLOOR
                                                                    or not spend_allowed(p, free_cash, reserve)):
                        continue  # a counter that buys promises cash: it never uses the floor kept for accepts, nor an earmark
                    cards = tuple(sorted(refs_of(o)))
                    if any(s["maker"] == o["maker"] and s["cards"] == cards and tick - s["tick"] < MAKER_COOLDOWN * scale
                           for s in sent.values()):
                        continue
                    body = counter_body(o, d, p) if p else None
                    if not body:
                        continue
                    entry = {"maker": o["maker"], "cards": cards, "refs": list(refs_of(o)), "tick": tick, "price": p}
                    try:
                        res = b.list_offer(body["give"], body["want"], venue=o.get("venue"), to=o["maker"],
                                           expires_in_ticks=round(COUNTER_TICKS * scale))
                    except BazaarError as e:  # asset locked by another offer, not owner any more, ...
                        log.event("trader_error", tick=tick, op=f"counter to {o['maker']} on offer {o['id']}", error=str(e))
                        log.say(f"[t{tick}] counter to {o['maker']} refused: {e}")
                        sent[o["id"]] = {**entry, "offer_id": -1, "outcome": "refused"}
                        continue
                    offer_id = (res.get("offer") or res).get("id")
                    sent[o["id"]] = {**entry, "offer_id": offer_id, "outcome": None}
                    reserved |= set(body["give"].get("assets") or [])
                    outstanding += 1
                    log.event("trader_counter", tick=tick, incoming=o["id"], counter=offer_id, maker=o["maker"], price=p,
                              their=d["cash_in"] or d["cash_out"], clearing=d["counter_cash"],
                              best_bid=best_bid(sale[0]) if sale else None, body=body)
                    log.say(f"[t{tick}] COUNTER to {o['maker']}: {p} P (they offered {d['cash_in'] or d['cash_out']}, "
                            f"our clearing price {d['counter_cash']}) · offer {offer_id}")
            for x in decisions:  # every ACCEPT we could not take, with the reason: the review loop prices what we missed
                if x[2]["action"] != "accept" or x[2]["offer"] in accepted_now:
                    continue
                why_not = block_reason(x)
                if why_not and (x[2]["offer"], why_not) not in blocked_seen:
                    blocked_seen.add((x[2]["offer"], why_not))
                    log.event("trader_blocked", tick=tick, offer=x[2]["offer"], maker=x[2]["maker"], source=x[1],
                              venue=x[2]["venue"], reason=why_not, surplus=x[2]["surplus"], cost=cost(x[2]), why=x[2]["why"])
            try:  # heartbeat: the review loop reads it, so a dead trader is noticed
                with open(HEARTBEAT, "w", encoding="utf-8") as f:
                    json.dump({"tick": tick, "ts": time.time(), "live": args.live, "acting": acting, "cash": st.cash,
                               "stopped": bool(quoter and quoter.guard.stopped), "tick_seconds": clk.get("tick_seconds"),
                               "budget": args.budget, "floor": CASH_FLOOR}, f)
            except OSError:
                pass
            if args.once:
                log.say(f"{len(decisions)} offers judged")
                return
            b.wait_tick()
        except BazaarError as e:  # an accept refused by the game ends here too
            log.event("trader_error", tick=None, op="trader loop (accept or read)", error=str(e))
            log.say(f"trader: {e}")
            time.sleep(3)
        except Exception as e:  # never die on one odd offer
            log.event("trader_error", tick=None, op="trader loop", error=f"unexpected {type(e).__name__}: {e}")
            log.say(f"trader: unexpected {type(e).__name__}: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
