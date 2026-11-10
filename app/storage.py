# 本地 JSON 存储：配置 / 缓存 / 谜题进度
import json
import os
from datetime import date, datetime

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

DEFAULT_SETTINGS = {
    "repoRoots": [],
    "theme": "dark",
    "allowNetwork": True,
    "reduceMotion": False,
    "trendingLimit": 10,
}


def _path(name: str) -> str:
    return os.path.join(BASE_DIR, name)


def _backup_bad(p: str) -> None:
    """把无法解析或结构不符的文件留档为 .bad，避免下次启动继续踩同一个坑"""
    try:
        os.replace(p, p + ".bad")
    except OSError:
        pass


def load_json(name: str, default, expect=None):
    """读取 JSON：解析失败或顶层类型与 expect 不符时备份为 .bad 并回落到默认值"""
    p = _path(name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        _backup_bad(p)
        return default
    if expect is not None and not isinstance(data, expect):
        _backup_bad(p)
        return default
    return data


def save_json(name: str, data) -> None:
    os.makedirs(BASE_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(name))


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    raw = load_json("settings.json", {}, dict)
    roots = raw.get("repoRoots")
    if isinstance(roots, list):
        s["repoRoots"] = [r for r in roots if isinstance(r, str) and r.strip()]
    if raw.get("theme") in ("dark", "light"):
        s["theme"] = raw["theme"]
    for key in ("allowNetwork", "reduceMotion"):
        if isinstance(raw.get(key), bool):
            s[key] = raw[key]
    limit = raw.get("trendingLimit")
    if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= 50:
        s["trendingLimit"] = limit
    return s


def save_settings(settings: dict) -> None:
    save_json("settings.json", settings)


# ---- 谜题进度 ----
# riddle_progress.json: {"history": [{"date": "2026-10-30", "answer": "明", "solved": true}]}

def load_progress() -> dict:
    raw = load_json("riddle_progress.json", {}, dict)
    hist = raw.get("history")
    history = []
    if isinstance(hist, list):
        history = [h for h in hist if isinstance(h, dict) and isinstance(h.get("date"), str)]
    return {"history": history}


def record_answer(today: date, answer: str, solved: bool) -> dict:
    p = load_progress()
    key = today.isoformat()
    p["history"] = [h for h in p["history"] if h.get("date") != key]
    p["history"].append({"date": key, "answer": answer, "solved": solved})
    p["history"] = p["history"][-60:]
    save_json("riddle_progress.json", p)
    return p


def today_record(progress: dict, today: date):
    key = today.isoformat()
    for h in progress.get("history", []):
        if h.get("date") == key:
            return h
    return None


def recent_glyphs(progress: dict, n: int = 7) -> list:
    solved = [h for h in progress.get("history", []) if h.get("solved")]
    return [h.get("answer", "") for h in solved[-n:]]


def streak(progress: dict, today: date) -> int:
    days = {h.get("date") for h in progress.get("history", []) if h.get("solved")}
    count = 0
    d = today.toordinal()
    while date.fromordinal(d).isoformat() in days:
        count += 1
        d -= 1
    return count


# ---- 缓存 ----

def load_trending_cache():
    raw = load_json("github_cache.json", {}, dict)
    items = raw.get("items")
    items = [it for it in items if isinstance(it, dict)] if isinstance(items, list) else []
    fetched = raw.get("fetchedAt")
    return {"fetchedAt": fetched if isinstance(fetched, str) else None, "items": items}


def save_trending_cache(items: list) -> None:
    save_json("github_cache.json", {
        "fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    })


def load_repo_cache():
    raw = load_json("repo_cache.json", {}, dict)
    repos = raw.get("repos")
    repos = [r for r in repos if isinstance(r, dict)] if isinstance(repos, list) else []
    scanned = raw.get("scannedAt")
    return {"scannedAt": scanned if isinstance(scanned, str) else None, "repos": repos}


def save_repo_cache(repos: list) -> None:
    save_json("repo_cache.json", {
        "scannedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repos": repos,
    })
