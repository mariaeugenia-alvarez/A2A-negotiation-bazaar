"""One timeline of everything the trader did, from its own logs. Pure reads; the dashboard and trader_notify.py use it.

Each item: {"ts", "tick", "kind", "status", "es", "en", "key"}.
status: ok (a trade settled, a counter accepted, a bid or ask filled), fail (refused by the game, an accept that did
not settle, a guard stop, an error), blocked (an accept we could not take), expired (a counter or quote that ended
with no trade), alert (something a person must look at), info (a quote posted or cancelled, a counter sent).
"""
import json
import os
import time

from . import log

ALERT_FAIL = {"STOP", "SCORE-DROP", "ERROR"}
ALERT_SHOW = {"WIN", "UP", "PAGE", "PAGE-DONE", "RESUME", "LEAD-HANDSOFF", "TAPE-NEED", "OUTBID", "STALE"}
ALERT_QUIET = {"FOREIGN", "LEAD", "INFO", "DUEL_START", "TAPE-SPARE"}  # too many, or not the trader's: left out


def _read(name: str, log_dir: str) -> list:
    p = os.path.join(log_dir, f"{name}.jsonl")
    out = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def _item(r, kind, status, es, en, key):
    return {"ts": r.get("ts"), "tick": r.get("tick"), "kind": kind, "status": status, "es": es, "en": en, "key": key}


HANDS_OFF = ("RET-09",)  # cards a person buys by hand: an ask under our value is told at once (tick 1272-1420: RET-09
# stood at 84 P, worth 177 to us, for 150 ticks; only signals.jsonl saw it)


def timeline(log_dir: str = None, since_ts: float = 0, hands_off=HANDS_OFF) -> list:
    """Every trader operation since since_ts, oldest first."""
    d = log_dir or log.LOG_DIR
    out = []
    settled = {x["offer"]: x for x in _read("trader_settlement", d)}
    for a in _read("trader_accept", d):
        g = a.get("gives") or []
        out.append(_item(a, "accept", "info", f"Acepta la oferta {a['offer']} de {a.get('maker')} ({a.get('source')}): "
                                              f"+{a.get('surplus')} P de valor previsto, paga hasta {(a.get('cash_out') or 0) + (a.get('fee') or 0)} P",
                         f"Accepted offer {a['offer']} from {a.get('maker')} ({a.get('source')}): +{a.get('surplus')} P planned", f"acc{a['offer']}"))
        x = settled.get(a["offer"])
        if x:
            if x.get("found"):
                rg = x.get("realized_gain")
                out.append(_item(x, "settled", "ok", f"Oferta {a['offer']} cerrada a {x.get('price')} P (comisión {x.get('fee')})"
                                                     + (f", ganancia real {rg:+.1f}" if rg is not None else ""),
                                 f"Offer {a['offer']} settled at {x.get('price')} P", f"set{a['offer']}"))
            else:
                out.append(_item(x, "settled", "fail", f"La aceptación de la oferta {a['offer']} NO aparece en el juego "
                                                       "(la retiraron o la tomó otro)",
                                 f"Accept of offer {a['offer']} did NOT settle", f"set{a['offer']}"))
    outcomes = {o["incoming"]: o for o in _read("trader_outcome", d)}
    for c in _read("trader_counter", d):
        sell = bool(((c.get("body") or {}).get("give") or {}).get("assets"))
        verb_es, verb_en = ("vender por", "sell for") if sell else ("comprar por", "buy for")
        out.append(_item(c, "counter", "info", f"Contraoferta a {c.get('maker')}: {verb_es} {c.get('price')} P "
                                               f"(ellos {c.get('their')}, nuestro mínimo {c.get('clearing')})",
                         f"Counter to {c.get('maker')}: {verb_en} {c.get('price')} P (they offered {c.get('their')})",
                         f"cnt{c.get('counter')}"))
        o = outcomes.get(c["incoming"])
        if o:
            st = {"accepted": "ok", "expired": "expired", "refused": "fail"}.get(o["outcome"], "info")
            es = {"accepted": "ACEPTADA", "expired": "caducada sin respuesta", "refused": "rechazada por el juego"}.get(o["outcome"], o["outcome"])
            out.append(_item(o, "counter_result", st, f"Contraoferta {o.get('counter')} a {o.get('maker')} a {o.get('price')} P: {es}"
                                                     + (f" (cerrada a {o['settled_price']} P)" if o.get("settled_price") is not None else ""),
                             f"Counter {o.get('counter')} to {o.get('maker')} at {o.get('price')} P: {o['outcome'].upper()}", f"cres{o.get('counter')}"))
    for q in _read("quotes", d):
        ev, side, ref = q.get("event"), q.get("side"), q.get("ref")
        side_es = {"bid": "puja de compra", "ask": "oferta de venta"}.get(side, "cotización")
        if ev == "posted":
            out.append(_item(q, "quote", "info", f"Publica {side_es} {ref} a {q.get('price')} P (nos vale {q.get('value')})",
                             f"Posted {side} {ref} at {q.get('price')} P", f"qp{q.get('offer')}"))
        elif ev == "filled":
            out.append(_item(q, "quote", "ok", f"SE LLENA la {side_es} {ref} a {q.get('settled') or q.get('price')} P",
                             f"FILLED {side} {ref} at {q.get('settled') or q.get('price')} P", f"qf{q.get('offer')}"))
        elif ev == "closed":
            out.append(_item(q, "quote", "expired", f"Caduca sin trato la {side_es} {ref} a {q.get('price')} P",
                             f"Expired {side} {ref} at {q.get('price')} P", f"qc{q.get('offer')}"))
        elif ev == "cancelled":
            out.append(_item(q, "quote", "info", f"Cancela la cotización {ref} ({q.get('why')})",
                             f"Cancelled quote {ref} ({q.get('why')})", f"qx{q.get('offer')}"))
    for x in _read("trader_blocked", d):
        out.append(_item(x, "blocked", "blocked", f"No puede aceptar la oferta {x.get('offer')} de {x.get('maker')} "
                                                  f"(+{x.get('surplus')} P): {x.get('reason')}",
                         f"Could not accept offer {x.get('offer')} (+{x.get('surplus')} P): {x.get('reason')}",
                         f"blk{x.get('offer')}{x.get('reason')}"))
    for x in _read("trader_error", d):
        out.append(_item(x, "error", "fail", f"Fallo en {x.get('op')}: {x.get('error')}", f"FAILED {x.get('op')}: {x.get('error')}",
                         f"err{x.get('ts')}"))
    for x in _read("trader_stale_bid", d):
        out.append(_item(x, "stale", "alert", f"Puja {x.get('offer')} desfasada: ya tenemos {x.get('cards')}",
                         f"Stale bid {x.get('offer')}: we already hold {x.get('cards')}", f"stl{x.get('offer')}"))
    for x in _read("alerts", d):
        lv = x.get("level")
        if lv in ALERT_QUIET or lv not in ALERT_FAIL | ALERT_SHOW:
            continue
        st = "fail" if lv in ALERT_FAIL else "alert"
        text = str(x.get("text") or "")[:300]
        out.append(_item(x, "alert", st, f"{lv}: {text}", f"{lv}: {text}", f"al{x.get('ts')}"))
    told = set()
    for x in _read("signals", d):  # a hands-off card on a board at a price that clears our value: a person must act
        if x.get("ref") in hands_off and x.get("clears") and x.get("id") not in told:
            told.add(x.get("id"))
            es = (f"MANO (Maru): {x['ref']} a la venta a {x.get('price')} P en {x.get('venue')} (oferta {x.get('id')}), "
                  f"nos vale {x.get('value')}: comprar a mano")
            en = f"HANDS-OFF {x['ref']} for sale at {x.get('price')} P on {x.get('venue')} (offer {x.get('id')}), worth {x.get('value')}: buy by hand"
            out.append(_item(x, "handsoff", "alert", es, en, f"ho{x.get('id')}"))
    out = [i for i in out if (i["ts"] or 0) >= since_ts]
    return sorted(out, key=lambda i: (i["ts"] or 0, i["tick"] or 0))


def health(log_dir: str = None, now: float = None) -> dict:
    """The trader's heartbeat: alive (beat < 120 s old), live, acting, paused, stopped by its guard."""
    d = log_dir or log.LOG_DIR
    now = now or time.time()
    hb = {}
    try:
        hb = json.load(open(os.path.join(d, "trader.heartbeat"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    age = round(now - hb["ts"]) if hb.get("ts") else None
    return {"age": age, "alive": age is not None and age < 120, "live": hb.get("live"), "acting": hb.get("acting"),
            "stopped": hb.get("stopped"), "paused": os.path.exists(os.path.join(d, "trader.pause")), "cash": hb.get("cash"),
            "game_paused": bool(hb.get("game_paused")),
            "tick": hb.get("tick")}


def summary(items: list) -> dict:
    """Counts per status, and the trades that closed (ok)."""
    c = {}
    for i in items:
        c[i["status"]] = c.get(i["status"], 0) + 1
    return c


def view(log_dir: str = None, hours: float = 6, cap: int = 300) -> dict:
    """What the dashboard shows: health, counts for the last `hours`, the last `cap` items newest first, failures apart."""
    items = timeline(log_dir, since_ts=time.time() - hours * 3600)
    return {"health": health(log_dir), "hours": hours, "counts": summary(items),
            "items": list(reversed(items))[:cap], "failures": [i for i in reversed(items) if i["status"] in ("fail", "blocked")][:60]}
