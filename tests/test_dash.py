"""bz/dash: the pure parts of the dashboard data. python3 tests/test_dash.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz import dash  # noqa: E402

PACK = {"give": {"cash": 0, "assets": [], "types": ["pack:sobre_barrio"]}}


def offer(maker, cash=None, final=False, dealer_sells=True):
    leg_cash = {"cash": cash or 0, "assets": [], "types": []}
    if dealer_sells:
        o = {"maker": maker, "give": PACK["give"], "want": leg_cash} if maker == "abuela" else \
            {"maker": maker, "give": leg_cash, "want": {"cash": 0, "assets": [], "types": ["pack:sobre_barrio"]}}
    o["final"], o["status"], o["id"] = final, "open", 1
    return o


def msg(tick, sender, cash, text=None, final=False):
    return {"id": tick * 10, "tick": tick, "sender": sender, "text": text, "offer": offer(sender, cash, final)}


def thread(i, team, prices, deal=None):
    """prices: [(who, price)] who = 'abuela' or the team."""
    return {"id": i, "team": team, "with": "abuela", "kind": "persona", "status": "open", "topic": {"buy": {"pack": "sobre_barrio"}},
            "messages": [msg(10 + k, "abuela" if w == "abuela" else team, p, "hola" if w == "abuela" else None, final=(k == len(prices) - 1 and deal is not None))
                         for k, (w, p) in enumerate(prices)]}


def test_rows_and_steps():
    t = thread(1, "t09", [("abuela", 30), ("t09", 15), ("abuela", 26), ("t09", 17)])
    rows = dash.rows_of(t, "t09")
    assert [r["who"] for r in rows] == ["dealer", "us", "dealer", "us"]
    assert rows[2]["step"] == -4 and rows[3]["step"] == 2 and rows[0]["step"] is None
    assert rows[0]["text"] == "hola"


def test_finish_uses_settlement_price():
    t = thread(2, "t12", [("abuela", 30), ("t12", 15), ("abuela", 25)])
    r = dash.finish(t, "t09", {}, {}, deal_price=21, source="feed")
    assert r["deal"] == 21 and r["best"] == 21 and r["status"] == "deal" and r["kind"] == "buy:pack:sobre_barrio"
    assert r["hers"] == [30, 25] and r["ours"] == [15]


def test_infer_topic_from_offers():
    t = thread(3, "t13", [("abuela", 30), ("t13", 15)])
    assert dash.infer_topic(t) == {"buy": {"pack": "sobre_barrio"}}


def test_feed_threads_skips_us_and_matches_settlement():
    def ev(i, tick, typ, payload):
        return {"id": i, "tick": tick, "type": typ, "payload": payload}
    ours = thread(10, "t09", [("abuela", 30), ("t09", 15)])
    theirs = thread(11, "t12", [("abuela", 30), ("t12", 15), ("abuela", 24)])
    events = [ev(1, 10, "thread.opened", {"thread": 11, "kind": "persona", "team": "t12", "with": "abuela", "topic": {"buy": {"pack": "sobre_barrio"}}})]
    for t in (ours, theirs):
        for m in t["messages"]:
            events.append(ev(100 + m["id"] + t["id"], m["tick"], "thread.message",
                             {"thread": t["id"], "kind": "persona", "message": m["id"], "sender": m["sender"], "text": m["text"],
                              "team": t["team"], "with": "abuela", "offer": m["offer"]}))
    events.append(ev(999, 13, "settlement", {"settlement": 7, "tick": 13, "persona": "abuela", "parties": ["abuela", "t12"], "price": 22, "items": []}))
    out = dash.feed_threads(events, "t09", {}, {})
    assert [t["id"] for t in out] == [11], "our own thread must not show up as somebody else's"
    assert out[0]["deal"] == 22 and out[0]["status"] == "deal" and out[0]["source"] == "feed"


def test_fit_and_summary():
    assert dash.fit([(1, 2)]) == {}
    f = dash.fit([(1, 10), (2, 8), (3, 6), (4, 4)])
    assert f["b"] == -2.0 and f["a"] == 12.0 and f["r"] == -1.0
    ts = [dash.finish(thread(i, "t09" if i == 20 else "t12", [("abuela", 30), ("t09" if i == 20 else "t12", 15), ("abuela", 30 - d)], 0), "t09", {}, {},
                      deal_price=30 - d, source="ours" if i == 20 else "feed") for i, d in ((20, 4), (21, 6), (22, 8))]
    s = dash.summarize(ts)["abuela"]["buy:pack:sobre_barrio"]
    assert s["threads"] == 3 and s["ours"] == 1 and s["deal_best"] == 22 and s["deal_median"] == 24
    assert s["fit"]["n"] == 3 and s["fit"]["r"] == -1.0


def test_duels():
    d = {"duel": 1, "session": 1, "status": "deal", "role": "buyer", "item": "Taxi", "issues": ["price"], "your_limit": 129, "rival": "Azul",
         "decay_per_round": 0.06, "rounds": 3, "price": 103, "result": 21.6, "deadline_tick": 132,
         "messages": [{"tick": 1, "from": "Azul", "text": "a", "price": 129}, {"tick": 2, "from": "you", "text": "b", "price": 73}]}
    v = dash.duel_view(d, [])
    assert v["rival_open_share"] == 1.0 and v["our_open_share"] == 0.57 and v["result_share"] == 0.167
    s = dash.duel_summary([v])
    assert s[0]["role"] == "buyer" and s[0]["deal_rate"] == 1.0 and s[0]["mean_share"] == 0.167


def test_render_escapes_script_end():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import dashboard
    html = dashboard.render({"x": "</script><b>"})
    assert "</script><b>" not in html and "<\\/script>" in html


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
