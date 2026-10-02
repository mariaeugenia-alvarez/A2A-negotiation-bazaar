"""Append-only JSONL logs under logs/: one line per event, so every haggle can be replayed and tuned later."""
import json
import os
import time

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def event(stream: str, **fields) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, f"{stream}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), **fields}, ensure_ascii=False) + "\n")


def say(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)
