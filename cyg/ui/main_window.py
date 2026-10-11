"""主窗口。"""
import re

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSplitter,
                               QVBoxLayout, QWidget)

from .. import config
from ..api import CygApi
from ..crawler import CrawlWorker
from ..db import Db
from ..filters import apply_filter
from ..imageloader import ImageLoader
from .card import CardWidget
from .card_list import CardList
from .filter_panel import FilterPanel

_LEVEL_RE = re.compile(r"(\d+)\s*级")
_REBIRTH_RE = re.compile(r"(\d+)\s*转")


class _AreaSignals(QObject):
    done = Signal(object)
    error = Signal(str)


class _FetchAreas(QRunnable):
    def __init__(self, api: CygApi):
        super().__init__()
        self.api = api
        self.signals = _AreaSignals()

    def run(self):
        try:
            data = self.api.get_servers()
            self.signals.done.emit(data)
        except Exception as e:  # noqa: BLE001
            self.signals.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{config.APP_NAME} · {config.GAME_NAME}")
        self.resize(1320, 820)

        self.api = CygApi()
        self.db = Db()
        self.loader = ImageLoader(self)
        self.worker = None
        self._roles = []
        self._areas = []

        self._build_ui()
        self._load_areas()
        self.refresh_data()

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(QLabel("大区"))
        self.area_combo = QComboBox()
        self.area_combo.setMinimumWidth(160)
        self.area_combo.addItem("全部大区", None)
        top.addWidget(self.area_combo)

        top.addWidget(QLabel("职业"))
        self.job_combo = QComboBox()
        self.job_combo.setMinimumWidth(120)
        self.job_combo.addItem("全部职业", None)
        for jid, name in config.JOB_NAMES.items():
            self.job_combo.addItem(name, jid)
        top.addWidget(self.job_combo)

        self.btn_crawl = QPushButton("拉取 / 更新数据")
        self.btn_crawl.clicked.connect(self.start_crawl)
        top.addWidget(self.btn_crawl)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_crawl)
        top.addWidget(self.btn_cancel)

        self.chk_force = QCheckBox("重新抓取详情")
        top.addWidget(self.chk_force)

        top.addStretch(1)
        root.addLayout(top)

        status_row = QHBoxLayout()
        self.bar = QProgressBar()
        self.bar.setFixedWidth(260)
        self.status = QLabel("就绪")
        self.status.setStyleSheet("color:#52525b;")
        status_row.addWidget(self.bar)
        status_row.addWidget(self.status, 1)
        root.addLayout(status_row)

        splitter = QSplitter(Qt.Horizontal)
        self.filter_panel = FilterPanel()
        self.filter_panel.changed.connect(self.apply_and_render)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.filter_panel)
        scroll.setMinimumWidth(360)
        scroll.setStyleSheet("QScrollArea{border:none;background:#fafafb;}")
        splitter.addWidget(scroll)

        self.card_list = CardList(self.loader)
        self.card_list.open_requested.connect(CardWidget.open_in_browser)
        splitter.addWidget(self.card_list)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 940])
        root.addWidget(splitter, 1)

    # ---------- 大区 ----------
    def _load_areas(self):
        self.status.setText("加载大区…")
        task = _FetchAreas(self.api)
        task.signals.done.connect(self._on_areas)
        task.signals.error.connect(lambda m: self.status.setText(f"大区加载失败：{m}"))
        QThreadPool.globalInstance().start(task)

    def _on_areas(self, areas):
        self._areas = areas
        self.area_combo.blockSignals(True)
        while self.area_combo.count() > 1:
            self.area_combo.removeItem(1)
        for a in areas:
            self.area_combo.addItem(a.get("name") or a.get("id"), a)
        self.area_combo.blockSignals(False)
        self.status.setText(f"已加载 {len(areas)} 个大区")
        self.refresh_data()

    def _server_area_map(self):
        """serverId -> 大区名。"""
        mapping = {}
        for a in self._areas:
            name = a.get("name") or a.get("id") or ""
            for s in a.get("server") or []:
                sid = str(s.get("serverId") or "")
                if sid and sid not in mapping:
                    mapping[sid] = name
        return mapping

    # ---------- 爬取 ----------
    def start_crawl(self):
        if self.worker and self.worker.isRunning():
            return
        area = self.area_combo.currentData()
        server_ids = None
        if area:
            server_ids = sorted({str(s.get("serverId"))
                                 for s in (area.get("server") or []) if s.get("serverId")})
        job = self.job_combo.currentData()

        self._set_busy(True)
        self.status.setText("开始拉取…")
        self.worker = CrawlWorker(
            self.api, self.db,
            server_ids=server_ids, job=job,
            fetch_details=True, force_detail=self.chk_force.isChecked(),
        )
        self.worker.stage.connect(self.status.setText)
        self.worker.log.connect(self._on_log)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_crawl_done)
        self.worker.failed.connect(self._on_crawl_failed)
        self.worker.start()

    def cancel_crawl(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("正在取消…")

    def _set_busy(self, busy: bool):
        self.btn_crawl.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        self.area_combo.setEnabled(not busy)
        self.job_combo.setEnabled(not busy)
        if not busy:
            self.bar.setValue(0)

    def _on_log(self, msg):
        self.status.setText(msg)

    def _on_progress(self, cur, total):
        if total <= 0:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, total)
            self.bar.setValue(cur)

    def _on_crawl_done(self, n):
        self._set_busy(False)
        self.status.setText(f"完成，共 {n} 条角色")
        self.refresh_data()

    def _on_crawl_failed(self, msg):
        self._set_busy(False)
        self.status.setText("抓取失败")
        QMessageBox.warning(self, "抓取失败", msg[:1500])

    # ---------- 数据 & 渲染 ----------
    def refresh_data(self):
        self._roles = self.db.load_all()
        area_map = self._server_area_map()
        for r in self._roles:
            r["area_name"] = area_map.get(str(r.get("server_id") or ""), "")
            self._enrich(r)
        attrs = self._available_attrs()
        servers = self._available_servers()
        self.filter_panel.set_options(attrs, servers)
        self.apply_and_render()

    def _enrich(self, role):
        attrs = role.setdefault("attrs", {})
        title = role.get("title") or ""
        if "等级" not in attrs:
            m = _LEVEL_RE.search(title)
            if m:
                attrs["等级"] = {"num": float(m.group(1)), "raw": m.group(1)}
        if "转生" not in attrs:
            m = _REBIRTH_RE.search(title)
            if m:
                attrs["转生"] = {"num": float(m.group(1)), "raw": m.group(1)}

    def _available_attrs(self):
        names = {}
        for r in self._roles:
            for n, a in r.get("attrs", {}).items():
                if a.get("num") is not None:
                    names[n] = True
        return sorted(names.keys(),
                      key=lambda n: (n not in config.FILTER_PRIMARY_ATTRS, n))

    def _available_servers(self):
        """当前数据里出现的区服（serverId），带大区名与服务器名提示。"""
        name_map = {}
        for a in self._areas:
            area = a.get("name") or a.get("id") or ""
            for s in a.get("server") or []:
                sid = str(s.get("serverId") or "")
                if not sid:
                    continue
                info = name_map.setdefault(sid, {"area": area, "names": []})
                nm = s.get("name")
                if nm and nm not in info["names"]:
                    info["names"].append(nm)
        seen = set()
        options = []
        for r in self._roles:
            sid = str(r.get("server_id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            info = name_map.get(sid) or {}
            area = info.get("area") or r.get("area_name") or ""
            names = info.get("names") or []
            label = f"{area} · {sid}" if area else f"区服 {sid}"
            tip = label + ("\n" + " / ".join(names) if names else "")
            options.append({"id": sid, "label": label, "tip": tip, "area": area})
        options.sort(key=lambda o: (o["area"], o["id"]))
        return options

    def apply_and_render(self):
        state = self.filter_panel.get_state()
        filtered = apply_filter(self._roles, state)
        self.card_list.set_roles(filtered)
