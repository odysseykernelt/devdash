# GitHub 今日热榜：trending 页面优先，Search API 后备
import html as html_mod
import json
import re
from datetime import datetime, timezone

import requests

URL = "https://github.com/trending?since=daily"
SEARCH_URL = "https://api.github.com/search/repositories"
TIMEOUT = (3, 3)  # 连接/读取上限：兼顾慢网与关闭窗口时的收敛速度
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "application/vnd.github+json",
}


class _Cancelled(Exception):
    """窗口关闭导致的中断，不属于拉取失败"""


def _get(url: str, should_stop, **kwargs) -> str:
    """分块读取：取消时立刻关连接，避免关闭窗口卡在网络等待上"""
    resp = requests.get(url, timeout=TIMEOUT, stream=True, **kwargs)
    try:
        resp.raise_for_status()
        chunks = []
        for chunk in resp.iter_content(16384):
            if should_stop is not None and should_stop():
                raise _Cancelled
            chunks.append(chunk)
        return b"".join(chunks).decode(resp.encoding or "utf-8", "replace")
    finally:
        resp.close()


def fetch_trending(limit: int = 10, should_stop=None) -> list:
    try:
        items = parse(_get(URL, should_stop, headers=UA))
        if items:
            return items[:limit]
    except _Cancelled:
        raise
    except (requests.RequestException, ValueError):
        pass
    return _from_search_api(limit, should_stop)


def _from_search_api(limit: int, should_stop=None) -> list:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    params = {
        "q": f"created:>={today}",
        "sort": "stars",
        "order": "desc",
        "per_page": str(limit),
    }
    text = _get(SEARCH_URL, should_stop, headers=UA, params=params)
    items = []
    for it in json.loads(text).get("items", []):
        stars = it.get("stargazers_count", 0)
        items.append({
            "repo": it.get("full_name", ""),
            "url": it.get("html_url", ""),
            "desc": _clean(it.get("description") or ""),
            "lang": it.get("language") or "",
            "stars": stars,
            "forks": it.get("forks_count", 0),
            "today": stars,  # 当天新建仓库的 star 即当日所得
        })
    return items


def _clean(s: str) -> str:
    # 先还原实体再剥标签：反序会把 &lt;a href=...&gt; 还原成可被 QLabel 解析的富文本标记
    return re.sub(r"<[^>]+>", "", html_mod.unescape(s)).strip()


def _num(s: str) -> int:
    return int(s.replace(",", "").strip() or 0)


def parse(text: str) -> list:
    blocks = re.findall(r'<article class="Box-row">(.*?)</article>', text, re.S)
    items = []
    for b in blocks:
        m = re.search(r'<h2[^>]*>.*?<a[^>]*href="/([^"/]+/[^"/]+)"', b, re.S)
        if not m:
            continue
        repo = m.group(1).strip().strip("/")

        desc_m = re.search(r'<p class="col-9[^"]*">(.*?)</p>', b, re.S)
        desc = _clean(desc_m.group(1)) if desc_m else ""

        lang_m = re.search(r'itemprop="programmingLanguage">(.*?)</span>', b)
        lang = _clean(lang_m.group(1)) if lang_m else ""

        stars_m = re.search(r'href="/[^"]+/stargazers"[^>]*>.*?</svg>\s*([\d,]+)', b, re.S)
        stars = _num(stars_m.group(1)) if stars_m else 0

        forks_m = re.search(r'href="/[^"]+/forks"[^>]*>.*?</svg>\s*([\d,]+)', b, re.S)
        forks = _num(forks_m.group(1)) if forks_m else 0

        today_m = re.search(r'([\d,]+)\s*stars\s*today', b, re.I)
        today = _num(today_m.group(1)) if today_m else 0

        items.append({
            "repo": repo,
            "url": f"https://github.com/{repo}",
            "desc": desc,
            "lang": lang,
            "stars": stars,
            "forks": forks,
            "today": today,
        })
    return items
