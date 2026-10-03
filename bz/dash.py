"""Everything the dashboard shows, as one JSON-able dict (dashboard.py renders it into logs/dashboard.html).

Sources, all read-only:
  logs/threads/*.json          our haggles with dealers, full transcripts (bz/learn.py keeps them)
  logs/haggles.jsonl           opening and limit of each haggle (bz/haggle.py), when we have it
  logs/duels.jsonl, logs/duels/ our duel decisions and the duel transcripts (the API forgets nothing, but we keep a copy)
  logs/feed.jsonl              every public event; the dashboard appends what /api/feed shows now
  /api/dealers, /api/leaderboard, /api/feed ...   public, no key needed
  our key (optional)           our score, our duels, the values behind our limits
  bz/testbed.py                our haggle() against simulated dealers (logs/testbed.json, rerun when the code changes)

Other teams' haggles come from the public feed: it shows the dealer's words and every price, but the teams' own words
are blank. That is enough to see how each dealer moves with everybody.
"""
import json
import os
import re
import statistics
import subprocess
import time
import urllib.request
from collections import Counter, defaultdict

from . import learn, log, price, testbed
from .duel import OPEN_FRAC
from .trade import HOUSE_FEE, MIN_SHARE, MIN_SURPLUS

ROOT = os.path.dirname(log.LOG_DIR)
PUBLIC = "https://bazaar.causaprima.ai"
FEED_PATH = os.path.join(log.LOG_DIR, "feed.jsonl")
DUEL_DIR = os.path.join(log.LOG_DIR, "duels")
CACHE_PATH = os.path.join(log.LOG_DIR, "public_cache.json")


# ---------------------------------------------------------------- reading

def read_jsonl(path: str) -> list:
    out = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def fetch_public(offline: bool = False) -> dict:
    """The public endpoints the big screen uses. Falls back to the last copy when the network is down."""
    names = {"dealers": "dealers", "leaderboard": "leaderboard", "levels": "levels", "schedule": "schedule",
             "clock": "clock", "catalog": "catalog", "venues": "venues", "feed": "feed?limit=2000"}
    out, errors = {}, []
    if not offline:
        for key, route in names.items():
            try:
                with urllib.request.urlopen(f"{PUBLIC}/api/{route}", timeout=25) as r:
                    out[key] = json.loads(r.read().decode("utf-8"))
            except Exception as e:  # a missing piece must not stop the dashboard
                errors.append(f"{key}: {type(e).__name__}")
    cached = {}
    if os.path.exists(CACHE_PATH):
        cached = json.load(open(CACHE_PATH, encoding="utf-8"))
    merged = {**cached, **out}
    if out:
        os.makedirs(log.LOG_DIR, exist_ok=True)
        slim = {k: v for k, v in merged.items() if k != "feed"}
        json.dump(slim, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    merged["_errors"] = errors
    return merged


def sync_feed(events: list) -> list:
    """Append the events we have not stored yet (same file and format as feed_logger.py) and return all of them."""
    have = {e["id"]: e for e in read_jsonl(FEED_PATH) if "id" in e}
    new = sorted((e for e in events if e["id"] not in have), key=lambda e: e["id"])
    if new:
        os.makedirs(log.LOG_DIR, exist_ok=True)
        with open(FEED_PATH, "a", encoding="utf-8") as f:
            for e in new:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        have.update({e["id"]: e for e in new})
    return [have[k] for k in sorted(have)]


def try_connect():
    """Our key, if there is one and it works. The dashboard never needs it, it only adds our own numbers."""
    try:
        from agent import connect
        b = connect()
        b.me()
        return b
    except (SystemExit, Exception):
        return None


# ---------------------------------------------------------------- one conversation

def cash_of(o: dict):
    return learn._cash(o) if o else None


def rows_of(t: dict, me: str) -> list:
    """The messages of a thread as table rows: who spoke, what they said, the price they put on the table."""
    dealer, out, last = t.get("with"), [], {}
    for m in t.get("messages") or []:
        o = m.get("offer") or {}
        p = cash_of(o)
        who = "dealer" if m.get("sender") == dealer else ("us" if m.get("sender") == me else "team")
        row = {"tick": m.get("tick"), "who": who, "sender": m.get("sender"), "text": m.get("text"), "price": p,
               "final": bool(o.get("final")), "status": o.get("status"), "offer": o.get("id")}
        if p is not None:
            row["step"] = p - last[who] if who in last else None
            last[who] = p
        out.append(row)
    return out


def infer_topic(t: dict) -> dict:
    """The feed shows threads that opened before it started: read the topic from the offers instead."""
    dealer = t.get("with")
    for m in t.get("messages") or []:
        o = m.get("offer") or {}
        gives = o.get("give") if o.get("maker") == dealer else o.get("want")  # what the dealer hands over
        gets = o.get("want") if o.get("maker") == dealer else o.get("give")
        for ty in (gives or {}).get("types") or []:
            kind, _, ref = ty.partition(":")
            return {"buy": {"pack": ref}} if kind == "pack" else {"buy": {"card": ref}}
        for a in (gives or {}).get("assets") or []:
            if a.get("kind") == "card":
                return {"buy": {"card": a.get("ref")}}
        if (gets or {}).get("assets"):
            return {"sell": {"assets": [a.get("id") for a in gets["assets"]]}}
    return {}


def finish(t: dict, me: str, cards_by_id: dict, traits: dict, deal_price=None, source="ours") -> dict:
    """One thread, ready to draw: rows, learned features, outcome."""
    f = learn.features(t, cards_by_id)
    if deal_price is not None:  # the feed shows offers as they were when sent, the settlement says what was paid
        sell = f["kind"].startswith("sell")
        seen = f["hers"] + [deal_price]
        f.update(deal_price=deal_price, best=max(seen) if sell else min(seen))
    rows = rows_of(t, me)
    ticks = [r["tick"] for r in rows if r["tick"] is not None]
    return {
        "id": t.get("id"), "source": source, "team": t.get("team"), "dealer": t.get("with"), "kind": f["kind"],
        "status": "deal" if f["deal_price"] is not None else (t.get("status") or "closed"),
        "closed_reason": t.get("closed_reason"), "tick0": t.get("created_tick", ticks[0] if ticks else None),
        "tick1": ticks[-1] if ticks else None, "deal": f["deal_price"], "first": f["first"], "best": f["best"],
        "hers": f["hers"], "ours": f["ours"], "final_after": f["final_after"], "moves": f["moves"],
        "accepted_opening": f["accepted_opening"], "rows": rows,
    }


# ---------------------------------------------------------------- the feed: other teams' haggles

def feed_threads(events: list, me: str, cards_by_id: dict, traits: dict) -> list:
    """Dealer conversations of every team but us, rebuilt from the public feed."""
    th = {}
    for e in events:
        p = e.get("payload") or {}
        if p.get("kind") != "persona" or e["type"] not in ("thread.opened", "thread.message"):
            continue
        t = th.setdefault(p["thread"], {"id": p["thread"], "team": p.get("team"), "with": p.get("with"),
                                        "messages": [], "status": "open", "kind": "persona"})
        if e["type"] == "thread.opened":
            t["topic"], t["created_tick"] = p.get("topic"), e["tick"]
        else:
            t["messages"].append({"id": p.get("message"), "tick": e["tick"], "sender": p.get("sender"),
                                  "text": p.get("text"), "offer": p.get("offer")})
    sett = [e["payload"] for e in events if e["type"] == "settlement" and e["payload"].get("persona")]
    last_tick = max((e["tick"] for e in events), default=0)
    used, out = set(), []
    for t in sorted(th.values(), key=lambda x: x["id"]):
        if t["team"] == me or not t["messages"]:
            continue
        if not t.get("topic"):
            t["topic"] = infer_topic(t)
        end = max(m["tick"] for m in t["messages"])
        hit = next((s for s in sett if s["settlement"] not in used and t["team"] in s["parties"] and s["persona"] == t["with"]
                    and end - 1 <= s["tick"] <= end + 3), None)
        if hit:
            used.add(hit["settlement"])
        r = finish(t, me, cards_by_id, traits, hit["price"] if hit else None, source="feed")
        if not hit:
            r["status"] = "open" if last_tick - end <= 4 else "ended"
        out.append(r)
    return out


# ---------------------------------------------------------------- what the dealer does, over many conversations

def fit(points: list) -> dict:
    """Least squares y = a + b x and the correlation; None when the points say nothing."""
    if len(points) < 3:
        return {}
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0:
        return {}
    b = sxy / sxx
    return {"a": round(my - b * mx, 2), "b": round(b, 2), "r": round(sxy / (sxx * syy) ** 0.5, 2), "n": len(points)}


def summarize(threads: list) -> dict:
    """dealer -> kind -> what we see across every team's conversations (ours flagged)."""
    groups = defaultdict(list)
    for t in threads:
        if t["first"] is not None:
            groups[(t["dealer"], t["kind"])].append(t)
    out = {}
    for (dealer, kind), ts in groups.items():
        sell = kind.startswith("sell")
        spoke = [t for t in ts if t["ours"]]
        pts = []
        for t in spoke:
            if len(t["hers"]) >= 2:
                d1 = abs(t["hers"][0] - t["hers"][1])
                last = t["deal"] if t["deal"] is not None else t["hers"][-1]
                pts.append({"thread": t["id"], "team": t["team"], "d1": d1, "end": last, "deal": t["deal"] is not None,
                            "ours": t["source"] == "ours", "tick": t["tick0"]})
        deals = [t["deal"] for t in ts if t["deal"] is not None]
        firsts = [t["first"] for t in ts]
        finals = [t["final_after"] for t in spoke if t["final_after"] is not None]
        out.setdefault(dealer, {})[kind] = {
            "threads": len(ts), "ours": sum(1 for t in ts if t["source"] == "ours"), "spoke": len(spoke),
            "first_median": statistics.median(firsts) if firsts else None, "first_set": sorted(set(firsts)),
            "deals": sorted(deals), "deal_median": statistics.median(deals) if deals else None,
            "deal_best": (max(deals) if sell else min(deals)) if deals else None,
            "final_after_median": statistics.median(finals) if finals else None,
            "fit": fit([(p["d1"], p["end"]) for p in pts]), "points": pts,
        }
    return out


def team_stats(events: list, threads: list, board: dict) -> list:
    """The leaderboard plus what the feed shows each team doing."""
    per = defaultdict(lambda: {"dealer_threads": 0, "dealer_deals": 0, "team_trades": 0, "offers": 0, "packs": 0,
                               "last_tick": 0, "spent": 0})
    for t in threads:
        s = per[t["team"]]
        s["dealer_threads"] += 1
        s["dealer_deals"] += t["deal"] is not None
        s["spent"] += (t["deal"] or 0) if t["kind"].startswith("buy") else 0
    for e in events:
        p = e.get("payload") or {}
        if e["type"] == "offer.listed":
            per[p.get("maker") or e.get("actor")]["offers"] += 1
        elif e["type"] == "pack.opened":
            per[p.get("team")]["packs"] += 1
        elif e["type"] == "settlement" and not p.get("persona"):
            for team in p.get("parties") or []:
                per[team]["team_trades"] += 1
        who = e.get("actor") or p.get("team") or ""
        per[who]["last_tick"] = max(per[who]["last_tick"], e["tick"])
    rows = []
    for team in board.get("teams", []):
        rows.append({**{k: team.get(k) for k in ("team", "name", "rank", "score", "negotiating", "market", "level", "deals",
                                                  "album_filled", "album_slots", "pages_complete", "luck", "venue")},
                     "rarest": (team.get("rarest") or {}).get("name"), **per.get(team["team"], {})})
    return rows


def team_demand(events: list, me: str, collection: dict = None) -> dict:
    """The cards each other team asks for in public: offers that want a card and dealer threads to buy one.

    Asking is not proof of missing it (values are private), and starting hands and pack contents are hidden.
    A card counts as got when a settlement gave the team a copy at or after its last ask (5 ticks of slack).
    """
    want = defaultdict(dict)  # team -> ref -> row
    got = defaultdict(dict)   # team -> ref -> last tick a copy reached it

    def ask(team, ref, tick, via, bid=None):
        if not team or team == me or not str(team).startswith("t"):
            return
        r = want[team].setdefault(ref, {"ref": ref, "n": 0, "offers": 0, "dealer": 0, "first": tick, "last": tick, "bid": None})
        r["n"] += 1
        r[via] += 1
        r["last"] = max(r["last"], tick)
        if bid:
            r["bid"] = bid  # the latest bid, not the highest: prices move

    for e in events:
        p = e.get("payload") or {}
        if e["type"] == "offer.listed":
            o = p.get("offer") or {}
            give = o.get("give") or {}
            for ty in (o.get("want") or {}).get("types") or []:
                if ty.startswith("card:"):
                    alone = not give.get("assets") and not give.get("types")
                    ask(o.get("maker"), ty[5:], e["tick"], "offers", give.get("cash") if alone else None)
        elif e["type"] == "thread.opened" and p.get("kind") == "persona":
            ref = ((p.get("topic") or {}).get("buy") or {}).get("card")
            if ref:
                ask(p.get("team"), ref, e["tick"], "dealer")
        elif e["type"] == "settlement":
            for it in p.get("items") or []:
                if it.get("kind") == "card" and it.get("to"):
                    got[it["to"]][it["ref"]] = e["tick"]

    ours = {}
    for s in (collection or {}).get("sets") or []:
        for c in s["cards"]:
            ours[c["ref"]] = {"n": c["n"], "floor": c.get("floor")}
    teams = {}
    for team, cards in want.items():
        rows = []
        for r in cards.values():
            g = got[team].get(r["ref"])
            r["got"] = g is not None and g >= r["last"] - 5
            o = ours.get(r["ref"]) or {}
            r["we_have"], r["floor"] = o.get("n", 0), o.get("floor")
            rows.append(r)
        rows.sort(key=lambda r: (r["got"], -r["n"], -r["last"]))
        teams[team] = rows
    # our spare copies that someone still asks for: where to offer them first
    spare = defaultdict(list)
    for team, rows in teams.items():
        for r in rows:
            if not r["got"] and r["we_have"] > 1:
                spare[r["ref"]].append({"team": team, "n": r["n"], "last": r["last"], "bid": r["bid"]})
    sell = [{"ref": ref, "floor": ours[ref]["floor"], "copies": ours[ref]["n"],
             "teams": sorted(ts, key=lambda t: (-(t["bid"] or 0), -t["last"]))} for ref, ts in spare.items()]
    sell.sort(key=lambda x: -len(x["teams"]))
    return {"teams": teams, "sell": sell}


def fetch_book(venues: list, offline: bool = False) -> dict:
    """Every open offer on every open venue (public). Makers come as pseudonyms: team_market names them from the feed."""
    if offline:
        return {"offers": [], "errors": []}
    from concurrent.futures import ThreadPoolExecutor
    ids = [v.get("venue") or v.get("id") for v in venues if (v.get("status") or "open") == "open"]
    ids = [i for i in ids if i]
    if "rastro" not in ids:
        ids.insert(0, "rastro")

    def one(v):
        try:
            with urllib.request.urlopen(f"{PUBLIC}/api/venues/{v}/offers", timeout=10) as r:
                return v, json.loads(r.read().decode("utf-8")).get("offers") or [], None
        except Exception as e:
            return v, [], f"{v}: {type(e).__name__}"

    offers, errors = [], []
    with ThreadPoolExecutor(8) as ex:
        for v, offs, err in ex.map(one, ids):
            offers += [{**o, "venue": o.get("venue") or v} for o in offs]
            if err:
                errors.append(err)
    return {"offers": offers, "errors": errors}


def _cards_of(leg: dict) -> list:
    leg = leg or {}
    return [a["ref"] for a in leg.get("assets") or [] if a.get("kind") == "card" and a.get("ref")] + \
           [t[5:] for t in leg.get("types") or [] if t.startswith("card:")]


def team_market(events: list, book: dict, demand: dict, collection: dict, me: str) -> dict:
    """What the other teams sell now (open offers that give cards for cash) and the pairs a seller and a buyer make.

    Buyers are open bids in the book (cash for a card) and, failing that, a team that asked for the card in the feed and
    has not got it (its last bid is a hint, not a standing price). We appear as a buyer when the card is missing from a
    page and the ask is within buy_cap. Prices are as listed: the venue's fee is not in them.
    """
    maker_of = {}
    for e in events:
        if e["type"] == "offer.listed":
            o = (e.get("payload") or {}).get("offer") or {}
            if o.get("id") is not None:
                maker_of[o["id"]] = o.get("maker")
    fee = {}
    sells, bids, swaps = [], [], []
    for o in book.get("offers") or []:
        team = maker_of.get(o.get("id")) or o.get("maker")
        known = str(team).startswith("t")
        give, want = o.get("give") or {}, o.get("want") or {}
        gc, wc = _cards_of(give), _cards_of(want)
        row = {"offer": o.get("id"), "team": team if known else None, "alias": None if known else o.get("maker"),
               "venue": o.get("venue"), "created": o.get("created_tick"), "expires": o.get("expires_tick"),
               "to": o.get("to"), "ours": team == me}
        if gc and not wc and want.get("cash"):
            for ref in gc:  # a bundle is priced as a whole: say so instead of splitting the price
                sells.append({**row, "ref": ref, "ask": want["cash"], "bundle": len(gc)})
        elif wc and not gc and give.get("cash"):
            for ref in wc:
                bids.append({**row, "ref": ref, "bid": give["cash"], "bundle": len(wc)})
        elif gc and wc:
            swaps.append({**row, "give": gc, "want": wc, "cash_in": give.get("cash") or 0, "cash_out": want.get("cash") or 0})
    sells.sort(key=lambda r: (r["ref"], r["ask"]))

    missing = {}
    for s in (collection or {}).get("sets") or []:
        for c in s["cards"]:
            if not c["n"] and c.get("cap") is not None:
                missing[c["ref"]] = {"cap": c["cap"], "page": c["page"]}
    pending = defaultdict(list)  # ref -> teams still asking in the feed
    for team, rows in ((demand or {}).get("teams") or {}).items():
        for r in rows:
            if not r["got"]:
                pending[r["ref"]].append({"team": team, "bid": r["bid"], "n": r["n"], "last": r["last"]})

    pairs = []
    for s in sells:
        if s["to"] and s["to"] != me:
            continue  # offered to one team only
        buyers = {}
        for b in bids:
            if b["ref"] == s["ref"] and b["bundle"] == 1 and (b["team"] or b["alias"]) != (s["team"] or s["alias"]):
                key = b["team"] or b["alias"]
                if key not in buyers or b["bid"] > buyers[key]["bid"]:
                    buyers[key] = {"buyer": key, "bid": b["bid"], "source": "puja abierta", "bid_offer": b["offer"],
                                   "bid_venue": b["venue"]}
        for p in pending.get(s["ref"], []):
            if p["team"] != s["team"] and p["team"] not in buyers:
                buyers[p["team"]] = {"buyer": p["team"], "bid": p["bid"], "source": f"la pidió ×{p['n']} (t{p['last']})",
                                     "bid_offer": None, "bid_venue": None}
        m = missing.get(s["ref"])
        if m and not s["ours"] and m["page"]:
            buyers[me] = {"buyer": me, "bid": m["cap"], "source": "nos falta (tope de compra)", "bid_offer": None,
                          "bid_venue": None}
        for b in buyers.values():
            gap = None if b["bid"] is None else b["bid"] - s["ask"]
            pairs.append({"ref": s["ref"], "seller": s["team"] or s["alias"], "seller_known": bool(s["team"]),
                          "ask": s["ask"], "bundle": s["bundle"], "sell_offer": s["offer"], "sell_venue": s["venue"],
                          **b, "gap": gap, "cross": gap is not None and gap >= 0 and s["bundle"] == 1})
    pairs.sort(key=lambda p: (not p["cross"], p["gap"] is None, -(p["gap"] or 0), p["ref"]))
    return {"sells": sells, "bids": bids, "swaps": swaps, "pairs": pairs, "book_size": len(book.get("offers") or []),
            "errors": book.get("errors") or []}


def team_trades(events: list) -> list:
    out = []
    for e in events:
        p = e.get("payload") or {}
        if e["type"] == "settlement":
            out.append({"tick": e["tick"], "parties": p.get("parties"), "persona": p.get("persona"), "price": p.get("price"),
                        "venue": p.get("venue"), "fee": p.get("fee"),
                        "items": [f"{i.get('ref')} ({i.get('rarity')})" if i.get("kind") == "card" else i.get("ref") for i in p.get("items") or []]})
    return out[-120:]


# ---------------------------------------------------------------- duels

def load_duels(b) -> list:
    """Duels from the API when we have a key, else from the copies we kept. Finished ones are kept in logs/duels/."""
    os.makedirs(DUEL_DIR, exist_ok=True)
    got = {}
    if b is not None:
        try:
            for done in (False, True):
                for d in b.duels(done=done).get("duels", []):
                    got[int(d["duel"])] = d
        except Exception:
            pass
    for d in got.values():
        if d.get("status") != "live":
            json.dump(d, open(os.path.join(DUEL_DIR, f"{d['duel']}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for name in os.listdir(DUEL_DIR):
        if name.endswith(".json") and int(name[:-5]) not in got:
            got[int(name[:-5])] = json.load(open(os.path.join(DUEL_DIR, name), encoding="utf-8"))
    return [got[k] for k in sorted(got)]


def duel_view(d: dict, decisions: list) -> dict:
    msgs = d.get("messages") or []
    rival = [m["price"] for m in msgs if m.get("from") != "you" and m.get("price") is not None]
    mine = [m["price"] for m in msgs if m.get("from") == "you" and m.get("price") is not None]
    lim = d.get("your_limit")
    res = d.get("result")
    return {
        "id": int(d["duel"]), "session": d.get("session"), "role": d.get("role"), "item": d.get("item"),
        "issues": d.get("issues"), "limit": lim, "limit_meaning": d.get("limit_meaning"), "rival": d.get("rival"),
        "status": d.get("status"), "price": d.get("price"), "days": d.get("days"), "result": res,
        "rounds": d.get("rounds"), "decay": d.get("decay_per_round"), "deadline": d.get("deadline_tick"),
        "start": min([d["deadline_tick"] - (12 if (d.get("decay_per_round") or 0) >= 0.1 else 16)]
                     + [m["tick"] for m in msgs if m.get("tick") is not None]) if d.get("deadline_tick") else None,
        "days_weight": d.get("your_days_weight"), "days_meaning": d.get("days_meaning"),
        "messages": [{"tick": m.get("tick"), "who": "us" if m.get("from") == "you" else "rival", "text": m.get("text"),
                      "price": m.get("price"), "days": m.get("days")} for m in msgs],
        "decisions": decisions, "rival_open_share": round(rival[0] / lim, 2) if rival and lim else None,
        "our_open_share": round(mine[0] / lim, 2) if mine and lim else None,
        "result_share": round(res / lim, 3) if res is not None and lim else None,
    }


def duel_summary(duels: list) -> list:
    out = []
    for role in ("buyer", "seller"):
        ds = [d for d in duels if d["role"] == role and d["status"] in ("deal", "no_deal")]
        deals = [d for d in ds if d["status"] == "deal" and d["result"] is not None]
        if not ds:
            continue
        out.append({"role": role, "duels": len(ds), "deals": len(deals), "deal_rate": round(len(deals) / len(ds), 2),
                    "mean_share": round(statistics.mean(d["result_share"] for d in deals if d["result_share"] is not None), 3)
                    if any(d["result_share"] is not None for d in deals) else None,
                    "mean_rounds": round(statistics.mean(d["rounds"] or 0 for d in deals), 1) if deals else None,
                    "rival_open": round(statistics.mean(d["rival_open_share"] for d in ds if d["rival_open_share"] is not None), 2)
                    if any(d["rival_open_share"] is not None for d in ds) else None})
    return out


def running(pattern: str) -> bool:
    """Is a process whose command line matches `pattern` running on this machine (pgrep -f)?"""
    try:
        return subprocess.run(["pgrep", "-f", pattern], capture_output=True, timeout=3).returncode == 0
    except Exception:
        return False


def session_stats(ds: list) -> dict:
    done = [d for d in ds if d["status"] in ("deal", "no_deal")]
    deals = [d for d in done if d["status"] == "deal" and d["result"] is not None]
    return {"duels": len(ds), "live": sum(d["status"] == "live" for d in ds), "done": len(done), "deals": len(deals),
            "no_deals": len(done) - len(deals), "deal_rate": round(len(deals) / len(done), 2) if done else None,
            "mean_result": round(statistics.mean(d["result"] for d in deals), 1) if deals else None,
            "points": round(sum(d["result"] for d in deals), 1),
            "mean_rounds": round(statistics.mean(d["rounds"] or 0 for d in deals), 1) if deals else None}


def avoidable(d: dict) -> bool:
    """A no-deal we could have avoided: the rival made at least one offer inside our limit worth >= 1 to us
    (price surplus + w x days, with w as our agent read it). Silent rivals and rivals never inside our limit don't count."""
    if d["status"] != "no_deal" or d.get("limit") is None:
        return False
    w = next((e.get("w") for e in reversed(d["decisions"]) if e.get("w") is not None), 0.0) or 0.0
    for m in d["messages"]:
        if m["who"] == "rival" and m.get("price") is not None:
            if d.get("deadline") is not None and m.get("tick") is not None and m["tick"] > d["deadline"] - 2:
                continue  # same as analyze_duels.py: an offer in the last 2 ticks may not have been answerable
            s = (d["limit"] - m["price"]) if d["role"] == "buyer" else (m["price"] - d["limit"])
            if s >= 0 and s + w * (m.get("days") or 0) >= 1:
                return True
    return False


def duel_live(duels: list, clock: dict, upcoming: list, switch_avoidable: int = 2) -> dict:
    """What the Live panel of the Duelos page needs: the session being played (or the last one), its scoreboard
    next to the session before, the safety switch, the duel agent's health and the next duel session."""
    tick = (clock or {}).get("tick")
    sessions = sorted({d["session"] for d in duels if d.get("session") is not None})
    live = [d for d in duels if d["status"] == "live"]
    cur = max((d["session"] for d in live), default=sessions[-1] if sessions else None)
    prev = max((s for s in sessions if cur is not None and s < cur), default=None)
    board = session_stats([d for d in duels if d.get("session") == cur]) if cur is not None else None
    before = session_stats([d for d in duels if d.get("session") == prev]) if prev is not None else None
    v2 = any("kind" in e for d in duels if d.get("session") == cur for e in d["decisions"])  # played by the waiting play
    missed = [d["id"] for d in duels if d.get("session") == cur and avoidable(d)]
    switch = ("trip" if len(missed) >= switch_avoidable else "ok") if v2 else None
    last_dec = max((e.get("tick") or 0 for d in duels for e in d["decisions"]), default=None)
    alerts = [a for a in read_jsonl(os.path.join(log.LOG_DIR, "alerts.jsonl")) if str(a.get("level", "")).startswith("DUEL")]
    nxt = None
    th = (clock or {}).get("t_hours")
    for u in upcoming or []:
        if u.get("action") == "duels" and th is not None and u["at_hours"] >= th:
            nxt = {"name": (u.get("params") or {}).get("name") or u.get("note"), "note": u.get("note"),
                   "minutes": round((u["at_hours"] - th) * 60), "params": u.get("params")}
            break
    return {"tick": tick, "paused": (clock or {}).get("paused"), "session": cur, "prev_session": prev,
            "live": [d["id"] for d in live], "board": board, "before": before, "switch": switch,
            "switch_avoidable": switch_avoidable, "avoidable": missed, "v2": v2,
            "watch": {"duels_watch": running("duels_watch\\.py"), "duels_py": running("(^|[ /])duels\\.py"), "last_decision_tick": last_dec},
            "alerts": [{"ts": a.get("ts"), "level": a.get("level"), "text": a.get("text")} for a in alerts[-8:]],
            "next": nxt}


# ---------------------------------------------------------------- the market: what the trader does with offers

def leg_text(leg: dict) -> str:
    """One side of an offer in words: '2 P', 'LAV-02', 'cualquier LAV-02', '3 P + LAV-02'."""
    leg = leg or {}
    parts = []
    if leg.get("cash"):
        parts.append(f"{leg['cash']} P")
    parts += [a.get("ref") or f"{a.get('kind')} {a.get('id')}" for a in leg.get("assets") or []]
    parts += [("cualquier " if t.startswith("card:") else "") + t.split(":", 1)[-1] for t in leg.get("types") or []]
    parts += list(leg.get("cards") or [])
    return " + ".join(parts) or "nada"


def trader_view(counters_sent_cap: int = 200, decisions_cap: int = 400) -> dict:
    """What trader.py judged, answered and settled (logs/trader*.jsonl), with the counts the chapter needs."""
    rows = read_jsonl(os.path.join(log.LOG_DIR, "trader.jsonl"))
    for r in rows:
        r.setdefault("source", "to_us")  # the first version only judged offers addressed to us
        r.pop("ts", None)
    counters = read_jsonl(os.path.join(log.LOG_DIR, "trader_counter.jsonl"))
    outcomes = {o["incoming"]: o for o in read_jsonl(os.path.join(log.LOG_DIR, "trader_outcome.jsonl"))}
    accepts = read_jsonl(os.path.join(log.LOG_DIR, "trader_accept.jsonl"))
    settled = {x["offer"]: x for x in read_jsonl(os.path.join(log.LOG_DIR, "trader_settlement.jsonl"))}
    for a in accepts:  # what the game recorded after each accept: the price and fee we really paid
        x = settled.get(a["offer"])
        a["settlement"] = {k: x.get(k) for k in ("found", "price", "fee", "expected_cash", "expected_fee", "tick")} if x else None
        a.pop("ts", None)
        a.pop("cash_before", None)
    cancels = {c["offer"]: c for c in read_jsonl(os.path.join(log.LOG_DIR, "trader_cancel.jsonl"))}
    stale = [{**{k: x.get(k) for k in ("tick", "offer", "cards", "cash")}, "cancelled": x["offer"] in cancels}
             for x in read_jsonl(os.path.join(log.LOG_DIR, "trader_stale_bid.jsonl"))]
    for c in counters:
        o = outcomes.get(c["incoming"])
        c["outcome"] = o["outcome"] if o else "open"
        c["settled_price"] = o.get("settled_price") if o else None
        c.pop("ts", None)
    acts = Counter((r["action"], bool(r.get("live"))) for r in rows)
    by_venue = {}
    for r in rows:
        v = by_venue.setdefault(r["venue"], {"venue": r["venue"], "decisions": 0, "accept": 0, "counter": 0, "ignore": 0, "human": 0, "surplus": []})
        v["decisions"] += 1
        v[r["action"]] = v.get(r["action"], 0) + 1
        v["surplus"].append(r.get("surplus"))
    for v in by_venue.values():
        s = [x for x in v.pop("surplus") if x is not None]
        v["surplus_median"] = round(statistics.median(s), 1) if s else None
    last = rows[-1] if rows else None
    return {
        "decisions": rows[-decisions_cap:], "total": len(rows),
        "counts": {"accept": sum(n for (a, _), n in acts.items() if a == "accept"), "counter": sum(n for (a, _), n in acts.items() if a == "counter"),
                   "ignore": sum(n for (a, _), n in acts.items() if a == "ignore"), "human": sum(n for (a, _), n in acts.items() if a == "human"),
                   "live": sum(n for (_, live), n in acts.items() if live), "shadow": sum(n for (_, live), n in acts.items() if not live)},
        "by_venue": sorted(by_venue.values(), key=lambda v: -v["decisions"]),
        "counters": counters[-counters_sent_cap:], "accepted_by_us": accepts[-60:], "stale_bids": stale[-40:],
        "cancelled": len(cancels),
        "counter_outcomes": dict(Counter(c["outcome"] for c in counters)),
        "mode": ("live" if last and last.get("live") else "shadow") if last else None, "last_tick": last["tick"] if last else None,
        "paused": os.path.exists(os.path.join(log.LOG_DIR, "trader.pause")),
        "first_tick": rows[0]["tick"] if rows else None,
    }


def market_view(pub: dict, b, st, me: str) -> dict:
    """Our place in the market: the trader's work, our stall, the other venues, our offers open right now."""
    venues = []
    for v in (pub.get("venues") or {}).get("venues", []):
        venues.append({k: v.get(k) for k in ("venue", "name", "owner", "owner_name", "status", "fee_bps", "fee_per_card", "trades",
                                              "volume", "fees", "traders", "pairs", "starter", "house", "description", "value_created")}
                      | {"mechanism": (v.get("rules") or {}).get("mechanism"), "ours": v.get("owner") == me})
    offers = []
    if b is not None:
        try:
            for o in b.my_offers().get("offers") or []:
                cards = [t.split(":", 1)[1] for t in (o.get("want") or {}).get("types") or [] if t.startswith("card:")]
                cards += list((o.get("want") or {}).get("cards") or [])
                offers.append({"id": o["id"], "dir": "us" if o.get("maker") == me else "to_us", "other": o.get("to") if o.get("maker") == me else o.get("maker"),
                               "bid": o.get("maker") == me and o.get("status") == "open" and bool((o.get("give") or {}).get("cash")) and bool(cards),
                               "cards": cards, "cash": (o.get("give") or {}).get("cash") or 0,
                               "venue": o.get("venue"), "status": o.get("status"), "give": leg_text(o.get("give")), "want": leg_text(o.get("want")),
                               "created": o.get("created_tick"), "expires": o.get("expires_tick")})
        except Exception:
            pass
    score = (st.me.get("score") if st else None) or {}
    bench = [u for u in ((pub.get("schedule") or {}).get("upcoming") or []) if u.get("action") == "bench"]
    trader = trader_view()
    open_ids = {o["id"] for o in offers if o["status"] == "open"}
    for x in trader["stale_bids"]:  # a stale bid only matters while it is still open
        x["open"] = x["offer"] in open_ids and not x["cancelled"] if b is not None else None
    bids = [o for o in offers if o["bid"]]
    committed = sum(o["cash"] for o in bids)
    cash = st.me.get("cash") if st else None
    stale_ids = {x["offer"] for x in trader["stale_bids"] if x.get("open")}
    for o in bids:
        o["stale"] = o["id"] in stale_ids
    ledger_path = os.path.join(ROOT, "TRADES.md")
    try:  # one timeline of the trader's operations, failures apart (bz/activity.py)
        from . import activity
        act = activity.view()
    except Exception as e:  # the chapter must still draw
        act = {"error": f"{type(e).__name__}: {e}"}
    return {"trader": trader, "activity": act, "venues": venues, "offers": offers, "bench_next": bench[:5],
            "bids": {"list": bids, "committed": committed, "cash": cash, "free": (cash - committed) if cash is not None else None},
            "ledger": open(ledger_path, encoding="utf-8").read() if os.path.exists(ledger_path) else None,
            "our_venue": next((v for v in venues if v["ours"]), None),
            "bench": {k: score.get(k) for k in ("bench_efficiency", "bench_points", "mm_points", "bench_venue", "market")},
            "limits": trader_constants()}


def trader_constants() -> dict:
    out = {}
    try:
        import trader
        out.update(counter_ticks=trader.COUNTER_TICKS, max_outstanding=trader.MAX_OUTSTANDING, maker_cooldown=trader.MAKER_COOLDOWN)
        from .trade import ANCHOR
        out["anchor"] = ANCHOR
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- formulas and parameters

def _src_default(path: str, pattern: str):
    try:
        m = re.search(pattern, open(os.path.join(ROOT, path), encoding="utf-8").read())
        return float(m.group(1)) if m else None
    except OSError:
        return None


def formulas(b, st, model: dict, traits: dict) -> dict:
    """The numbers behind our limits, with today's values: what an item is worth to us, the cap or floor that follows."""
    out = {
        "constants": {
            "step_frac": _src_default("agent.py", r'"--step",[^)]*default=([0-9.]+)'),
            "margin": _src_default("agent.py", r'"--margin",[^)]*default=([0-9.]+)'),
            "accept_gap": 1, "max_msgs": 40, "messages_per_trait_default": learn.MESSAGES_PER_TRAIT,
            "messages_per_trait_seen": round(learn.messages_per_trait(model, traits), 2),
            "trade_min_surplus": MIN_SURPLUS, "trade_min_share": MIN_SHARE, "house_fee_bps": HOUSE_FEE[0],
            "house_fee_per_card": HOUSE_FEE[1], "duel_open_frac": OPEN_FRAC, "duel_beta": 2.0, "duel_rounds": 3,
        },
        "limits": trader_constants(),
        "values": None,
    }
    if st is None:
        return out
    try:
        v = price.from_state(st)
        packs = [{"pack": pid, "worth": round(v.pack_value(pid), 2), "cap": price.buy_cap(v.pack_value(pid), margin=out["constants"]["margin"] or 0.1),
                  "neutral": v.packs[pid].get("expected_book"), "slots": v.packs[pid].get("slots")} for pid in v.packs]
        spares = [{"ref": a["ref"], "name": a.get("name"), "rarity": a.get("rarity"), "worth": round(v.copy_value(a["ref"]), 2),
                   "floor": price.sell_floor(v.copy_value(a["ref"]))} for a in st.spares()]
        out["values"] = {"book": v.book, "marginals": v.marginals, "affinity": st.me.get("affinity"), "packs": packs,
                         "spares": spares[:24]}
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- our collection

def collection_view(st) -> dict:
    """Every card of every set: how many copies we hold, what each is worth to us, what is missing and repeated.

    A held copy is priced with its own your_value (/api/me, page bonus included); a missing card with the value of the
    next copy (price.Valuer, the same as /api/me/value), which leaves the page bonus out.
    """
    if st is None:
        return None
    try:
        v = price.from_state(st)
        held = st.by_ref()
        album = {p["set"]: p for p in (st.me.get("album") or {}).get("pages") or []}
        sets = []
        for s in st.catalog["sets"]:
            cards = []
            for c in s["cards"]:
                copies = held.get(c["id"], [])
                row = {"ref": c["id"], "name": c.get("name"), "rarity": c["rarity"], "page": bool(c.get("page")),
                       "minted": c.get("minted"), "print_run": c.get("print_run"), "n": len(copies),
                       "values": [a.get("your_value") for a in copies], "ids": [a["id"] for a in copies]}
                if c["id"] in v.cards:
                    nxt = v.card_value(c["id"])
                    row["next"] = round(nxt, 2)
                    row["cap"] = price.buy_cap(nxt)
                if len(copies) > 1:
                    spare = copies[-1].get("your_value") or 0  # the cheapest copy is the one we would sell
                    row["spare"] = spare
                    row["floor"] = price.sell_floor(spare)
                cards.append(row)
            page = album.get(s["id"]) or {}
            missing = [c["ref"] for c in cards if c["page"] and not c["n"]]
            sets.append({"id": s["id"], "name": s.get("name"), "color": s.get("color"), "released": bool(s.get("released")),
                         "release": s.get("release"), "affinity": (st.me.get("affinity") or {}).get(s["id"]),
                         "have": page.get("have"), "of": page.get("of"), "complete": page.get("complete"),
                         "master": page.get("master"), "missing": missing if s.get("released") else None, "cards": cards})
        return {"sets": sets, "collection_value": st.me.get("collection_value"),
                "rarities": {k: r.get("color") for k, r in st.catalog.get("rarities", {}).items()},
                "album": {k: (st.me.get("album") or {}).get(k) for k in ("filled", "slots")},
                "page_bonus": st.catalog.get("values", {}).get("page_bonus"),
                "master_bonus": st.catalog.get("values", {}).get("master_bonus")}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- everything

def notes() -> dict:
    """DEALERS.md split by its '## ' headings: what we wrote down about each dealer."""
    path = os.path.join(ROOT, "DEALERS.md")
    if not os.path.exists(path):
        return {}
    parts = re.split(r"^## ", open(path, encoding="utf-8").read(), flags=re.M)
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] if "\n" in p else "" for p in parts[1:]}


def testbed_view() -> dict:
    """The testbed table, or why it is missing: a bug there must not take the rest of the dashboard down."""
    try:
        return testbed.cached()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def build(offline: bool = False, key: bool = True) -> dict:
    pub = fetch_public(offline)
    events = sync_feed((pub.get("feed") or {}).get("events") or [])
    b = try_connect() if key and not offline else None
    st = None
    if b is not None:
        try:
            from .state import State
            st = State(b)
            learn.backfill(b)
            learn.save_traits(b)
        except Exception:
            st = None
    traits = learn.load_traits() or {p["id"]: p.get("traits") or {} for p in (pub.get("dealers") or {}).get("personas", [])}
    cards = {c["id"]: c for s in (pub.get("catalog") or {}).get("sets", []) for c in s["cards"]}
    mine_threads = [t for t in learn.transcripts() if t.get("kind", "persona") == "persona" and t.get("with") in traits]
    me = (st.me["id"] if st else None) or (Counter(t.get("team") for t in mine_threads).most_common(1) or [[None]])[0][0]
    # a conversation still open is not stored yet: show it too
    if b is not None:
        try:
            have = {t["id"] for t in mine_threads}
            for th in (b.my_threads(status="open").get("threads") or []):
                if th["id"] not in have and th.get("kind") == "persona":
                    mine_threads.append(b.thread(th["id"]))
        except Exception:
            pass
    haggle_log = {h["thread"]: h for h in read_jsonl(os.path.join(log.LOG_DIR, "haggles.jsonl")) if h.get("thread")}
    ours = []
    for t in sorted(mine_threads, key=lambda x: x["id"]):
        r = finish(t, me, cards, traits)
        h = haggle_log.get(t["id"])
        r["params"] = {k: h.get(k) for k in ("opening", "limit", "label", "reason", "side")} if h else None
        ours.append(r)
    others = feed_threads(events, me, cards, traits)
    model = learn.build_model(cards)
    plans = {}
    for dealer, kinds in model.items():
        for kind in kinds:
            p = learn.plan(dealer, kind, cards, traits=traits.get(dealer))
            p["text"] = learn.describe(dealer, kind, p)
            p.pop("stats", None)
            plans.setdefault(dealer, {})[kind] = p
    dec = defaultdict(list)
    for e in read_jsonl(os.path.join(log.LOG_DIR, "duels.jsonl")):
        if e.get("duel") is not None:
            dec[int(e["duel"])].append({k: v for k, v in e.items() if k not in ("ts", "duel")})
    duels = [duel_view(d, dec.get(int(d["duel"]), [])) for d in load_duels(b)]
    dealers = {p["id"]: p for p in (pub.get("dealers") or {}).get("personas", [])}
    collection = collection_view(st)
    demand = team_demand(events, me, collection)
    try:
        venues = (pub.get("venues") or {}).get("venues") or []
        tmarket = team_market(events, fetch_book(venues, offline), demand, collection, me)
    except Exception as e:  # a bug here must not take the rest of the dashboard down
        tmarket = {"error": f"{type(e).__name__}: {e}"}
    return {
        "built": time.strftime("%Y-%m-%d %H:%M:%S"), "offline": offline, "errors": pub.get("_errors"), "me": me,
        "clock": pub.get("clock"), "upcoming": ((pub.get("schedule") or {}).get("upcoming") or [])[:14],
        "levels": (pub.get("levels") or {}).get("levels"),
        "feed_span": [events[0]["tick"], events[-1]["tick"]] if events else None, "feed_events": len(events),
        "dealers": dealers, "traits": traits, "ours": ours, "others": others,
        "summary": summarize(ours + others), "model": model, "plans": plans,
        "teams": team_stats(events, ours + others, pub.get("leaderboard") or {}),
        "rounds": (pub.get("leaderboard") or {}).get("rounds"), "trades": team_trades(events),
        "score": (st.me.get("score") if st else None), "score_log": read_jsonl(os.path.join(log.LOG_DIR, "score.jsonl")),
        "wallet": ({"cash": st.me.get("cash"), "level": st.me.get("level"), "collection": st.me.get("collection_value"),
                    "album": (st.me.get("album") or {}).get("filled")} if st else None),
        "duels": duels, "duel_summary": duel_summary(duels), "formulas": formulas(b, st, model, traits),
        "duel_live": duel_live(duels, pub.get("clock"), (pub.get("schedule") or {}).get("upcoming") or []),
        "market": market_view(pub, b, st, me), "notes": notes(), "testbed": testbed_view(),
        "collection": collection, "demand": demand, "team_market": tmarket,
    }
