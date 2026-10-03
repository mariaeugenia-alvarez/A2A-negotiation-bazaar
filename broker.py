"""Our broker: crosses exactly as the free stall does (starter_broker's plans), and records the book every time it changes,
so the Market Test's traders (quotes over time, who relaxes, who leaves) can be studied before we try to beat the stall.

    python3 broker.py            # BROKER_KEY from the environment or .env; logs/bench/book.jsonl gets one line per new book

Run it for the whole game on our board venue. On an 'auto' venue (the free stall) the engine crosses before a broker reads.
"""
import json
import os
import time

from agent import load_env
from bazaar_sdk import BazaarError, Broker
from starter_broker import bench_plan, public_plan

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_LOG = os.path.join(HERE, "logs", "bench", "book.jsonl")


def record(tick: int, book: dict, path: str = BOOK_LOG) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "tick": tick, "bench_offers": book.get("bench_offers") or [],
                            "offers": book.get("offers") or [], "settlements": book.get("settlements") or []}) + "\n")


def main() -> None:
    load_env()
    broker = Broker(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BROKER_KEY"])
    seen = None
    while True:  # two reads a second, as the starter broker: a new tick or a new offer is seen within 1 s
        try:
            tick, book = broker.clock()["tick"], broker.book()
            now = (tick, [o["id"] for o in (book.get("bench_offers") or []) + (book.get("offers") or [])])
            if now != seen:  # plan once per state of the book, so a refused match is not retried every second
                seen = now
                record(tick, book)
                for sell, buy, price in bench_plan(book) + public_plan(book):
                    try:
                        broker.match(sell, buy, price)
                    except BazaarError as e:  # taken since the read, a shape the venue cannot cross, ...
                        print(f"tick {tick}: {sell} x {buy} at {price} refused ({e})", flush=True)
        except BazaarError as e:  # the server restarting, say: keep going, on a board venue nothing matches without us
            print(f"cannot read the book ({e}), trying again", flush=True)
        time.sleep(1.0)


if __name__ == "__main__":
    main()
