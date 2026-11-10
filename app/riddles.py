# 谜题：按日期轮换，答案限一个汉字
from datetime import date

from . import storage


def load_riddles() -> list:
    raw = storage.load_json("riddles.json", [], list)
    return [
        r for r in raw
        if isinstance(r, dict)
        and isinstance(r.get("text"), str) and r["text"].strip()
        and str(r.get("answer") or "").strip()
    ]


def today_riddle(riddles: list, today: date) -> dict:
    if not riddles:
        return {"id": "none", "text": "题库为空", "answer": "?", "hint": "检查 data/riddles.json"}
    idx = (today.toordinal()) % len(riddles)
    return riddles[idx]


def check(user_input: str, riddle: dict) -> bool:
    if riddle.get("id") == "none":  # 题库为空时的兜底题不参与判定
        return False
    return user_input.strip() == str(riddle.get("answer", "")).strip()
