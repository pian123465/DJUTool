"""PyQt6 主窗口 - 苹果风格重写版。

布局:
    ┌─ Sidebar(80px) ─┬─ Main ──────────────────────────┐
    │                  │ Titlebar              [搜索]    │
    │   📺 搜索        │ ──────────────────────────────  │
    │   🔗 链接        │  分段控件: [搜索] [链接]        │
    │   ⬇ 任务        │  卡片化内容区                  │
    │   ⚙️ 设置       │                                  │
    └──────────────────┴──────────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from loguru import logger
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from .apple_style import APPLE_QSS, Colors, Fonts
from .core.aria2_client import Aria2Client
from .core.base import DownloadOptions, Drama, Episode
from .core.downloader import DownloadEngine
from .core.link_parser import LinkParser
from .core.orchestrator import SearchOrchestrator
from .core.share_resolver import ShareResolver
from .core.task_store import Task, TaskStore
from .platforms._template import HemaPlatform, HongguoPlatform

# 加载用户自定义签名
try:
    from .plugins import signatures  # noqa: F401
except ImportError:
    logger.warning("未加载用户签名插件")


# ====================================================================
#  工作线程
# ====================================================================
class SearchWorker(QThread):
    result = pyqtSignal(object)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, orchestrator: SearchOrchestrator, keyword: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.keyword = keyword

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _collect():
                buf = []
                async for d in self.orchestrator.search_all(self.keyword):
                    buf.append(d)
                return buf

            results = loop.run_until_complete(_collect())
            for r in results:
                self.result.emit(r)
            self.finished_ok.emit()
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int, str, int)
    done = pyqtSignal(int, str)
    failed = pyqtSignal(int, str)

    def __init__(self, engine, episode, url, save_dir, store, task_id):
        super().__init__()
        self.engine = engine
        self.episode = episode
        self.url = url
        self.save_dir = save_dir
        self.store = store
        self.task_id = task_id

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def _on_prog(done, total, status):
                return _on_prog_signal(done, total, status, self.task_id)
            # 不直接 set 内层 closure 会丢,改成调用 self.progress.emit
            def on_prog(d, t, s):
                self.progress.emit(d, t, s, self.task_id)

            result = loop.run_until_complete(self.engine.download(self.episode, self.url, on_prog))
            if result.success:
                self.store.mark_done(self.task_id, result.path.stat().st_size if result.path else 0)
                self.done.emit(self.task_id, str(result.path))
            else:
                self.store.mark_failed(self.task_id, result.error)
                self.failed.emit(self.task_id, result.error)
        except Exception as e:
            self.store.mark_failed(self.task_id, str(e))
            self.failed.emit(self.task_id, str(e))


def _on_prog_signal(*a):
    pass


# ====================================================================
#  通用卡片 / 按钮工厂
# ====================================================================
def make_card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setFrameShape(QFrame.Shape.NoFrame)
    return f


def make_title_label(text: str, size: int = Fonts.TITLE) -> QLabel:
    lbl = QLabel(text)
    font = lbl.font()
    font.setPointSize(size)
    font.setWeight(QFont.Weight.DemiBold)
    lbl.setFont(font)
    return lbl


def make_subtitle(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("subtitleLabel")
    return lbl


# ====================================================================
#  搜索页
# ====================================================================
class SearchPage(QWidget):
    """搜索 + 结果页。"""

    drama_selected = pyqtSignal(object)  # Drama

    def __init__(self, orchestrator: SearchOrchestrator, parent=None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(16)

        # 搜索框(大,卡片化)
        search_row = QHBoxLayout()
        self.input_kw = QLineEdit()
        self.input_kw.setPlaceholderText("搜索短剧关键字,例如:龙王 / 总裁 / 战神 ...")
        self.input_kw.setMinimumHeight(44)
        self.input_kw.returnPressed.connect(self.do_search)
        self.btn_search = QPushButton("搜索")
        self.btn_search.setObjectName("primaryBtn")
        self.btn_search.setMinimumHeight(44)
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.clicked.connect(self.do_search)
        search_row.addWidget(self.input_kw, 1)
        search_row.addWidget(self.btn_search)
        v.addLayout(search_row)

        # 结果标题
        self.lbl_count = make_subtitle("对 · 暂无搜索结果")
        v.addWidget(self.lbl_count)

        # 结果卡片列表
        self.list_results = QListWidget()
        self.list_results.setSpacing(6)
        self.list_results.itemClicked.connect(self._on_item_clicked)
        v.addWidget(self.list_results, 1)

    def do_search(self):
        kw = self.input_kw.text().strip()
        if not kw:
            return
        self.list_results.clear()
        self.lbl_count.setText(f"搜索 {kw} 中...")
        self.btn_search.setEnabled(False)

        self._worker = SearchWorker(self.orchestrator, kw)
        self._worker.result.connect(self._on_result)
        self._worker.finished_ok.connect(self._on_search_done)
        self._worker.error.connect(lambda m: QMessageBox.warning(self, "搜索出错", m))
        self._worker.start()

    def _on_result(self, d: Drama):
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 80))
        item.setData(Qt.ItemDataRole.UserRole, d)
        widget = self._make_result_card(d)
        self.list_results.addItem(item)
        self.list_results.setItemWidget(item, widget)

    def _make_result_card(self, d: Drama) -> QWidget:
        card = make_card()
        card.setMinimumHeight(72)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 封面占位
        cover = QLabel()
        cover.setFixedSize(48, 64)
        cover.setStyleSheet(f"background:{Colors.PRIMARY};border-radius:8px;color:white;font-weight:600;font-size:18px;")
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setText(d.title[:1])
        layout.addWidget(cover)

        info = QVBoxLayout()
        info.setSpacing(4)
        title = QLabel(d.title)
        title.setObjectName("cardTitle")
        meta = QLabel(f"{d.platform} · {d.episode_count} 集")
        meta.setObjectName("cardMeta")
        info.addWidget(title)
        info.addWidget(meta)
        info.addStretch(1)
        layout.addLayout(info, 1)

        # 右侧箭头
        chev = QLabel("›")
        chev.setStyleSheet("color:#AEAEB2;font-size:24px;font-weight:300;")
        layout.addWidget(chev, alignment=Qt.AlignmentFlag.AlignVCenter)
        return card

    def _on_item_clicked(self, item: QListWidgetItem):
        d = item.data(Qt.ItemDataRole.UserRole)
        self.drama_selected.emit(d)

    def _on_search_done(self):
        self.btn_search.setEnabled(True)
        n = self.list_results.count()
        self.lbl_count.setText(f"对 · 找到 {n} 条结果" if n else "对 · 未找到结果(平台 API 尚未接入)")


# ====================================================================
#  链接解析页
# ====================================================================
class LinkPage(QWidget):
    """分享链接解析页。"""

    drama_loaded = pyqtSignal(object, object)  # Drama, list[Episode]

    def __init__(self, resolver: ShareResolver, parent=None):
        super().__init__(parent)
        self.resolver = resolver
        self.current_drama: Drama | None = None
        self.current_eps: list[Episode] = []
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(16)

        # 输入卡片
        input_card = make_card()
        ic_lay = QVBoxLayout(input_card)
        ic_lay.setContentsMargins(16, 16, 16, 16)
        ic_lay.setSpacing(12)
        ic_lay.addWidget(make_title_label("粘贴分享文本", Fonts.BODY))
        self.input_share = QTextEdit()
        self.input_share.setPlaceholderText(
            "把抖音 / 红果 / 河马的分享文案整段贴进来,自动识别链接。\n"
            "示例:[红果短剧] 龙王驾到 https://v.douyin.com/abc123/"
        )
        self.input_share.setMaximumHeight(110)
        ic_lay.addWidget(self.input_share)

        btn_row = QHBoxLayout()
        self.btn_paste = QPushButton("📋 从剪贴板粘贴")
        self.btn_paste.setObjectName("secondaryBtn")
        self.btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_paste.clicked.connect(self._paste_clipboard)
        self.btn_parse = QPushButton("🔍 解析")
        self.btn_parse.setObjectName("primaryBtn")
        self.btn_parse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_parse.clicked.connect(self.do_parse)
        btn_row.addWidget(self.btn_paste)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_parse)
        ic_lay.addLayout(btn_row)
        v.addWidget(input_card)

        # 解析结果卡
        self.result_card = make_card()
        rc_lay = QVBoxLayout(self.result_card)
        rc_lay.setContentsMargins(16, 16, 16, 16)
        rc_lay.setSpacing(8)
        rc_lay.addWidget(make_title_label("解析结果", Fonts.BODY))
        self.lbl_result = QLabel("等待解析...")
        self.lbl_result.setObjectName("cardMeta")
        self.lbl_result.setWordWrap(True)
        rc_lay.addWidget(self.lbl_result)
        v.addWidget(self.result_card)

        # 剧集列表
        self.list_eps = QListWidget()
        self.list_eps.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_eps.setSpacing(6)
        v.addWidget(self.list_eps, 1)

        # 参数
        param_card = make_card()
        pl = QFormLayout(param_card)
        pl.setContentsMargins(16, 12, 16, 12)
        pl.setSpacing(10)
        pl.addRow(self._make_fmt_row())
        pl.addRow(self._make_path_row())
        pl.addRow(self._make_all_row())
        v.addWidget(param_card)

        self.btn_download = QPushButton("⬇ 下载选中 / 全集")
        self.btn_download.setObjectName("primaryBtn")
        self.btn_download.setMinimumHeight(44)
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self.do_download)
        v.addWidget(self.btn_download)

    def _make_fmt_row(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(QLabel("格式"))
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(["mp4", "ts", "mkv"])
        h.addWidget(self.cmb_fmt)
        h.addWidget(QLabel("分辨率"))
        self.cmb_res = QComboBox()
        self.cmb_res.addItems(["source", "1080p", "720p", "480p"])
        h.addWidget(self.cmb_res)
        h.addWidget(QLabel("并发"))
        self.spin_conc = QSpinBox()
        self.spin_conc.setRange(1, 16)
        self.spin_conc.setValue(4)
        h.addWidget(self.spin_conc)
        h.addStretch(1)
        return row

    def _make_path_row(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QLabel("保存到"))
        self.path_edit = QLineEdit("./downloads")
        h.addWidget(self.path_edit, 1)
        return row

    def _make_all_row(self):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        self.chk_all = QCheckBox("批量下载全集(忽略选择)")
        h.addWidget(self.chk_all)
        h.addStretch(1)
        return row

    def _paste_clipboard(self):
        cb = QApplication.clipboard().text()
        if cb:
            self.input_share.setPlainText(cb)

    def do_parse(self):
        text = self.input_share.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "先粘贴分享文本")
            return
        self.lbl_result.setText("解析中...")
        self.btn_parse.setEnabled(False)

        async def _do():
            return await self.resolver.resolve(text)

        loop = asyncio.new_event_loop()
        try:
            parsed, drama = loop.run_until_complete(_do())
        finally:
            loop.close()
        self.btn_parse.setEnabled(True)

        self.list_eps.clear()
        self.current_drama = drama

        if not parsed or not parsed.url:
            self.lbl_result.setText("❌ 文本里没识别出 URL")
            self.current_eps = []
            return

        info = (
            f"✅ URL:{parsed.url}\n"
            f"   重定向 → {parsed.final_url[:70]}{'...' if len(parsed.final_url) > 70 else ''}\n"
            f"   平台:{parsed.platform} | 剧 ID:{parsed.drama_id}"
        )
        if not drama:
            info += "\n   ⚠️ 平台适配器未接入(需先逆向签名才能拿到剧集)"
        self.lbl_result.setText(info)

        if drama:
            # 拉剧集
            try:
                loop2 = asyncio.new_event_loop()
                try:
                    platform = next((p for p in self.resolver.platforms
                                    if any(d in parsed.platform or d in parsed.domain for d in p.url_domains)),
                                   None)
                    if platform:
                        eps = loop2.run_until_complete(platform.get_episodes(drama))
                        self.current_eps = eps
                        for ep in eps:
                            item = QListWidgetItem(f"第{ep.index}集 · {ep.title}")
                            item.setSizeHint(QSize(0, 44))
                            item.setData(Qt.ItemDataRole.UserRole, ep)
                            self.list_eps.addItem(item)
                finally:
                    loop2.close()
            except Exception as e:
                self.list_eps.addItem(f"⚠️ 拉剧集失败:{e}")

    def do_download(self):
        if not self.current_drama:
            QMessageBox.information(self, "提示", "请先成功解析")
            return
        QMessageBox.information(
            self, "已就绪",
            f"准备下载:{self.current_drama.title}\n"
            f"格式:{self.cmb_fmt.currentText()} / 分辨率:{self.cmb_res.currentText()}\n\n"
            "下载入口完整(aria2 / yt-dlp / native + 断点续传)。\n"
            "接入平台签名后,真实 URL 一解析就能下。",
        )


# ====================================================================
#  任务页
# ====================================================================
class TasksPage(QWidget):
    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(12)

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setObjectName("secondaryBtn")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_clean = QPushButton("🧹 清理已完成(7天前)")
        self.btn_clean.setObjectName("secondaryBtn")
        self.btn_clean.clicked.connect(self._clean)
        bar.addWidget(self.btn_refresh)
        bar.addWidget(self.btn_clean)
        bar.addStretch(1)
        v.addLayout(bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "剧集", "状态", "进度", "引擎"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        v.addWidget(self.table, 1)
        self.refresh()

    def refresh(self):
        tasks = self.store.list_tasks(limit=200)
        self.table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            color = {
                "done": Colors.SUCCESS,
                "failed": Colors.DANGER,
                "downloading": Colors.PRIMARY,
                "paused": Colors.WARNING,
            }.get(t.status, Colors.TEXT_SECONDARY)

            self.table.setItem(i, 0, QTableWidgetItem(str(t.id)))
            self.table.setItem(i, 1, QTableWidgetItem(f"{t.drama_title} - {t.episode_title}"))
            status = QTableWidgetItem(t.status)
            status.setForeground(QColor(color))
            self.table.setItem(i, 2, status)
            pct = (t.done_size / t.total_size * 100) if t.total_size else 0
            self.table.setItem(i, 3, QTableWidgetItem(f"{pct:.1f}%"))
            self.table.setItem(i, 4, QTableWidgetItem(t.engine))

    def _clean(self):
        self.store.clear_finished(keep_days=7)
        self.refresh()


# ====================================================================
#  设置页
# ====================================================================
class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 16, 24, 16)
        v.setSpacing(16)

        v.addWidget(make_title_label("设置", Fonts.LARGE))

        # 引擎状态卡
        engine_card = make_card()
        ec = QVBoxLayout(engine_card)
        ec.setContentsMargins(16, 16, 16, 16)
        ec.addWidget(make_title_label("下载引擎", Fonts.BODY))
        aria2_ok = Aria2Client.is_installed()
        items = [
            ("aria2c", "✓ 已安装" if aria2_ok else "✗ 未安装"),
            ("yt-dlp", "✓ 可用(需装 Python 包)"),
            ("native", "✓ 可用(内置 aiohttp + ffmpeg)"),
        ]
        for name, st in items:
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            row.addStretch(1)
            row.addWidget(QLabel(st))
            ec.addLayout(row)
        v.addWidget(engine_card)

        # 关于
        about_card = make_card()
        ac = QVBoxLayout(about_card)
        ac.setContentsMargins(16, 16, 16, 16)
        ac.addWidget(make_title_label("关于", Fonts.BODY))
        ac.addWidget(QLabel("短剧下载器 v0.3"))
        ac.addWidget(QLabel("技术栈:PyQt6 · aiohttp · aria2 · yt-dlp · ffmpeg · SQLite"))
        about_lbl = QLabel(
            "本工具仅供技术研究与个人学习。\n"
            "请勿用于商业传播或侵犯版权,各平台视频版权归平台与版权方所有。"
        )
        about_lbl.setObjectName("cardDesc")
        about_lbl.setWordWrap(True)
        ac.addWidget(about_lbl)
        v.addWidget(about_card)
        v.addStretch(1)


# ====================================================================
#  主窗口
# ====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("短剧下载器")
        self.resize(1200, 800)

        self.platforms = [HongguoPlatform(), HemaPlatform()]
        self.orchestrator = SearchOrchestrator(self.platforms)
        self.share_resolver = ShareResolver(self.platforms)
        self.task_store = TaskStore()

        # 子页面
        self.search_page = SearchPage(self.orchestrator)
        self.link_page = LinkPage(self.share_resolver)
        self.tasks_page = TasksPage(self.task_store)
        self.settings_page = SettingsPage()

        self.search_page.drama_selected.connect(self._on_drama_selected)
        self.link_page.drama_loaded.connect(self._on_drama_selected)

        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ========== 侧边栏 ==========
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(12, 16, 12, 16)
        sv.setSpacing(8)

        logo = QLabel("📺 短剧下载器")
        logo.setStyleSheet("font-size:16px;font-weight:600;color:#1D1D1F;padding:8px 12px;")
        sv.addWidget(logo)
        sv.addSpacing(8)

        self.nav_btns: list[QPushButton] = []
        nav_items = [
            ("🔍 搜索短剧", 0),
            ("🔗 链接解析", 1),
            ("⬇ 下载任务", 2),
            ("⚙ 设置", 3),
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("sidebarBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sv.addWidget(btn)
            self.nav_btns.append(btn)
        sv.addStretch(1)
        h.addWidget(sidebar)

        # ========== 主区 ==========
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)

        # 顶栏
        titlebar = QFrame()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(60)
        tv = QHBoxLayout(titlebar)
        tv.setContentsMargins(24, 0, 24, 0)
        self.lbl_title = make_title_label("搜索短剧", Fonts.TITLE)
        self.lbl_subtitle = make_subtitle("跨平台并发搜索 · 三引擎下载 · 断点续传")
        title_info = QVBoxLayout()
        title_info.setSpacing(2)
        title_info.addWidget(self.lbl_title)
        title_info.addWidget(self.lbl_subtitle)
        tv.addLayout(title_info)
        tv.addStretch(1)
        mv.addWidget(titlebar)

        # 页面栈
        self.stack = QStackedWidget()
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.link_page)
        self.stack.addWidget(self.tasks_page)
        self.stack.addWidget(self.settings_page)
        mv.addWidget(self.stack, 1)
        h.addWidget(main, 1)

        # 状态栏
        self.status = self.statusBar()
        self.status.showMessage("就绪")
        self._switch_page(0)

    def _switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        titles = [
            ("搜索短剧", "跨平台并发搜索 · 三引擎下载 · 断点续传"),
            ("链接解析", "粘贴分享文案 · 自动识别 · 一键下载"),
            ("下载任务", "查看下载进度 · 续传未完成任务 · 清理记录"),
            ("设置", "引擎状态 · 版本信息"),
        ]
        self.lbl_title.setText(titles[idx][0])
        self.lbl_subtitle.setText(titles[idx][1])
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == idx)
        if idx == 2:
            self.tasks_page.refresh()

    def _on_drama_selected(self, drama: Drama):
        # 选中剧后自动跳到链接页(逻辑串起来)
        self._switch_page(1)
        # 在链接页预填搜索关键字
        self.link_page.input_share.setPlainText(drama.title)


def main():
    app = QApplication([])
    app.setStyleSheet(APPLE_QSS)
    # 默认字体
    font = QFont("Segoe UI Variable Display", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()