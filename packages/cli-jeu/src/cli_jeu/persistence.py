from __future__ import annotations
import json
import pickle
import datetime
from pathlib import Path
from typing import Any

BASE = Path(".avpol")
BASE.mkdir(exist_ok=True)
SESSION = BASE / "session.pkl"
JOURNAL = BASE / "journal.jsonl"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save_engine(engine: Any) -> None:
    with SESSION.open("wb") as f:
        pickle.dump(engine, f)


def load_engine() -> Any | None:
    if not SESSION.exists():
        return None
    with SESSION.open("rb") as f:
        return pickle.load(f)


def append_event(evt: dict) -> None:
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
