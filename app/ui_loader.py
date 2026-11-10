# 启动加载页：一句谜 + 阶段进度 + 速查轮播
from datetime import date, datetime

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPropertyAnimation,
                            Qt, QTimer)
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QLineEdit, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from . import cheats, riddles, storage
from .theme import palette
from .workers import RepoScanWorker, TrendingWorker, WorkerHost

STAGES = ["读配置", "扫仓库", "载入手册", "GitHub 热榜", "准备界面"]


class LoaderWindow(QWidget, WorkerHost):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DevDash · 一句谜")
        self.resize(880, 470)

        self._today = date.today()
        self._settings = storage.load_settings()
        self._pal = palette(self._settings.get("theme"))
        self._progress = storage.load_progress()
        self._riddle = riddles.today_riddle(riddles.load_riddles(), self._today)
        self._cheat_rows = cheats.flatten(cheats.load_cheats())
        self._repos = []
        self._trending = storage.load_trending_cache().get("items", [])
        self._stage_state = ["wait"] * len(STAGES)
        self._workers = []
        self._ticker_idx = 0
        self._opened = False
        self._closing = False
        self._anims = []
        self._reduce = bool(self._settings.get("reduceMotion"))

        self._build_ui()
        self._refresh_glyphs()
        QTimer.singleShot(60, self._run_stages)

    # ---------- UI ----------
    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("card")
        f.setAttribute(Qt.WA_Hover)
        return f

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(12)

        mid = QHBoxLayout()
        mid.setSpacing(12)
        root.addLayout(mid, 1)

        # 左：谜题卡
        left = self._card()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(18, 16, 18, 16)
        lv.setSpacing(10)

        head = QHBoxLayout()
        name = QLabel("DevDash · 一句谜")
        name.setObjectName("title")
        name.setStyleSheet(f"color:{self._pal['accent']}")
        day = QLabel(self._today.strftime("%Y-%m-%d %A"))
        day.setObjectName("muted")
        head.addWidget(name)
        head.addStretch(1)
        head.addWidget(day)
        lv.addLayout(head)

        lv.addSpacing(6)
        self.riddle_label = QLabel(f"今日谜面：{self._riddle.get('text', '')}")
        self.riddle_label.setObjectName("big")
        self.riddle_label.setWordWrap(True)
        lv.addWidget(self.riddle_label)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setObjectName("mono")
        self.input.setMaxLength(1)
        self.input.setPlaceholderText("一个汉字")
        self.input.setFixedWidth(90)
        self.input.returnPressed.connect(self._submit)
        submit = QPushButton("猜")
        submit.setObjectName("primary")
        submit.clicked.connect(self._submit)
        hint_btn = QPushButton("提示")
        hint_btn.clicked.connect(self._show_hint)
        skip_btn = QPushButton("跳过")
        skip_btn.clicked.connect(self._skip)
        row.addWidget(self.input)
        row.addWidget(submit)
        row.addWidget(hint_btn)
        row.addWidget(skip_btn)
        row.addStretch(1)
        lv.addLayout(row)

        self.msg = QLabel("")
        self.msg.setObjectName("muted")
        self._msg_eff = QGraphicsOpacityEffect(self.msg)
        self.msg.setGraphicsEffect(self._msg_eff)
        lv.addWidget(self.msg)

        lv.addSpacing(4)
        glyph_row = QHBoxLayout()
        glyph_row.setSpacing(6)
        cap = QLabel("近七日集字")
        cap.setObjectName("muted")
        glyph_row.addWidget(cap)
        self.glyph_boxes = []
        for _ in range(7):
            box = QLabel("")
            box.setAlignment(Qt.AlignCenter)
            box.setFixedSize(30, 30)
            box.setStyleSheet(
                f"border:1px solid {self._pal['border2']}; border-radius:6px;"
                f"color:{self._pal['muted']}; background:{self._pal['panel2']};")
            glyph_row.addWidget(box)
            self.glyph_boxes.append(box)
        glyph_row.addStretch(1)
        lv.addLayout(glyph_row)
        lv.addStretch(1)
        mid.addWidget(left, 3)

        # 右：阶段卡
        right = self._card()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(18, 16, 18, 16)
        rv.setSpacing(8)

        t = QLabel("正在准备")
        t.setObjectName("big")
        rv.addWidget(t)

        self.stage_labels = []
        for s in STAGES:
            lab = QLabel(f"○  {s}")
            lab.setObjectName("muted")
            rv.addWidget(lab)
            self.stage_labels.append(lab)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        rv.addWidget(self.bar)

        self.stage_msg = QLabel("")
        self.stage_msg.setObjectName("muted")
        self.stage_msg.setWordWrap(True)
        rv.addWidget(self.stage_msg)

        rv.addStretch(1)
        self.enter_btn = QPushButton("进入仪表盘")
        self.enter_btn.setObjectName("primary")
        self.enter_btn.setEnabled(False)
        self.enter_btn.clicked.connect(self._enter)
        rv.addWidget(self.enter_btn)
        mid.addWidget(right, 2)

        # 底部速查轮播
        self.ticker = QLabel("")
        self.ticker.setObjectName("muted")
        root.addWidget(self.ticker)
        self._tick()
        self._ticker_timer = QTimer(self)
        self._ticker_timer.timeout.connect(self._tick)
        self._ticker_timer.start(2600)

    def _tick(self):
        lines = cheats.ticker_lines(self._cheat_rows)
        if not lines:
            return
        text = f"速查  {lines[self._ticker_idx % len(lines)]}"
        self._ticker_idx += 1
        if self._reduce:
            self.ticker.setText(text)
            return
        eff = QGraphicsOpacityEffect(self.ticker)
        self.ticker.setGraphicsEffect(eff)
        fade_in = QPropertyAnimation(eff, b"opacity", self)
        fade_in.setDuration(420)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.ticker.setText(text)
        self._keep(fade_in)

    # ---------- 动效工具 ----------
    def _keep(self, anim):
        """持引用并启动，防止动画被回收"""
        self._anims.append(anim)
        anim.finished.connect(lambda: self._anims.remove(anim) if anim in self._anims else None)
        anim.start(QAbstractAnimation.DeleteWhenStopped)

    def _flash_msg(self):
        if self._reduce:
            return
        anim = QPropertyAnimation(self._msg_eff, b"opacity", self)
        anim.setDuration(320)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        self._keep(anim)

    def _shake_input(self):
        if self._reduce:
            return
        anim = QPropertyAnimation(self.input, b"pos", self)
        pos = self.input.pos()
        anim.setDuration(280)
        anim.setKeyValueAt(0.0, pos)
        anim.setKeyValueAt(0.2, pos + self._dx(-7))
        anim.setKeyValueAt(0.4, pos + self._dx(6))
        anim.setKeyValueAt(0.6, pos + self._dx(-4))
        anim.setKeyValueAt(0.8, pos + self._dx(3))
        anim.setKeyValueAt(1.0, pos)
        self._keep(anim)

    def _dx(self, n):
        from PySide6.QtCore import QPoint
        return QPoint(n, 0)

    def _pop_glyph(self, box: QLabel):
        if self._reduce:
            return
        eff = QGraphicsOpacityEffect(box)
        box.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(480)
        anim.setKeyValueAt(0.0, 0.0)
        anim.setKeyValueAt(0.4, 1.0)
        anim.setKeyValueAt(0.7, 0.55)
        anim.setKeyValueAt(1.0, 1.0)
        anim.setEasingCurve(QEasingCurve.OutBack)
        self._keep(anim)

    def _animate_bar(self, target: int):
        if self._reduce:
            self.bar.setValue(target)
            return
        anim = QPropertyAnimation(self.bar, b"value", self)
        anim.setDuration(380)
        anim.setStartValue(self.bar.value())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._keep(anim)

    # ---------- 谜题 ----------
    def _refresh_glyphs(self, pop: bool = False):
        glyphs = storage.recent_glyphs(self._progress, 7)
        for i, box in enumerate(self.glyph_boxes):
            ch = glyphs[i] if i < len(glyphs) else ""
            box.setText(ch)
            if ch:
                box.setStyleSheet(
                    f"border:1px solid {self._pal['info']}; border-radius:6px;"
                    f"color:{self._pal['bg']}; background:{self._pal['info']};"
                    f"font-weight:700;")
        if pop and glyphs:
            self._pop_glyph(self.glyph_boxes[len(glyphs) - 1])

    def _submit(self):
        text = self.input.text().strip()
        if not text:
            return
        if riddles.check(text, self._riddle):
            self._progress = storage.record_answer(self._today, text, True)
            self._refresh_glyphs(pop=True)
            self.msg.setText("答对了，字已收入。")
            self.msg.setStyleSheet(f"color:{self._pal['ok']}")
            self.input.setDisabled(True)
        else:
            self.msg.setText("再想想，差一点都不算。")
            self.msg.setStyleSheet(f"color:{self._pal['err']}")
            self._shake_input()
        self.input.clear()
        self._flash_msg()

    def _show_hint(self):
        self.msg.setText(f"提示：{self._riddle.get('hint', '无')}")
        self.msg.setStyleSheet(f"color:{self._pal['warn']}")

    def _skip(self):
        self.msg.setText(f"答案：{self._riddle.get('answer', '?')}（明日再来）")
        self.msg.setStyleSheet(f"color:{self._pal['muted']}")

    # ---------- 阶段推进 ----------
    def _set_stage(self, idx: int, state: str, note: str = ""):
        self._stage_state[idx] = state
        icon = {"wait": "○", "run": "●", "done": "●", "fail": "●"}[state]
        color = {"wait": self._pal["muted"], "run": self._pal["info"],
                 "done": self._pal["ok"], "fail": self._pal["err"]}[state]
        suffix = {"run": " …"}.get(state, "")
        self.stage_labels[idx].setText(f"{icon}  {STAGES[idx]}{suffix}")
        self.stage_labels[idx].setStyleSheet(f"color:{color}")
        done_n = sum(1 for s in self._stage_state if s in ("done", "fail"))
        self._animate_bar(int(done_n / len(STAGES) * 100))
        if note:
            self.stage_msg.setText(note)

    def _run_stages(self):
        if self._closing:
            return
        self._set_stage(0, "done", f"配置已读取 · 仓库根目录 {len(self._settings.get('repoRoots', []))} 个")
        self._set_stage(1, "run")
        scan = RepoScanWorker(self._settings.get("repoRoots", []), self)
        self._track(scan)
        scan.done.connect(self._on_repos)
        scan.failed.connect(self._on_scan_fail)
        scan.start()

    def _on_repos(self, repos: list):
        self._repos = repos
        if repos:
            storage.save_repo_cache(repos)
        self._set_stage(1, "done", f"仓库 {len(repos)} 个")
        self._continue_after_scan()

    def _on_scan_fail(self, err: str):
        cached = storage.load_repo_cache().get("repos", [])
        self._repos = cached
        self._set_stage(1, "fail", f"扫描失败：{err}｜显示上次缓存 {len(cached)} 个")
        self._continue_after_scan()

    def _continue_after_scan(self):
        if self._closing:
            return
        self._set_stage(2, "done", f"速查 {len(self._cheat_rows)} 条")

        if self._settings.get("allowNetwork", True):
            self._set_stage(3, "run")
            tw = TrendingWorker(self._settings.get("trendingLimit", 10), self)
            self._track(tw)
            tw.done.connect(self._on_trending)
            tw.failed.connect(self._on_trending_fail)
            tw.start()
        else:
            self._set_stage(3, "done", "离线模式，读取热榜缓存")
            self._finish()

    def _on_trending(self, items: list):
        self._trending = items
        storage.save_trending_cache(items)
        self._set_stage(3, "done", f"热榜 Top {len(items)} 已更新")
        self._finish()

    def _on_trending_fail(self, err: str):
        self._set_stage(3, "fail", "热榜拉取失败，显示上次缓存")
        self._finish()

    def _finish(self):
        self._set_stage(4, "done", "就绪，欢迎回来。")
        self.enter_btn.setEnabled(True)
        self.enter_btn.setFocus()

    # ---------- 进入主界面 ----------
    def closeEvent(self, event):
        self._closing = True
        self._ticker_timer.stop()
        self._stop_workers()
        super().closeEvent(event)

    def _enter(self):
        if self._opened:
            return
        self._opened = True
        from .ui_dashboard import DashboardWindow
        payload = {
            "settings": self._settings,
            "repos": self._repos,
            "trending": self._trending,
            "riddle": self._riddle,
            "progress": self._progress,
            "cheat_rows": self._cheat_rows,
            "today": self._today,
        }
        self._dash = DashboardWindow(payload)
        self._dash.show()
        self.close()
