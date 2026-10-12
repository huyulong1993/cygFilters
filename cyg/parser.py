"""解析角色详情 HTML，抽取属性键值。"""
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from . import config

_NUM_RE = re.compile(r"-?\d[\d,，]*\.?\d*")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# 装备条：data-info="{name: '...', ..., type: '..', ...}"
_INFO_RE = re.compile(r'data-info="\{(.*?)\}"', re.S)
_NAME_RE = re.compile(r"name:\s*'([^']*)'")
_TYPE_RE = re.compile(r"\btype:\s*'([^']*)'")


def _strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s)


def _norm_key(key: str) -> str:
    key = _strip_tags(key)
    key = _WS_RE.sub(" ", key).strip()
    key = key.strip("：: ").replace("?", "").strip()
    return key


def _norm_val(val: str) -> str:
    return _WS_RE.sub(" ", _strip_tags(val)).strip()


def to_number(value) -> Optional[float]:
    """抽取数值。

    形如 '133,731' / 'LV6' / '75%' / '6级' 取第一个数值；
    形如 '1000/20000'（当前/最大）取「/」后的最大值。
    """
    if value is None:
        return None
    s = str(value).replace(" ", "")
    nums = _NUM_RE.findall(s)
    if not nums:
        return None
    raw = nums[-1] if "/" in s else nums[0]
    try:
        return float(raw.replace(",", "").replace("，", ""))
    except ValueError:
        return None


class _PairParser(HTMLParser):
    """按文档顺序抽取 .key / .value 元素文本（支持 value 内嵌在 key 中）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events: List[Tuple[str, str]] = []
        self._stack: List[Tuple[str, List[str]]] = []

    @staticmethod
    def _kind(cls: str) -> Optional[str]:
        parts = (cls or "").split()
        if "key" in parts:
            return "key"
        if "value" in parts:
            return "value"
        return None

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        kind = self._kind(cls)
        if kind:
            self._stack.append((kind, []))

    def handle_endtag(self, tag):
        if self._stack:
            kind, buf = self._stack.pop()
            self.events.append((kind, "".join(buf)))

    def handle_data(self, data):
        if self._stack:
            self._stack[-1][1].append(data)


def parse_detail(html: str) -> dict:
    """解析详情页「角色」分页，返回 {属性名: 原始值字符串}。

    只取第一个 m-intro-content（角色），避免混入召唤兽/坐骑等同名属性。
    """
    # 角色分页是第一个 m-intro-content 容器（注意与 m-intro-contents 外层区分）
    m = re.search(r'class="m-intro-content(?:"|\s)', html)
    if not m:
        return {}
    start = html.find(">", m.start()) + 1
    nxt = html.find('class="m-intro-content', start)
    block = html[start: nxt if nxt != -1 else len(html)]

    parser = _PairParser()
    parser.feed(block)
    events = parser.events

    attrs = {}

    def add(key_text: str, val_text: str):
        key = _norm_key(key_text)
        val = _norm_val(val_text)
        if key and val and key not in attrs:
            attrs[key] = val

    i = 0
    while i < len(events):
        kind, text = events[i]
        if kind == "key":
            if i + 1 < len(events) and events[i + 1][0] == "value":
                add(text, events[i + 1][1])
                i += 2
                continue
            i += 1
        else:  # value 在前（键内嵌值的写法）
            if i + 1 < len(events) and events[i + 1][0] == "key":
                add(events[i + 1][1], text)
                i += 2
                continue
            i += 1
    return attrs


def _equipment_section(html: str) -> str:
    """截取「装备」页签内容（到下一个页签为止）。"""
    i = html.find(">装备</h4>")
    if i == -1:
        return ""
    j = html.find('<div class="m-intro-content', i)
    return html[i: j if j != -1 else len(html)]


def parse_equipment(html: str) -> Dict[str, int]:
    """解析角色装备，返回 {装备标签: 件数}（如 {'至尊武器': 1, '神佑防具': 3}）。

    仅统计 武器 / 项链 / 戒指 / 防具(头·衣服·护腕·鞋·腰带) 中，
    名字含「至尊」或「神佑」的装备件数。
    """
    section = _equipment_section(html)
    if not section:
        return {}
    counts: Dict[str, int] = {}
    for m in _INFO_RE.finditer(section):
        body = m.group(1)
        nm = _NAME_RE.search(body)
        tp = _TYPE_RE.search(body)
        if not nm or not tp:
            continue
        name = nm.group(1)
        group = config.EQUIP_SLOT_TYPES.get(tp.group(1))
        if not group:
            continue
        if "至尊" in name:
            tag = "至尊" + group
        elif "神佑" in name:
            tag = "神佑" + group
        else:
            continue
        counts[tag] = counts.get(tag, 0) + 1
    return counts
