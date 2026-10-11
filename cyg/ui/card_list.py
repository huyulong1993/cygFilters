"""角色卡片列表（自动换行）。"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from .card import CardWidget

_PAGE = 60  # 每次渲染的卡片数，避免一次性创建过多控件


class CardList(QWidget):
    open_requested = Signal(dict)

    def __init__(self, loader, parent=None):
        super().__init__(parent)
        self.loader = loader
        self._roles = []
        self._rendered = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        head = QHBoxLayout()
        self.count = QLabel("共 0 条")
        self.count.setStyleSheet("font-size:14px;font-weight:600;color:#17171a;")
        head.addWidget(self.count)
        head.addStretch(1)
        tip = QLabel("点击卡片 → 浏览器打开详情/购买")
        tip.setStyleSheet("color:#8a8a95;font-size:12px;")
        head.addWidget(tip)
        root.addLayout(head)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setFlow(QListWidget.LeftToRight)
        self.list.setWrapping(True)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setUniformItemSizes(True)
        self.list.setSpacing(6)
        self.list.setGridSize(QSize(CardWidget.CARD_W + 16, CardWidget.CARD_H + 16))
        self.list.setStyleSheet("QListWidget{background:#f7f7f8;border:none;}")
        root.addWidget(self.list, 1)

        self.more = QPushButton("加载更多")
        self.more.clicked.connect(self._render_more)
        self.more.hide()
        root.addWidget(self.more, 0, Qt.AlignHCenter)

    def set_roles(self, roles):
        self._roles = roles
        self._rendered = 0
        self.list.clear()
        self._render_more()

    def _render_more(self):
        end = min(self._rendered + _PAGE, len(self._roles))
        for role in self._roles[self._rendered:end]:
            item = QListWidgetItem()
            item.setSizeHint(QSize(CardWidget.CARD_W + 10, CardWidget.CARD_H + 10))
            self.list.addItem(item)
            card = CardWidget(role, self.loader)
            card.clicked.connect(self.open_requested)
            self.list.setItemWidget(item, card)
        self._rendered = end
        total = len(self._roles)
        self.count.setText(f"共 {total} 条，已显示 {self._rendered} 条")
        self.more.setVisible(self._rendered < total)
