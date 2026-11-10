# 速查手册：本地分组条目，支持关键词过滤
from . import storage


def load_cheats() -> list:
    raw = storage.load_json("cheats.json", [], list)
    return [
        g for g in raw
        if isinstance(g, dict) and isinstance(g.get("items"), list)
    ]


def flatten(cheats: list) -> list:
    rows = []
    for group in cheats:
        gname = group.get("group")
        gname = gname if isinstance(gname, str) else ""
        for item in group.get("items", []):
            if not isinstance(item, dict):
                continue
            rows.append({
                "group": gname,
                "title": str(item.get("t") or ""),
                "desc": str(item.get("d") or ""),
            })
    return rows


def search(rows: list, keyword: str) -> list:
    kw = keyword.strip().lower()
    if not kw:
        return rows
    return [r for r in rows if kw in (r["group"] + " " + r["title"] + " " + r["desc"]).lower()]


def ticker_lines(rows: list, limit: int = 12) -> list:
    return [f"[{r['group']}] {r['title']} — {r['desc']}" for r in rows[:limit]]
