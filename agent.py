"""Our agent. Commands:

    python3 agent.py status                     cash, level, score, spares, missing page cards
    python3 agent.py buy-pack [--limit 23]      haggle a neighbourhood pack from Abuela, then open it
    python3 agent.py sell-spares [--n 2]        sell our cheapest spare commons/uncommons to Abuela
    python3 agent.py buy-card LAV-09            haggle one card we miss from Abuela
    python3 agent.py abuela [--packs 1 --spares 2]   a session: spares first, then packs
    python3 agent.py learn                      save past conversations, show what we learned per dealer

Every haggle uses what earlier conversations of the same kind taught us (bz/learn.py); --no-learn turns it off.
Limits come from what the item is worth to us (bz/price.py): buy up to its value minus --margin, sell never below
what the copy is worth to us. If Abuela has never gone past our limit, we skip the haggle; --force tries anyway.

BAZAAR_KEY (and optionally BAZAAR_URL) come from the environment or a .env file next to this one.
"""
import argparse
import os
import sys

from bazaar_sdk import Bazaar, BazaarError
from bz import learn, log, price
from bz.haggle import haggle
from bz.state import State

HERE = os.path.dirname(os.path.abspath(__file__))
DEALER = "abuela"


def load_env() -> None:
    path = os.path.join(HERE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                os.environ.setdefault(k.strip().removeprefix("export "), v.strip().strip("'\""))


def connect() -> Bazaar:
    load_env()
    key = os.environ.get("BAZAAR_KEY")
    if not key:
        sys.exit("Falta BAZAAR_KEY: exporta la clave del equipo o ponla en .env (BAZAAR_KEY=tk-...).")
    return Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), key)


def menu(b: Bazaar) -> dict:
    return b.dealer(DEALER)["menu"]


def sells_item(m: dict, **match) -> dict:
    return next((s for s in m["sells"] if all(s.get(k) == v for k, v in match.items())), None)


def learned(st: State, args, kind: str) -> dict:
    """haggle() keyword arguments learned from earlier conversations of this kind."""
    if getattr(args, "no_learn", False):
        return {}
    p = learn.plan(DEALER, kind, st.cards_by_id)
    log.say(learn.describe(DEALER, kind, p))
    return {k: p[k] for k in ("target", "accept_at", "patience")}


def skipped(side: str, label: str, why: str) -> dict:
    log.say(f"skip {label}: {why}")
    return {"side": side, "label": label, "status": "skipped", "reason": why, "price": None, "ours": [], "theirs": []}


def out_of_reach(args, side: str, limit: int, plan: dict):
    """Why the haggle cannot work, or None: her best price ever is already beyond our limit."""
    best = plan.get("accept_at")
    if getattr(args, "force", False) or best is None:
        return None
    if side == "buy" and best > limit:
        return f"her best price ever is {best}, above our limit {limit}"
    if side == "sell" and best < limit:
        return f"her best bid ever is {best}, below our floor {limit}"
    return None


def cmd_learn(b: Bazaar, st: State, _args) -> None:
    n = learn.backfill(b)
    print(f"saved {n} new transcripts")
    for dealer, kinds in learn.build_model(st.cards_by_id).items():
        for kind, s in kinds.items():
            print(f"{dealer:8} {kind:24} n={s['n']} haggled={s['haggled']} first={s['first']} best={s['best']} "
                  f"patience={s['patience']} deals={s['deals']} opening_accepts={s['opening_accepts']}")
            print("         " + learn.describe(dealer, kind, learn.plan(dealer, kind, st.cards_by_id)))


def cmd_status(b: Bazaar, st: State, _args) -> None:
    me = st.me
    score = me.get("score") or {}
    print(f"{me['name']}: {me['cash']} P, level {me['level']}, score {score.get('score')} (rank {score.get('rank')})")
    print(f"unlocked: {me.get('unlocked') or me.get('dealers')}")
    cards = st.cards()
    print(f"{len(cards)} cards, {len(st.packs())} sealed packs, value {sum(a.get('your_value') or 0 for a in cards):.1f}")
    for a in st.spares():
        print(f"  spare {a['ref']:7} {a['name'][:28]:28} {a.get('rarity', ''):9} worth {a.get('your_value')} to us")
    for set_id, miss in st.missing().items():
        print(f"  {set_id}: missing {len(miss)} page cards {' '.join(miss)}")


def open_new_packs(b: Bazaar, st: State, ref: str = "sobre_barrio") -> None:
    st.refresh()
    for p in st.packs(ref):
        try:
            res = b.open_pack(p["id"])
        except BazaarError as e:
            log.say(f"cannot open pack {p['id']}: {e}")
            continue
        log.event("packs", pack=p["id"], cards=res.get("cards"), luck=res.get("luck"))
        for c in res.get("cards", []):
            log.say(f"  pulled {c.get('ref', c.get('id'))} {c['name']} · {c['rarity']} · #{c.get('serial')}/{c.get('print_run')}")


def cmd_buy_pack(b: Bazaar, st: State, args) -> dict:
    item = sells_item(menu(b), pack="sobre_barrio")
    lp = item["list_price"]
    worth = price.from_state(st).pack_value("sobre_barrio")
    limit = min(st.cash, args.limit or price.buy_cap(worth, margin=args.margin))
    label = f"pack (list {lp}, worth {worth:.1f} to us)"
    log.say(f"{label}: limit {limit}")
    if limit < 1:
        return skipped("buy", label, f"worth {worth:.1f} to us: not worth buying")
    opening = args.open or round(lp * 0.5)
    plan = learned(st, args, "buy:pack:sobre_barrio")
    why = out_of_reach(args, "buy", limit, plan)
    if why:
        return skipped("buy", label, why)
    res = haggle(b, DEALER, {"buy": {"pack": "sobre_barrio"}}, "buy", opening, limit,
                 step_frac=args.step, label=label, **plan)
    if res["status"] == "deal" and not args.keep:
        open_new_packs(b, st)
    return res


def cmd_buy_card(b: Bazaar, st: State, args) -> dict:
    card = st.cards_by_id.get(args.card)
    if not card:
        sys.exit(f"unknown card {args.card}")
    item = sells_item(menu(b), rarity=card["rarity"])
    if not item:
        sys.exit(f"Abuela does not sell {card['rarity']} cards")
    worth = b.value(args.card)["your_value"]
    lp = item["list_price"]
    limit = min(st.cash, args.limit or min(lp, price.buy_cap(worth, margin=args.margin)))
    label = f"{args.card} (list {lp}, worth {worth} to us)"
    if limit < 1:
        return skipped("buy", label, f"{args.card} is worth {worth} to us: not worth buying")
    plan = learned(st, args, f"buy:card:{card['rarity']}")
    why = out_of_reach(args, "buy", limit, plan)
    if why:
        return skipped("buy", label, why)
    return haggle(b, DEALER, {"buy": {"card": args.card}}, "buy", args.open or round(lp * 0.5), limit,
                  step_frac=args.step, label=label, **plan)


def cmd_sell_spares(b: Bazaar, st: State, args) -> list:
    buys = {r["rarity"] for r in menu(b)["buys"]}
    prices = {s["rarity"]: s["list_price"] for s in menu(b)["sells"] if s.get("rarity")}
    out = []
    valuer = price.from_state(st)
    for a in st.spares(rarities=buys)[: args.n]:
        rarity = st.cards_by_id[a["ref"]]["rarity"]
        worth = valuer.copy_value(a["ref"])
        floor = args.limit or price.sell_floor(worth)  # never sell below what the copy is worth to us
        opening = args.open or max(floor + 1, round(prices.get(rarity, 10) * 1.2))
        label = f"spare {a['ref']} (worth {worth:.1f} to us)"
        plan = learned(st, args, f"sell:{rarity}")
        why = out_of_reach(args, "sell", floor, plan)
        if why:
            out.append(skipped("sell", label, why))
            continue
        res = haggle(b, DEALER, {"sell": {"assets": [a["id"]]}}, "sell", opening, floor,
                     step_frac=args.step, label=label, **plan)
        out.append(res)
        if res["status"] == "error":
            break
    return out


def cmd_abuela(b: Bazaar, st: State, args) -> None:
    args.open = args.limit = None
    sells = cmd_sell_spares(b, st, args) if args.spares else []
    buys = []
    for _ in range(args.packs):
        st.refresh()
        buys.append(cmd_buy_pack(b, st, args))
        if buys[-1]["status"] in ("error", "skipped"):
            break
    for r in sells + buys:
        print(f"{r['side']:4} {r['label'][:45]:45} {r['status']:12} price {r['price']}  path ours {r['ours']} hers {r['theirs']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="The Bazaar agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("learn")
    for name in ("buy-pack", "buy-card", "sell-spares", "abuela"):
        p = sub.add_parser(name)
        p.add_argument("--step", type=float, default=0.15, help="share of the room left to our limit we concede per message")
        p.add_argument("--no-learn", action="store_true", help="ignore what earlier conversations taught us")
        p.add_argument("--force", action="store_true", help="haggle even if her best price ever is beyond our limit")
        p.add_argument("--margin", type=float, default=0.1, help="share of an item's value we keep as profit when buying")
        if name != "abuela":
            p.add_argument("--open", type=int, help="our first price")
            p.add_argument("--limit", type=int, help="most we pay (buy) / least we take (sell)")
        if name == "buy-card":
            p.add_argument("card")
        if name == "sell-spares":
            p.add_argument("--n", type=int, default=1)
        if name in ("buy-pack", "abuela"):
            p.add_argument("--keep", action="store_true", help="do not open the pack")
        if name == "abuela":
            p.add_argument("--packs", type=int, default=1)
            p.add_argument("--spares", type=int, default=2)
    args = ap.parse_args()
    if args.cmd == "abuela":
        args.n = args.spares
    b = connect()
    st = State(b)
    if args.cmd not in ("status", "learn"):
        learn.backfill(b)
    {"status": cmd_status, "learn": cmd_learn, "buy-pack": cmd_buy_pack, "buy-card": cmd_buy_card,
     "sell-spares": cmd_sell_spares, "abuela": cmd_abuela}[args.cmd](b, st, args)


if __name__ == "__main__":
    main()
