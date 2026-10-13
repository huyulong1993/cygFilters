"""爬虫线程：先拉列表，再并发抓角色详情。"""
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from . import config
from .api import CygApi
from .db import Db
from .parser import parse_detail, parse_equipment


class CrawlWorker(QThread):
    stage = Signal(str)              # 阶段说明
    progress = Signal(int, int)      # 已完成, 总数
    log = Signal(str)                # 日志
    done = Signal(int)               # 抓取到的角色总数
    failed = Signal(str)

    def __init__(self, api: CygApi, db: Db,
                 server_ids: Optional[List[str]] = None,
                 job: Optional[int] = None,
                 fetch_details: bool = True,
                 force_detail: bool = False,
                 concurrency: int = config.DETAIL_CONCURRENCY,
                 parent=None):
        super().__init__(parent)
        self.api = api
        self.db = db
        self.server_ids = server_ids
        self.job = job
        self.fetch_details = fetch_details
        self.force_detail = force_detail
        self.concurrency = concurrency
        self._cancel = False
        self._fetched = set()   # 本轮列表抓到的 goodsCode
        self._list_incomplete = False  # 列表分页是否出现过失败

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.stage.emit("拉取角色列表…")
            self._crawl_list()
            if self._cancel:
                self.done.emit(0)
                return
            self._cleanup_stale()
            if self.fetch_details:
                self.stage.emit("抓取角色详情…")
                self._crawl_details()
            if self._cancel:
                self.done.emit(0)
            else:
                self.done.emit(self.db.count_roles(self.server_ids))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{e}\n{traceback.format_exc()}")

    def _cleanup_stale(self):
        """删除范围内已下架/已售的角色（已不在当前列表中）。"""
        if self._list_incomplete:
            self.log.emit("列表抓取不完整，跳过旧数据清理")
            return
        if not self._fetched:
            return
        job_name = config.JOB_NAMES.get(self.job) if self.job is not None else None
        try:
            removed = self.db.prune_roles(self.server_ids, job_name, self._fetched)
            if removed:
                self.log.emit(f"清理已下架/已售角色 {removed} 条")
        except Exception as e:  # noqa: BLE001
            self.log.emit(f"清理旧数据失败：{e}")

    # ---------- 列表 ----------
    def _crawl_list(self):
        scopes = self.server_ids if self.server_ids else [None]
        for sid in scopes:
            for status in (2, 1):  # 待售 + 公示中
                if self._cancel:
                    return
                label = "全部区服" if sid is None else f"区服 {sid}"
                label += "·在售" if status == 2 else "·公示"
                page = 1
                while True:
                    if self._cancel:
                        return
                    resp = self._fetch_page_retry(page, sid, status)
                    if resp is None:
                        self._list_incomplete = True
                        self.log.emit(f"{label} 第 {page} 页多次失败，跳过该分组")
                        break
                    data = resp.get("data") or {}
                    goods = [it["goods"] for it in (data.get("list") or [])
                             if it.get("goods")]
                    if goods:
                        self.db.upsert_roles(goods)
                        self._fetched.update(str(g.get("goodsCode")) for g in goods)
                    total_page = data.get("totalPage") or 0
                    self.log.emit(f"{label} 第 {page}/{total_page} 页，新增 {len(goods)} 条")
                    self.progress.emit(page, total_page)
                    if page >= total_page:
                        break
                    page += 1

    def _fetch_page_retry(self, page, sid, status, attempts: int = 3):
        """列表分页请求；失败重试，避免单页偶发失败丢掉后面（含公示）的数据。"""
        for i in range(attempts):
            if self._cancel:
                return None
            try:
                return self.api.fetch_list_page(page=page, server_id=sid,
                                                job=self.job, status=status)
            except Exception as e:  # noqa: BLE001
                self.log.emit(f"列表请求失败(第{page}页 {i + 1}/{attempts}): {e}")
                time.sleep(1.0 * (i + 1))
        return None

    # ---------- 详情 ----------
    def _crawl_details(self):
        scope = self.server_ids or None
        if self.force_detail:
            self.db.reset_details(scope)
        pending = self.db.pending_details(scope)
        total = len(pending)
        if total == 0:
            self.log.emit("详情已是最新，无需抓取")
            self.progress.emit(0, 0)
            return
        self.log.emit(f"待抓详情 {total} 条，并发 {self.concurrency}")
        self.progress.emit(0, total)
        done = 0
        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            futures = {ex.submit(self._fetch_one, code): code for code in pending}
            for fut in as_completed(futures):
                if self._cancel:
                    ex.shutdown(wait=False, cancel_futures=True)
                    break
                code = futures[fut]
                done += 1
                try:
                    fut.result()
                except Exception as e:  # noqa: BLE001
                    self.log.emit(f"详情失败 {code}: {e}")
                if done % 5 == 0 or done == total:
                    self.progress.emit(done, total)
        self.progress.emit(done, total)

    def _fetch_one(self, goods_code: str):
        html = self.api.fetch_detail_html(goods_code)
        attrs = parse_detail(html)
        tags = parse_equipment(html)
        self.db.save_attrs(goods_code, attrs, tags)
