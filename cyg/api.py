"""畅易阁接口封装。"""
from typing import Iterator, Optional

import requests

from . import config


class CygApi:
    """列表接口 + 区服接口 + 角色详情页。"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Referer": config.BASE_URL + "/list",
        })

    # ---------- 区服 ----------
    def get_servers(self, game_id: int = config.GAME_ID) -> list:
        """返回大区列表：[{id, name, server:[{serverId, name, groupId}]}]"""
        r = self.session.get(
            config.BASE_URL + "/gameServer.json",
            params={"gameId": game_id},
            timeout=20,
        )
        r.raise_for_status()
        return (r.json().get("data") or {}).get("server") or []

    # ---------- 列表 ----------
    def fetch_list_page(
        self,
        page: int = 1,
        page_size: int = config.LIST_PAGE_SIZE,
        server_id: Optional[str] = None,
        job: Optional[int] = None,
        status: Optional[int] = None,
        game_id: int = config.GAME_ID,
        goods_type: int = config.GOODS_TYPE,
        sort: Optional[dict] = None,
    ) -> dict:
        """拉取一页角色列表，返回完整响应 dict。

        status: 1=公示中，2=待售；None=不限定（服务端默认返回两者）。
        """
        filter_list = [
            {"field": "gameId", "value": str(game_id), "type": 1},
            {"field": "goodsType", "value": str(goods_type), "type": 1},
        ]
        game_server = {"gameId": str(game_id)}
        if status is not None:
            filter_list.append({"field": "status", "value": str(status), "type": 1})
        if server_id:
            filter_list.append({"field": "serverId", "value": str(server_id)})
            game_server["serverId"] = str(server_id)
        if job is not None:
            filter_list.append({"field": "job", "value": str(job), "type": 1})

        body = {
            "filterList": filter_list,
            "gameServer": game_server,
            "pageNumber": page,
            "pageSize": page_size,
        }
        if sort:
            body["sort"] = sort

        r = self.session.post(
            config.BASE_URL + "/list/filterSortGoods.json",
            json=body,
            timeout=25,
        )
        r.raise_for_status()
        return r.json()

    def iter_list(
        self,
        server_id: Optional[str] = None,
        job: Optional[int] = None,
        status: Optional[int] = None,
        page_size: int = config.LIST_PAGE_SIZE,
    ) -> Iterator[dict]:
        """分页迭代某个 serverId（或全区）下的全部角色 goods。"""
        page = 1
        while True:
            resp = self.fetch_list_page(page=page, page_size=page_size,
                                        server_id=server_id, job=job,
                                        status=status)
            data = resp.get("data") or {}
            for item in data.get("list") or []:
                goods = item.get("goods")
                if goods:
                    yield goods
            total_page = data.get("totalPage") or 0
            if page >= total_page:
                break
            page += 1

    # ---------- 角色详情 ----------
    def fetch_detail_html(self, goods_code: str,
                          game_id: int = config.GAME_ID) -> str:
        """拉取角色详情静态 HTML（角色属性 / 召唤兽 / 坐骑 / 技能 …）。"""
        url = config.DETAIL_URL.format(game_id=game_id, goods_code=goods_code)
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
