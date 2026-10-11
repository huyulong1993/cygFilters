"""左侧筛选面板。"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDoubleValidator, QFontMetrics
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QVBoxLayout,
                               QWidget)

from .. import config
from ..filters import FilterState

_ATTR_COLUMNS = 2   # 角色属性分栏数
_LABEL_W = 138      # 单元标签可用宽度（用于省略号）


def _parse(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class _RangeCell(QWidget):
    """两行式属性筛选单元：标签 + (最小 ~ 最大)。"""

    def __init__(self, name: str, on_change):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self.label = QLabel()
        self.label.setStyleSheet("color:#40444d;font-size:12px;")
        fm = QFontMetrics(self.label.font())
        self.label.setText(fm.elidedText(name, Qt.ElideRight, _LABEL_W))
        self.label.setToolTip(name)
        lay.addWidget(self.label)

        self.lo = QLineEdit()
        self.hi = QLineEdit()
        for e in (self.lo, self.hi):
            e.setPlaceholderText("不限")
            e.setValidator(QDoubleValidator())
            e.setFixedWidth(56)
            e.textChanged.connect(on_change)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self.lo)
        row.addWidget(QLabel("~"))
        row.addWidget(self.hi)
        row.addStretch(1)
        lay.addLayout(row)

    def value(self):
        return _parse(self.lo.text()), _parse(self.hi.text())


class FilterPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attr_cells = {}       # name -> _RangeCell
        self._ordered_cells = []    # [(name, cell)] 保持展示顺序
        self._job_checks = {}
        self._server_checks = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.changed.emit)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # 关键词
        gb_kw = QGroupBox("关键词")
        kw_lay = QVBoxLayout(gb_kw)
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("角色名，如：挥剑破云")
        self.keyword.textChanged.connect(self._tick)
        kw_lay.addWidget(self.keyword)
        root.addWidget(gb_kw)

        # 价格
        gb_price = QGroupBox("价格（元）")
        p_lay = QHBoxLayout(gb_price)
        self.price_lo = QLineEdit()
        self.price_hi = QLineEdit()
        for e in (self.price_lo, self.price_hi):
            e.setPlaceholderText("不限")
            e.setValidator(QDoubleValidator())
            e.textChanged.connect(self._tick)
        p_lay.addWidget(self.price_lo)
        p_lay.addWidget(QLabel("~"))
        p_lay.addWidget(self.price_hi)
        root.addWidget(gb_price)

        # 职业（多选）
        gb_job = QGroupBox("职业")
        job_grid = QGridLayout(gb_job)
        for i, name in enumerate(config.JOB_NAMES.values()):
            cb = QCheckBox(name)
            cb.stateChanged.connect(self._tick)
            self._job_checks[name] = cb
            job_grid.addWidget(cb, i // 3, i % 3)
        root.addWidget(gb_job)

        # 区服（多选）
        self.gb_server = QGroupBox("区服")
        self.server_grid = QGridLayout(self.gb_server)
        self.server_grid.setVerticalSpacing(4)
        root.addWidget(self.gb_server)

        # 角色属性（搜索 + 分栏）
        self.gb_attr = QGroupBox("角色属性（数值区间）")
        attr_v = QVBoxLayout(self.gb_attr)
        self.attr_search = QLineEdit()
        self.attr_search.setPlaceholderText("模糊搜索属性，如：评分 / 抗性 / 积分")
        self.attr_search.textChanged.connect(self._relayout_attrs)
        attr_v.addWidget(self.attr_search)

        self.attr_container = QWidget()
        self.attr_grid = QGridLayout(self.attr_container)
        self.attr_grid.setContentsMargins(0, 0, 0, 0)
        self.attr_grid.setHorizontalSpacing(10)
        self.attr_grid.setVerticalSpacing(8)
        attr_v.addWidget(self.attr_container)

        self._empty_hint = QLabel("（无匹配属性）")
        self._empty_hint.setStyleSheet("color:#9a9aa5;font-size:12px;")
        self._empty_hint.hide()
        root.addWidget(self.gb_attr)

        # 排序
        gb_sort = QGroupBox("排序")
        s_lay = QHBoxLayout(gb_sort)
        self.sort = QComboBox()
        self.sort.currentIndexChanged.connect(self._tick)
        s_lay.addWidget(self.sort)
        root.addWidget(gb_sort)
        self._rebuild_sort([])

        root.addStretch(1)

    # ---------- 构建选项 ----------
    def set_options(self, attrs, servers):
        self._build_attrs(attrs)
        self._build_servers(servers)
        self._rebuild_sort(attrs)

    def _build_attrs(self, attrs):
        # 清空并销毁旧单元（仅移出布局会残留显示，造成重影）
        while self.attr_grid.count():
            item = self.attr_grid.takeAt(0)
            w = item.widget()
            if w is None:
                continue
            if w is self._empty_hint:
                self._empty_hint.hide()
            else:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._attr_cells.clear()
        self._ordered_cells.clear()
        if attrs:
            ordered = [a for a in config.FILTER_PRIMARY_ATTRS if a in attrs]
            ordered += [a for a in attrs if a not in ordered]
            for name in ordered:
                cell = _RangeCell(name, self._tick)
                self._attr_cells[name] = cell
                self._ordered_cells.append((name, cell))
        self._relayout_attrs()

    def _build_servers(self, servers):
        while self.server_grid.count():
            item = self.server_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._server_checks.clear()
        if not servers:
            hint = QLabel("（暂无区服数据）")
            hint.setStyleSheet("color:#9a9aa5;font-size:12px;")
            self.server_grid.addWidget(hint, 0, 0)
            return
        for i, s in enumerate(servers):
            cb = QCheckBox(s.get("label") or str(s.get("id")))
            if s.get("tip"):
                cb.setToolTip(s["tip"])
            cb.stateChanged.connect(self._tick)
            self._server_checks[str(s.get("id"))] = cb
            self.server_grid.addWidget(cb, i, 0)

    def _relayout_attrs(self, *args):
        """按搜索关键词重排（模糊匹配）属性单元。"""
        while self.attr_grid.count():
            self.attr_grid.takeAt(0)
        kw = self.attr_search.text().strip().lower()
        idx = 0
        for name, cell in self._ordered_cells:
            if kw and kw not in name.lower():
                cell.hide()
                continue
            self.attr_grid.addWidget(cell, idx // _ATTR_COLUMNS, idx % _ATTR_COLUMNS)
            cell.show()
            idx += 1
        if idx == 0:
            self.attr_grid.addWidget(self._empty_hint, 0, 0)
            self._empty_hint.show()
        else:
            self._empty_hint.hide()

    def _rebuild_sort(self, attrs):
        cur = self.sort.currentData()
        self.sort.blockSignals(True)
        self.sort.clear()
        self.sort.addItem("价格 低→高", ("price", False))
        self.sort.addItem("价格 高→低", ("price", True))
        self.sort.addItem("上架时间 早→晚", ("offline_time", False))
        self.sort.addItem("上架时间 晚→早", ("offline_time", True))
        for a in attrs:
            self.sort.addItem(f"{a} 高→低", (a, True))
        if cur is not None:
            i = self.sort.findData(cur)
            if i >= 0:
                self.sort.setCurrentIndex(i)
        self.sort.blockSignals(False)

    # ---------- 取值 ----------
    def get_state(self) -> FilterState:
        st = FilterState()
        st.keyword = self.keyword.text().strip()
        st.price_min = _parse(self.price_lo.text())
        st.price_max = _parse(self.price_hi.text())
        st.jobs = {n for n, cb in self._job_checks.items() if cb.isChecked()}
        st.servers = {sid for sid, cb in self._server_checks.items() if cb.isChecked()}
        for name, cell in self._attr_cells.items():
            lo, hi = cell.value()
            if lo is not None or hi is not None:
                st.ranges[name] = (lo, hi)
        data = self.sort.currentData()
        if data:
            st.sort_key, st.sort_desc = data
        return st

    def _tick(self, *args):
        self._timer.start()
