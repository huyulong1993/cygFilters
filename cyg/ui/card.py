"""角色卡片控件。"""
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontMetrics, QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QVBoxLayout, QWidget)

from .. import config
from ..imageloader import ImageLoader

_FIELD_LABEL_W = 68


def _fmt_num(v) -> str:
    if v is None:
        return "-"
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return "-"
    if fv.is_integer():
        return f"{int(fv):,}"
    return f"{fv:,.2f}"


def _field_value(role: dict, key: str, use_raw: bool) -> str:
    a = (role.get("attrs") or {}).get(key)
    if not a:
        return "-"
    if use_raw:
        return a.get("raw") or "-"
    return _fmt_num(a.get("num"))


class CardWidget(QFrame):
    clicked = Signal(dict)

    CARD_W = 384
    CARD_H = 214

    def __init__(self, role: dict, loader: ImageLoader, parent=None):
        super().__init__(parent)
        self.role = role
        self.loader = loader
        self.setObjectName("card")
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "#card{background:#ffffff;border:1px solid #e3e3e8;border-radius:8px;}"
            "#card:hover{border:1px solid #0fdc78;}"
            "#name{color:#17171a;}"
            "#sub{color:#7a7a85;}"
            "#price{color:#e8463a;}"
            "#fkey{color:#8a8a95;}"
            "#fval{color:#26262b;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addLayout(self._build_header(role))
        root.addLayout(self._build_fields(role))
        root.addStretch(1)

        self._load_image()

    # ---------- 顶部：头像 + 名称/价格/大区 ----------
    def _build_header(self, role):
        header = QHBoxLayout()
        header.setSpacing(10)

        self.img = QLabel()
        self.img.setFixedSize(84, 84)
        self.img.setAlignment(Qt.AlignCenter)
        self.img.setStyleSheet("background:#f2f4f7;border-radius:6px;color:#9a9aa5;")
        self.img.setText("无图")
        header.addWidget(self.img)

        right = QVBoxLayout()
        right.setSpacing(4)

        top = QHBoxLayout()
        name_font = QFont(self.font())
        name_font.setPointSize(11)
        name_font.setBold(True)
        self.name = QLabel()
        self.name.setObjectName("name")
        self.name.setFont(name_font)
        fm = QFontMetrics(name_font)
        text = role.get("name") or "(未命名角色)"
        self.name.setText(fm.elidedText(text, Qt.ElideRight, 150))
        self.name.setToolTip(text)
        top.addWidget(self.name)
        top.addStretch(1)

        price = role.get("price")
        self.price = QLabel(f"¥{_fmt_num(price)}" if price is not None else "价格未知")
        self.price.setObjectName("price")
        pf = QFont(self.font())
        pf.setPointSize(11)
        pf.setBold(True)
        self.price.setFont(pf)
        top.addWidget(self.price)
        right.addLayout(top)

        sub = QLabel(self._subtitle_text(role))
        sub.setObjectName("sub")
        sub.setStyleSheet("color:#7a7a85;")
        right.addWidget(sub)
        right.addStretch(1)

        header.addLayout(right, 1)
        return header

    @staticmethod
    def _subtitle_text(role) -> str:
        parts = []
        area = role.get("area_name") or ""
        if area:
            parts.append(area)
        elif role.get("server_id"):
            parts.append(f"区服 {role['server_id']}")
        if role.get("job"):
            parts.append(role["job"])
        if role.get("title"):
            parts.append(role["title"])
        return " · ".join(parts)

    # ---------- 属性网格 ----------
    def _build_fields(self, role):
        # 两列；行内单元格用 2 列 × 若干行
        per_col = (len(config.CARD_FIELDS) + 1) // 2  # 左列优先填满
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        for i, (label, key, use_raw) in enumerate(config.CARD_FIELDS):
            col = 0 if i < per_col else 1
            row = i if i < per_col else i - per_col
            grid.addWidget(self._field_cell(label, _field_value(role, key, use_raw)),
                           row, col)
        return grid

    @staticmethod
    def _field_cell(label: str, value: str) -> QWidget:
        cell = QWidget()
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        k = QLabel(label)
        k.setObjectName("fkey")
        k.setFixedWidth(_FIELD_LABEL_W)
        k.setStyleSheet("color:#8a8a95;font-size:12px;")
        v = QLabel(value)
        v.setObjectName("fval")
        v.setStyleSheet("color:#26262b;font-size:12px;font-weight:600;")
        lay.addWidget(k)
        lay.addWidget(v)
        lay.addStretch(1)
        return cell

    # ---------- 图片 ----------
    def _load_image(self):
        url = ImageLoader.full_url(self.role.get("image") or "")
        if not url:
            return
        path = self.loader.request(url)
        if path:
            self._set_pixmap(path)
        else:
            self.loader.loaded.connect(self._on_loaded)

    def _on_loaded(self, url, path):
        cur = ImageLoader.full_url(self.role.get("image") or "")
        if url == cur:
            try:
                self.loader.loaded.disconnect(self._on_loaded)
            except (RuntimeError, TypeError):
                pass
            if path:
                self._set_pixmap(path)

    def _set_pixmap(self, path):
        pm = QPixmap(path)
        if not pm.isNull():
            self.img.setPixmap(pm.scaled(84, 84, Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation))
            self.img.setText("")

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.role)
        super().mouseReleaseEvent(event)

    @staticmethod
    def open_in_browser(role: dict):
        url = f"{config.BASE_URL}/details?goodsCode={role.get('goods_code')}"
        QDesktopServices.openUrl(QUrl(url))
