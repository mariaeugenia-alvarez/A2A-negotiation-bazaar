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


def test_leg_text():
    assert dash.leg_text({"cash": 3, "assets": [{"ref": "LAV-02"}], "types": ["card:MAL-01"]}) == "3 P + LAV-02 + cualquier MAL-01"
    assert dash.leg_text({"cash": 0, "assets": [], "types": []}) == "nada"


def test_trader_view_joins_counters_and_outcomes():
    import json
    import tempfile
    from bz import log
    old = log.LOG_DIR
    with tempfile.TemporaryDirectory() as tmp:
        log.LOG_DIR = tmp
        def w(name, rows):
            open(os.path.join(tmp, name), "w").write("".join(json.dumps(r) + "\n" for r in rows))
        base = {"ts": 1, "offer": 1, "maker": "t05", "venue": "rastro", "got": 4, "lost": 0, "cash_in": 0, "cash_out": 9, "fee": 2, "margin": 2}
        w("trader.jsonl", [{**base, "tick": 1, "live": False, "action": "ignore", "surplus": -7},
                           {**base, "tick": 2, "live": True, "source": "board", "action": "accept", "surplus": 5},
                           {**base, "tick": 3, "live": True, "source": "to_us", "action": "counter", "surplus": -3, "venue": "v02"}])
        w("trader_counter.jsonl", [{"tick": 3, "incoming": 7, "counter": 8, "maker": "t05", "price": 2, "their": 8, "clearing": 2}])
        w("trader_outcome.jsonl", [{"incoming": 7, "counter": 8, "outcome": "accepted", "settled_price": 2}])
        try:
            v = dash.trader_view()
        finally:
            log.LOG_DIR = old
    assert v["total"] == 3 and v["mode"] == "live" and v["last_tick"] == 3
    assert v["counts"] == {"accept": 1, "counter": 1, "ignore": 1, "human": 0, "live": 2, "shadow": 1}
    assert v["decisions"][0]["source"] == "to_us", "rows from the first trader version had no source"
    assert v["counters"][0]["outcome"] == "accepted" and v["counter_outcomes"] == {"accepted": 1}
    assert {x["venue"]: x["decisions"] for x in v["by_venue"]} == {"rastro": 2, "v02": 1}


def test_trader_view_new_logs():
    import json
    import tempfile
    from bz import log
    old = log.LOG_DIR
    with tempfile.TemporaryDirectory() as tmp:
        log.LOG_DIR = tmp
        def w(name, rows):
            open(os.path.join(tmp, name), "w").write("".join(json.dumps(r) + "\n" for r in rows))
        base = {"offer": 1, "maker": "t05", "venue": "rastro", "live": True, "action": "accept", "tick": 5, "surplus": 5, "margin": 2}
        w("trader.jsonl", [base, {"offer": 2, "maker": "abuela", "venue": None, "live": True, "action": "human", "tick": 6, "why": "no numbers"}])
        w("trader_accept.jsonl", [{**base, "source": "board", "cash_before": 99}, {**base, "offer": 9, "source": "board"}])
        w("trader_settlement.jsonl", [{"offer": 1, "expected_cash": 9, "expected_fee": 2, "found": True, "price": 9, "fee": 2, "tick": 8}])
        w("trader_stale_bid.jsonl", [{"tick": 7, "offer": 70, "cards": ["MAL-07"], "cash": 17}, {"tick": 7, "offer": 71, "cards": ["SAL-08"], "cash": 20}])
        w("trader_cancel.jsonl", [{"tick": 8, "offer": 71, "cards": ["SAL-08"], "why": "stale bid"}])
        w("trader_counter.jsonl", [{"tick": 5, "incoming": 3, "counter": 4, "maker": "t05", "price": 2, "their": 6, "clearing": 2, "best_bid": 5}])
        try:
            v = dash.trader_view()
        finally:
            log.LOG_DIR = old
    acc = {a["offer"]: a for a in v["accepted_by_us"]}
    assert acc[1]["settlement"]["found"] and acc[1]["settlement"]["price"] == 9 and "cash_before" not in acc[1]
    assert acc[9]["settlement"] is None, "an accept the game has not confirmed yet"
    assert [(x["offer"], x["cancelled"]) for x in v["stale_bids"]] == [(70, False), (71, True)] and v["cancelled"] == 1
    assert v["counters"][0]["best_bid"] == 5
    assert v["counts"]["human"] == 1


def test_free_port_skips_a_busy_one():
    import socket
    import dashboard
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        taken = busy.getsockname()[1]
        assert dashboard.free_port(taken) != taken, "a second dashboard must not fight the first one for its port"


def test_journal_writes_a_line():
    import tempfile
    from bz import log
    import dashboard
    old_dir, old_path = log.LOG_DIR, dashboard.JOURNAL
    with tempfile.TemporaryDirectory() as tmp:
        log.LOG_DIR, dashboard.JOURNAL = tmp, os.path.join(tmp, "dashboard_server.log")
        try:
            dashboard.journal("stopped by SIGTERM")
            text = open(dashboard.JOURNAL).read()
        finally:
            log.LOG_DIR, dashboard.JOURNAL = old_dir, old_path
    assert "stopped by SIGTERM" in text and "pid" in text


def test_rev_ignores_build_time():
    import dashboard
    a = dashboard.stamp({"built": "10:00:00", "x": [1, 2]})
    b = dashboard.stamp({"built": "10:00:20", "x": [1, 2]})
    c = dashboard.stamp({"built": "10:00:20", "x": [1, 3]})
    assert a["rev"] == b["rev"] and a["rev"] != c["rev"], "the page must redraw only when the data changed"


def test_render_escapes_script_end():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import dashboard
    html = dashboard.render({"x": "</script><b>"})
    assert "</script><b>" not in html and "<\\/script>" in html




def test_duel_live_board_switch_and_next():
    def v(i, session, status, result=None, rounds=1, decisions=None):
        d = {"duel": i, "session": session, "status": status, "role": "buyer", "item": "x", "your_limit": 100,
             "deadline_tick": 50, "price": 80 if status == "deal" else None, "result": result, "rounds": rounds,
             "messages": [{"tick": 40, "from": "Rival", "price": 90}]}
        return dash.duel_view(d, decisions or [])
    old = [v(1, 2, "deal", 10.0), v(2, 2, "no_deal")]
    k = [{"tick": 40, "kind": "self", "why": "x"}]
    cur = [v(3, 3, "deal", 20.0, decisions=k), v(4, 3, "no_deal", decisions=k), v(5, 3, "no_deal", decisions=k),
           v(6, 3, "no_deal", decisions=k), v(7, 3, "no_deal", decisions=k), v(8, 3, "live", decisions=k)]
    up = [{"at_hours": 11.65, "action": "duels", "note": "Duels II", "params": {"name": "Duels II", "duel_ticks": 16}}]
    L = dash.duel_live(old + cur, {"tick": 45, "t_hours": 11.0}, up)
    assert L["session"] == 3 and L["prev_session"] == 2 and L["live"] == [8]
    assert L["board"]["done"] == 5 and L["board"]["deals"] == 1 and L["board"]["deal_rate"] == 0.2
    assert L["before"]["deals"] == 1 and L["switch"] == "trip" and L["v2"]
    assert L["next"]["minutes"] == 39
    assert cur[0]["start"] == 34  # deadline 50 - 16 ticks
    L2 = dash.duel_live(old, {"tick": 45, "t_hours": 11.0}, up)
    assert L2["switch"] is None  # an old session without the waiting play has no switch


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
