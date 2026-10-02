"""One haggle with a dealer, buying or selling. The code sets every price; the words only ask nicely.

Concessions shrink as we near our limit (a share of the room left, at least 1 P, never past her price),
every message carries a new price, and we take the dealer's offer when it is within our limit and
either one step away, at or better than our own last price, or its final word.
"""
import time

from bazaar_sdk import BazaarError

from . import log
from .texts import Writer

RETRYABLE = ("network", "bad_response", "rate_limited")
FATAL = ("persona_quota", "cooloff", "locked", "insufficient_cash", "sold_out", "not_owner", "asset_locked")


def _wait(b) -> None:
    try:
        b.wait_tick()
    except BazaarError:
        time.sleep(5)


def _dealer_offer(t: dict, dealer: str):
    hers = [o for o in t.get("standing_offers") or [] if o.get("maker") == dealer and o.get("status") == "open"]
    return hers[-1] if hers else None


def _price(o: dict, side: str):
    leg = (o.get("want") if side == "buy" else o.get("give")) or {}
    return leg.get("cash")


def close_open_threads(b, dealer: str) -> None:
    """One open conversation per dealer: close a stale one left by an earlier run."""
    try:
        res = b.my_threads(status="open")
    except BazaarError:
        return
    threads = res.get("threads", res) if isinstance(res, dict) else res
    for th in threads if isinstance(threads, list) else []:
        if dealer in (th.get("with"), th.get("counterparty"), th.get("dealer"), th.get("persona")):
            try:
                b.close_thread(th["id"])
                log.say(f"closed a stale thread {th['id']} with {dealer}")
            except BazaarError as e:
                log.say(f"could not close thread {th['id']}: {e}")


def haggle(b, dealer: str, topic: dict, side: str, opening: int, limit: int, *,
           step_frac: float = 0.15, accept_gap: int = 1, max_msgs: int = 40, label: str = "",
           target: int = None, accept_at: int = None, patience: int = None) -> dict:
    """Run one conversation to its end. side "buy": limit is the most we pay; "sell": the least we take.

    Learned from earlier conversations (bz/learn.py), all optional:
      target     where her best usually lands: we pace towards one step short of it, then move 1 P at a time
      accept_at  her best price ever: take it once she stops moving at it
      patience   our messages before she usually names her final offer: the pacing horizon
    """
    buy = side == "buy"
    opening = min(opening, limit) if buy else max(opening, limit)

    def within(p):
        return p <= limit if buy else p >= limit

    def at_least_ours(p):  # the dealer meets or beats our own last price
        return bool(ours) and (p <= ours[-1] if buy else p >= ours[-1])

    def next_price(p):
        if not ours:
            return opening
        last = ours[-1]
        bound, step = limit, None
        if target is not None:
            short = target - 1 if buy else target + 1  # one step short of her usual best
            if (last < short <= limit) if buy else (limit <= short < last):
                bound = short
            elif (last >= short) if buy else (last <= short):
                step = 1  # past her usual best: only small steps from here
        if step is None and patience:
            step = max(1, round(abs(bound - last) / max(1, patience - len(ours) + 1)))
        if step is None:
            step = max(1, round(abs(bound - last) * step_frac))  # a share of the room we have left: steps shrink
        if buy:
            nxt = min(bound if step > 1 else limit, last + step, (p - 1) if p is not None else limit)
            return nxt if nxt > last else None
        nxt = max(bound if step > 1 else limit, last - step, (p + 1) if p is not None else limit)
        return nxt if nxt < last else None

    close_open_threads(b, dealer)
    th = b.open_thread(dealer, topic=topic)
    tid = th["id"]
    log.say(f"[{dealer}] thread {tid} open: {side} {label or topic} (opening {opening}, limit {limit}"
            + (f", target {target}, take at {accept_at}, patience {patience})" if target is not None else ")"))
    writer, ours, theirs = Writer(side), [], []
    accepted, waits, stalled, status, reason, saw_final, p_at_last_msg = None, 0, 0, "open", None, False, None

    while True:
        try:
            t = b.thread(tid)
            status = t.get("status", "open")
            if status != "open":
                reason = t.get("closed_reason")
                break
            o = _dealer_offer(t, dealer)
            p = _price(o, side) if o else None
            if p is not None and (not theirs or theirs[-1] != p or (o.get("final") and not saw_final)):
                theirs.append(p)
                saw_final = saw_final or bool(o.get("final"))
                log.say(f"[{dealer}] her price {p}{' (FINAL)' if o.get('final') else ''}")

            if accepted:  # settles on the next tick
                waits += 1
                if waits > 4:
                    reason = "accept_not_settled"
                    break
                _wait(b)
                continue

            if o and p is not None:
                final = bool(o.get("final"))
                close = bool(ours) and abs(p - ours[-1]) <= accept_gap
                # her best price ever, and she did not move after our last concession: take it now
                stalled_here = p_at_last_msg is not None and p == p_at_last_msg
                learned = accept_at is not None and stalled_here and (p <= accept_at if buy else p >= accept_at)
                if within(p) and (close or final or at_least_ours(p) or learned):
                    b.accept(o["id"])
                    accepted = p
                    log.say(f"[{dealer}] accepted {p}")
                    _wait(b)
                    continue
                if final:  # her last word is outside our limit
                    b.close_thread(tid)
                    status, reason = "walked_by_us", f"final {p} outside limit {limit}"
                    break

            nxt = next_price(p)
            if nxt is None:  # we are at our limit; she only moves when we do
                stalled += 1
                if stalled >= 2:
                    b.close_thread(tid)
                    status, reason = "walked_by_us", f"stuck at our limit {limit}, her price {p}"
                    break
                _wait(b)
                continue
            if len(ours) >= max_msgs:
                b.close_thread(tid)
                status, reason = "walked_by_us", "max_msgs"
                break
            b.say(tid, writer.line(nxt), price=nxt)
            ours.append(nxt)
            p_at_last_msg = p
            log.say(f"[{dealer}] we offer {nxt}")
            _wait(b)
        except BazaarError as e:
            if e.code in RETRYABLE or e.status >= 500:
                log.say(f"[{dealer}] {e}, retrying")
                time.sleep(2)
                continue
            log.say(f"[{dealer}] refused: {e}")
            status, reason = "error", e.code
            if e.code not in FATAL:
                try:
                    b.close_thread(tid)
                except BazaarError:
                    pass
            break

    if status == "deal" and accepted is None and ours:  # she accepted our standing offer
        accepted = ours[-1]
    result = {"dealer": dealer, "thread": tid, "side": side, "topic": topic, "label": label, "status": status,
              "reason": reason, "price": accepted if status == "deal" else None, "opening": opening, "limit": limit,
              "ours": ours, "theirs": theirs, "first_ask": theirs[0] if theirs else None}
    log.event("haggles", **result)
    try:  # keep the transcript: the next conversation learns from it
        from .learn import save_thread
        save_thread(b, tid)
    except (BazaarError, OSError) as e:
        log.say(f"[{dealer}] transcript not saved: {e}")
    log.say(f"[{dealer}] thread {tid} ended: {status}" + (f" at {accepted}" if status == "deal" else f" ({reason})"))
    return result
