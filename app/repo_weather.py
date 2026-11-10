# 本地仓库扫描：未提交 / 未推送 / 最近提交 / 分支滞留 → 晴 / 多云 / 雨
import os
import subprocess
import time

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
STALE_DAYS = 14


def _git(path: str, *args: str, timeout: int = 10, should_stop=None) -> tuple:
    """执行 git；should_stop 为真时立即杀掉子进程，保证窗口关闭能快速收敛"""
    try:
        proc = subprocess.Popen(
            ["git", "-C", path, *args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError:
        return -1, ""
    deadline = time.time() + timeout
    while True:
        try:
            out, _ = proc.communicate(timeout=0.05)
            return proc.returncode, (out or "").strip()
        except subprocess.TimeoutExpired:
            if (should_stop is not None and should_stop()) or time.time() > deadline:
                proc.kill()
                proc.communicate()
                return -1, ""


def find_repos(roots: list, max_depth: int = 2, should_stop=None) -> list:
    repos = []
    seen = set()
    for root in roots:
        if should_stop is not None and should_stop():
            break
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        visited = 0
        for dirpath, dirnames, _ in os.walk(root):
            if should_stop is not None and should_stop():
                dirnames[:] = []
                break
            visited += 1
            if visited > 5000:  # 大盘根目录护栏：防长时间枚举
                dirnames[:] = []
                continue
            depth = dirpath.count(os.sep) - base_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            if ".git" in dirnames:
                real = os.path.normcase(dirpath)
                if real not in seen:
                    seen.add(real)
                    repos.append(dirpath)
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if not d.startswith(".")
                           and d not in ("node_modules", "__pycache__", "dist", "build")]
    return repos


def repo_info(path: str, should_stop=None) -> dict:
    code, out = _git(path, "status", "--porcelain", should_stop=should_stop)
    uncommitted = len([ln for ln in out.splitlines() if ln.strip()]) if code == 0 else -1

    code, out = _git(path, "log", "-1", "--format=%ct", should_stop=should_stop)
    last_ts = int(out) if code == 0 and out.isdigit() else None

    code, out = _git(path, "rev-list", "--count", "@{u}..HEAD", should_stop=should_stop)
    unpushed = int(out) if code == 0 and out.isdigit() else None

    code, out = _git(path, "branch", "--show-current", should_stop=should_stop)
    current = out if code == 0 else ""

    code, out = _git(path, "for-each-ref", "--format=%(refname:short) %(committerdate:unix)",
                     "refs/heads", should_stop=should_stop)
    now = time.time()
    stale = 0
    branch_count = 0
    if code == 0 and out:
        for ln in out.splitlines():
            parts = ln.rsplit(" ", 1)
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            branch_count += 1
            name, ts = parts
            if name == current:
                continue
            if now - int(ts) > STALE_DAYS * 86400:
                stale += 1

    days_since = None if last_ts is None else (now - last_ts) / 86400.0

    score = 0
    if uncommitted > 0:
        score += 1
    if uncommitted >= 10:
        score += 2
    if unpushed:
        score += 1
    if days_since is not None and days_since > STALE_DAYS:
        score += 1
    if days_since is not None and days_since > 30:
        score += 2
    if stale >= 3:
        score += 1

    weather = "sun" if score == 0 else ("cloud" if score <= 2 else "rain")
    return {
        "path": path,
        "name": os.path.basename(path),
        "uncommitted": uncommitted,
        "unpushed": unpushed,
        "lastCommit": last_ts,
        "daysSinceCommit": round(days_since, 1) if days_since is not None else None,
        "branchCount": branch_count,
        "staleBranches": stale,
        "weather": weather,
    }


def scan(roots: list, should_stop=None) -> list:
    """扫描仓库；should_stop 返回真时尽快返回已收集结果，供窗口关闭时中断"""
    out = []
    for p in find_repos(roots, should_stop=should_stop):
        if should_stop is not None and should_stop():
            break
        out.append(repo_info(p, should_stop=should_stop))
    return out
