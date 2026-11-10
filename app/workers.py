# 后台任务线程：仓库扫描 / 热榜拉取，避免阻塞界面
import threading

from PySide6.QtCore import QThread, Signal

from . import github_trending, repo_weather

# 窗口关闭时仍未结束的线程：留住引用，等其自然结束后释放
_LINGERING = []


def adopt(thread: QThread) -> None:
    """接管一个仍在运行的线程：断开业务信号、脱离 Qt 父子链，避免随窗口析构而崩溃"""
    thread.setParent(None)
    for name in ("done", "failed"):
        sig = getattr(thread, name, None)
        if sig is not None:
            try:
                sig.disconnect()
            except (RuntimeError, TypeError):
                pass
    _LINGERING.append(thread)

    def _drop(t=thread):
        if t in _LINGERING:
            _LINGERING.remove(t)
        t.deleteLater()

    thread.finished.connect(_drop)


class WorkerHost:
    """窗口侧线程托管：跟踪生命周期；关闭时先取消再等待，最后兜底接管"""

    def _track(self, worker: QThread) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._forget(w))

    def _forget(self, worker: QThread) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def _stop_workers(self) -> None:
        for w in self._workers:
            cancel = getattr(w, "cancel", None)
            if callable(cancel):
                cancel()
        lingering = [w for w in self._workers if not w.wait(4000)]
        self._workers = []
        for w in lingering:
            adopt(w)


class CancellableThread(QThread):
    """可取消线程基类：cancel 后 run 不再发结果，便于窗口关闭时快速收敛"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()


class RepoScanWorker(CancellableThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, roots: list, parent=None):
        super().__init__(parent)
        self._roots = list(roots)

    def run(self):
        try:
            repos = repo_weather.scan(self._roots, should_stop=lambda: self.stopped)
        except Exception as exc:  # noqa: BLE001 - 边界处统一兜底
            if not self.stopped:
                self.failed.emit(str(exc))
            return
        if not self.stopped:
            self.done.emit(repos)


class TrendingWorker(CancellableThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, limit: int = 10, parent=None):
        super().__init__(parent)
        self._limit = limit

    def run(self):
        try:
            items = github_trending.fetch_trending(
                limit=self._limit, should_stop=lambda: self.stopped)
        except Exception as exc:  # noqa: BLE001
            if not self.stopped:
                self.failed.emit(str(exc))
            return
        if self.stopped:
            return
        if items:
            self.done.emit(items)
        else:
            self.failed.emit("empty")
