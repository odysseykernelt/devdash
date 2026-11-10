# 主仪表盘：总览 / GitHub 热榜 / 速查手册 / 设置
import html as html_mod
from datetime import datetime

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPropertyAnimation,
                            Qt, QUrl)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from . import cheats, riddles, storage
from .theme import palette, qss
from .workers import RepoScanWorker, TrendingWorker, WorkerHost

WEATHER_TEXT = {"sun": "晴", "cloud": "多云", "rain": "雨"}


def _fmt_ts(ts):
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def _int(value, default=0):
    """缓存里被手改成非整数时回落默认值，避免格式化/比较抛异常"""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _weather_key(repo: dict) -> str:
    key = repo.get("weather")
    return key if key in WEATHER_TEXT else "cloud"


class ClickableCard(QFrame):
    """整卡可点击；is_local=True 时按本地路径打开，其余只放行 http(s)"""
    def __init__(self, url: str, is_local: bool = False):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("clickable", True)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self._url = url
        self._is_local = is_local
        self.setToolTip(url)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._url:
            if self._is_local:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self._url))
            else:
                target = QUrl(self._url)
                if target.scheme() in ("http", "https"):
                    QDesktopServices.openUrl(target)
        super().mousePressEvent(event)


class DashboardWindow(QMainWindow, WorkerHost):
    def __init__(self, payload: dict):
        super().__init__()
        self.setWindowTitle("DevDash 仪表盘")
        self.resize(1080, 660)

        self._settings = payload["settings"]
        self._pal = palette(self._settings.get("theme"))
        self._repos = payload.get("repos", [])
        self._trending = payload.get("trending", [])
        self._riddle = payload.get("riddle", {})
        self._progress = payload.get("progress", {"history": []})
        self._cheat_rows = payload.get("cheat_rows", [])
        self._today = payload.get("today")
        self._workers = []
        self._anims = []
        self._reduce = bool(self._settings.get("reduceMotion"))
        self._pending = 0

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶栏
        top = QFrame()
        top.setObjectName("card")
        top.setStyleSheet("border-radius: 0; border-left: none; border-right: none; border-top: none;")
        th = QHBoxLayout(top)
        th.setContentsMargins(16, 10, 16, 10)
        title = QLabel("DevDash")
        title.setObjectName("title")
        title.setStyleSheet(f"color:{self._pal['accent']}")
        th.addWidget(title)
        sub = QLabel("开发者实用仪表盘")
        sub.setObjectName("muted")
        th.addWidget(sub)
        th.addStretch(1)
        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.clicked.connect(self._refresh_all)
        th.addWidget(self.refresh_btn)
        root.addWidget(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        # 左导航
        self.nav = QListWidget()
        self.nav.setFixedWidth(150)
        for name in ["总览", "GitHub 热榜", "速查手册", "设置"]:
            QListWidgetItem(name, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._switch)
        body.addWidget(self.nav)

        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)

        self.page_overview = QWidget()
        self.page_trending = QWidget()
        self.page_cheats = QWidget()
        self.page_settings = QWidget()
        for w in (self.page_overview, self.page_trending, self.page_cheats, self.page_settings):
            self.pages.addWidget(w)

        self._build_overview()
        self._build_trending()
        self._build_cheats()
        self._build_settings()

        self.setCentralWidget(central)

    # ---------- 通用 ----------
    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("card")
        f.setAttribute(Qt.WA_Hover)
        return f

    def _keep(self, anim):
        self._anims.append(anim)
        anim.finished.connect(lambda: self._anims.remove(anim) if anim in self._anims else None)
        anim.start(QAbstractAnimation.DeleteWhenStopped)

    def _scroll(self, inner: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(inner)
        return sa

    def _switch(self, row: int):
        w = self.pages.widget(row)
        self.pages.setCurrentIndex(row)
        if self._reduce or w is None:
            return
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._keep(anim)

    # ---------- 总览 ----------
    def _build_overview(self):
        lay = QVBoxLayout(self.page_overview)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # 统计条
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_repo = self._stat_card("本地仓库", str(len(self._repos)), self._pal["info"])
        w = {"sun": 0, "cloud": 0, "rain": 0}
        for r in self._repos:
            w[_weather_key(r)] += 1
        self.stat_weather = self._stat_card(
            "天气分布", f"晴 {w['sun']} · 多云 {w['cloud']} · 雨 {w['rain']}", self._pal["ok"])
        self.stat_streak = self._stat_card(
            "谜题连对", f"{storage.streak(self._progress, self._today)} 天", self._pal["accent"])
        cache = storage.load_trending_cache()
        self.stat_trend = self._stat_card("热榜更新", cache.get("fetchedAt") or "—", self._pal["warn"])
        for c in (self.stat_repo, self.stat_weather, self.stat_streak, self.stat_trend):
            stats.addWidget(c, 1)
        lay.addLayout(stats)

        # 谜题卡
        rc = self._card()
        rl = QHBoxLayout(rc)
        rl.setContentsMargins(16, 12, 16, 12)
        rl.setSpacing(14)
        q = QLabel(f"今日谜面：{self._riddle.get('text', '')}")
        q.setObjectName("big")
        rl.addWidget(q, 1)
        rec = storage.today_record(self._progress, self._today)
        state = QLabel("已答对" if rec and rec.get("solved") else "未作答")
        state.setStyleSheet(
            f"color:{self._pal['ok'] if rec and rec.get('solved') else self._pal['muted']}")
        rl.addWidget(state)
        glyphs = storage.recent_glyphs(self._progress, 7)
        gl = QLabel("  ".join(glyphs) if glyphs else "· · ·")
        gl.setObjectName("mono")
        gl.setStyleSheet(f"color:{self._pal['info']}; font-size:15px;")
        rl.addWidget(gl)
        lay.addWidget(rc)

        # 仓库卡列表
        inner = QWidget()
        self.repo_list_lay = QVBoxLayout(inner)
        self.repo_list_lay.setContentsMargins(0, 0, 0, 0)
        self.repo_list_lay.setSpacing(10)
        self._fill_repo_cards()
        lay.addWidget(self._scroll(inner), 1)

    def _stat_card(self, label: str, value: str, color: str) -> QFrame:
        c = self._card()
        v = QVBoxLayout(c)
        v.setContentsMargins(14, 10, 14, 10)
        lab = QLabel(label)
        lab.setObjectName("muted")
        val = QLabel(value)
        val.setStyleSheet(f"color:{color}; font-size:16px; font-weight:700;")
        v.addWidget(lab)
        v.addWidget(val)
        c.value_label = val
        return c

    def _fill_repo_cards(self):
        while self.repo_list_lay.count():
            item = self.repo_list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not self._repos:
            tip = QLabel("未发现 git 仓库。到「设置」添加仓库根目录后点「刷新数据」。")
            tip.setObjectName("muted")
            self.repo_list_lay.addWidget(tip)
            self.repo_list_lay.addStretch(1)
            return
        for r in self._repos:
            self.repo_list_lay.addWidget(self._repo_card(r))
        self.repo_list_lay.addStretch(1)

    def _repo_card(self, r: dict) -> QFrame:
        path = r.get("path", "")
        c = ClickableCard(path, is_local=True)
        c.setToolTip(f"点击打开：{path}")
        h = QHBoxLayout(c)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(12)

        wkey = _weather_key(r)
        wcolor = {"sun": self._pal["ok"], "cloud": self._pal["warn"], "rain": self._pal["err"]}[wkey]
        badge = QLabel(f"● {WEATHER_TEXT[wkey]}")
        badge.setStyleSheet(f"color:{wcolor}; font-weight:700;")
        badge.setFixedWidth(70)
        h.addWidget(badge)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(r.get("name", "?"))
        name.setObjectName("big")
        path = QLabel(r.get("path", ""))
        path.setObjectName("muted")
        info.addWidget(name)
        info.addWidget(path)
        h.addLayout(info, 1)

        def metric(txt, color=None):
            lab = QLabel(txt)
            lab.setObjectName("mono")
            if color:
                lab.setStyleSheet(f"color:{color}")
            h.addWidget(lab)

        uc = _int(r.get("uncommitted"), -1)
        metric(f"未提交 {uc}", self._pal["err"] if uc >= 10 else None)
        up = _int(r.get("unpushed"), None)
        metric(f"未推送 {up if up is not None else '—'}",
               self._pal["warn"] if up else None)
        d = r.get("daysSinceCommit")
        metric(f"最近提交 {_fmt_ts(_int(r.get('lastCommit'), None))}")
        metric(f"{d} 天前" if d is not None else "", self._pal["muted"])
        sb = _int(r.get("staleBranches"), 0)
        metric(f"滞留分支 {sb}", self._pal["warn"] if sb else None)
        return c

    # ---------- GitHub 热榜 ----------
    def _build_trending(self):
        lay = QVBoxLayout(self.page_trending)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        head = QLabel("GitHub 今日热榜（trending · daily）")
        head.setObjectName("big")
        lay.addWidget(head)

        inner = QWidget()
        self.trend_lay = QVBoxLayout(inner)
        self.trend_lay.setContentsMargins(0, 0, 0, 0)
        self.trend_lay.setSpacing(10)
        self._fill_trending()
        lay.addWidget(self._scroll(inner), 1)

    def _fill_trending(self):
        while self.trend_lay.count():
            item = self.trend_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not self._trending:
            tip = QLabel("暂无数据。检查网络后点「刷新数据」。")
            tip.setObjectName("muted")
            self.trend_lay.addWidget(tip)
            self.trend_lay.addStretch(1)
            return
        for i, it in enumerate(self._trending, 1):
            self.trend_lay.addWidget(self._trend_card(i, it))
        self.trend_lay.addStretch(1)

    def _trend_card(self, rank: int, it: dict) -> QFrame:
        url = str(it.get("url") or "")
        if not url.lower().startswith(("http://", "https://")):
            url = "#"
        c = ClickableCard(url)
        h = QHBoxLayout(c)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(12)

        no = QLabel(f"{rank:02d}")
        no.setObjectName("mono")
        no.setStyleSheet(f"color:{self._pal['muted']}; font-size:15px;")
        no.setFixedWidth(30)
        h.addWidget(no)

        mid = QVBoxLayout()
        mid.setSpacing(2)
        link = QLabel(f'<a href="{html_mod.escape(url, quote=True)}" '
                      f'style="color:{self._pal["info"]}; text-decoration:none; font-weight:700;">'
                      f'{html_mod.escape(str(it.get("repo") or ""))}</a>')
        link.setOpenExternalLinks(True)
        desc = QLabel(str(it.get("desc") or ""))
        desc.setTextFormat(Qt.PlainText)
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        mid.addWidget(link)
        mid.addWidget(desc)
        h.addLayout(mid, 1)

        if it.get("lang"):
            lang = QLabel(f"● {it['lang']}")
            lang.setStyleSheet(f"color:{self._pal['accent']}")
            h.addWidget(lang)
        star = QLabel(f"★ {_int(it.get('stars')):,}")
        star.setObjectName("mono")
        h.addWidget(star)
        today = QLabel(f"今日 +{_int(it.get('today')):,}")
        today.setObjectName("mono")
        today.setStyleSheet(f"color:{self._pal['ok']}; font-weight:700;")
        h.addWidget(today)
        return c

    # ---------- 速查手册 ----------
    def _build_cheats(self):
        lay = QVBoxLayout(self.page_cheats)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("检索速查…（Ctrl+K）")
        self.search_box.textChanged.connect(self._fill_cheats)
        lay.addWidget(self.search_box)

        inner = QWidget()
        self.cheat_lay = QVBoxLayout(inner)
        self.cheat_lay.setContentsMargins(0, 0, 0, 0)
        self.cheat_lay.setSpacing(6)
        self._fill_cheats()
        lay.addWidget(self._scroll(inner), 1)

    def _fill_cheats(self):
        kw = self.search_box.text() if hasattr(self, "search_box") else ""
        rows = cheats.search(self._cheat_rows, kw)
        while self.cheat_lay.count():
            item = self.cheat_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        last_group = None
        for r in rows:
            if r["group"] != last_group:
                g = QLabel(r["group"])
                g.setStyleSheet(f"color:{self._pal['accent']}; font-weight:700; margin-top:6px;")
                self.cheat_lay.addWidget(g)
                last_group = r["group"]
            row = QLabel(f"{r['title']}  —  {r['desc']}")
            row.setObjectName("mono")
            row.setWordWrap(True)
            row.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.cheat_lay.addWidget(row)
        if not rows:
            tip = QLabel("没有匹配条目")
            tip.setObjectName("muted")
            self.cheat_lay.addWidget(tip)
        self.cheat_lay.addStretch(1)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_K:
            self.nav.setCurrentRow(2)
            self.search_box.setFocus()
            self.search_box.selectAll()
            return
        super().keyPressEvent(event)

    # ---------- 设置 ----------
    def _build_settings(self):
        lay = QVBoxLayout(self.page_settings)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        lab = QLabel("仓库根目录（扫描两级以内的 .git）")
        lab.setObjectName("big")
        lay.addWidget(lab)

        self.roots_list = QListWidget()
        self.roots_list.addItems(self._settings.get("repoRoots", []))
        self.roots_list.setMaximumHeight(140)
        lay.addWidget(self.roots_list)

        row = QHBoxLayout()
        add = QPushButton("添加目录…")
        add.clicked.connect(self._add_root)
        rm = QPushButton("移除选中")
        rm.clicked.connect(self._remove_root)
        row.addWidget(add)
        row.addWidget(rm)
        row.addStretch(1)
        lay.addLayout(row)

        self.net_cb = QCheckBox("允许联网拉取 GitHub 热榜")
        self.net_cb.setChecked(self._settings.get("allowNetwork", True))
        lay.addWidget(self.net_cb)

        self.motion_cb = QCheckBox("减少动态效果")
        self.motion_cb.setChecked(self._settings.get("reduceMotion", False))
        lay.addWidget(self.motion_cb)

        trow = QHBoxLayout()
        tlab = QLabel("主题")
        trow.addWidget(tlab)
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(["dark", "light"])
        self.theme_cb.setCurrentText(self._settings.get("theme", "dark"))
        self.theme_cb.currentTextChanged.connect(self._apply_theme)
        trow.addWidget(self.theme_cb)
        trow.addStretch(1)
        lay.addLayout(trow)

        save = QPushButton("保存设置")
        save.setObjectName("primary")
        save.clicked.connect(self._save_settings)
        lay.addWidget(save)

        self.settings_msg = QLabel("")
        self.settings_msg.setObjectName("muted")
        lay.addWidget(self.settings_msg)
        lay.addStretch(1)

    def _add_root(self):
        d = QFileDialog.getExistingDirectory(self, "选择仓库根目录")
        if d:
            self.roots_list.addItem(d)

    def _remove_root(self):
        for item in self.roots_list.selectedItems():
            self.roots_list.takeItem(self.roots_list.row(item))

    def _apply_theme(self, name: str):
        self._pal = palette(name)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(qss(name))

    def _save_settings(self):
        roots = [self.roots_list.item(i).text() for i in range(self.roots_list.count())]
        self._settings.update({
            "repoRoots": roots,
            "allowNetwork": self.net_cb.isChecked(),
            "reduceMotion": self.motion_cb.isChecked(),
            "theme": self.theme_cb.currentText(),
        })
        storage.save_settings(self._settings)
        self.settings_msg.setText("已保存。部分改动在下次启动时完全生效。")

    # ---------- 刷新 ----------
    def _refresh_all(self):
        self._pending = 1 + int(bool(self._settings.get("allowNetwork", True)))
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("刷新中…")
        scan = RepoScanWorker(self._settings.get("repoRoots", []), self)
        self._track(scan)
        scan.done.connect(self._on_repos)
        scan.failed.connect(lambda e: self._settle())
        scan.start()
        if self._settings.get("allowNetwork", True):
            tw = TrendingWorker(self._settings.get("trendingLimit", 10), self)
            self._track(tw)
            tw.done.connect(self._on_trending)
            tw.failed.connect(lambda e: self._settle())
            tw.start()

    def _settle(self):
        self._pending -= 1
        if self._pending <= 0:
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("刷新数据")

    def _on_repos(self, repos: list):
        self._repos = repos
        storage.save_repo_cache(repos)
        self._fill_repo_cards()
        w = {"sun": 0, "cloud": 0, "rain": 0}
        for r in repos:
            w[_weather_key(r)] += 1
        self.stat_weather.value_label.setText(
            f"晴 {w['sun']} · 多云 {w['cloud']} · 雨 {w['rain']}")
        self.stat_repo.value_label.setText(str(len(repos)))
        self._settle()

    def _on_trending(self, items: list):
        self._trending = items
        storage.save_trending_cache(items)
        self._fill_trending()
        cache = storage.load_trending_cache()
        self.stat_trend.value_label.setText(cache.get("fetchedAt") or "—")
        self._settle()

    def closeEvent(self, event):
        self._stop_workers()
        super().closeEvent(event)
