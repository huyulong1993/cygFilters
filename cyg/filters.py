"""本地筛选与排序。"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class FilterState:
    keyword: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    jobs: set = field(default_factory=set)          # 空 = 不限
    servers: set = field(default_factory=set)       # server_id 集合，空 = 不限
    ranges: Dict[str, Tuple[Optional[float], Optional[float]]] = field(default_factory=dict)
    sort_key: str = "price"                         # role 字段或属性名
    sort_desc: bool = False
    # 需命中数值属性的角色才保留（用于“已抓详情”优先）

    def is_active(self) -> bool:
        return bool(self.keyword or self.price_min is not None
                    or self.price_max is not None or self.jobs or self.ranges)


def _attr_num(role: dict, name: str) -> Optional[float]:
    a = role.get("attrs", {}).get(name)
    return a["num"] if a else None


def apply_filter(roles: List[dict], state: FilterState) -> List[dict]:
    out = []
    kw = state.keyword.strip().lower()
    for r in roles:
        if kw and kw not in (r.get("name") or "").lower():
            continue
        price = r.get("price")
        if state.price_min is not None and (price is None or price < state.price_min):
            continue
        if state.price_max is not None and (price is None or price > state.price_max):
            continue
        if state.jobs and (r.get("job") or "") not in state.jobs:
            continue
        if state.servers and str(r.get("server_id") or "") not in state.servers:
            continue
        ok = True
        for name, (lo, hi) in state.ranges.items():
            if lo is None and hi is None:
                continue
            v = _attr_num(r, name)
            if v is None or (lo is not None and v < lo) or (hi is not None and v > hi):
                ok = False
                break
        if ok:
            out.append(r)

    key = state.sort_key
    if key == "offline_time":
        out.sort(key=lambda r: (r.get("offline_time") or ""), reverse=state.sort_desc)
    elif key == "price":
        out.sort(key=lambda r: (r.get("price") is None, r.get("price") or 0),
                 reverse=state.sort_desc)
    else:  # 数值属性
        out.sort(key=lambda r: (_attr_num(r, key) is None, _attr_num(r, key) or 0),
                 reverse=state.sort_desc)
    return out
