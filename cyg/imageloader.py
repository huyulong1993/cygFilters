"""异步图片加载（下载到磁盘缓存，GUI 线程再转 QPixmap）。"""
import hashlib
import os

import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from . import config

_session = requests.Session()
_session.headers.update({"User-Agent": config.USER_AGENT,
                         "Referer": config.BASE_URL + "/list"})


def _cache_path(url: str) -> str:
    name = hashlib.md5(url.encode("utf-8")).hexdigest()
    return str(config.IMAGE_CACHE_DIR / f"{name}.img")


class _Task(QRunnable):
    def __init__(self, loader, url: str):
        super().__init__()
        self.loader = loader
        self.url = url

    def run(self):
        path = _cache_path(self.url)
        try:
            if not os.path.exists(path):
                r = _session.get(self.url, timeout=20)
                if r.status_code == 200 and r.content:
                    tmp = path + ".part"
                    with open(tmp, "wb") as f:
                        f.write(r.content)
                    os.replace(tmp, path)
            self.loader.loaded.emit(self.url, path if os.path.exists(path) else "")
        except Exception:  # noqa: BLE001
            self.loader.loaded.emit(self.url, "")


class ImageLoader(QObject):
    loaded = Signal(str, str)  # url, 本地路径（空表示失败）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max(6, self.pool.maxThreadCount()))
        self._pending = set()

    @staticmethod
    def full_url(image_field: str) -> str:
        if not image_field:
            return ""
        if image_field.startswith("http"):
            return image_field
        return config.PUBLIC_URL + "/" + image_field.lstrip("/")

    def request(self, url: str) -> str:
        """返回本地已缓存路径；未缓存则返回空并触发下载。"""
        if not url:
            return ""
        path = _cache_path(url)
        if os.path.exists(path):
            return path
        if url not in self._pending:
            self._pending.add(url)
            self.pool.start(_Task(self, url))
        return ""
