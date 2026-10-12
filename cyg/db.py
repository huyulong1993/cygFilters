"""SQLite 存储层。"""
import sqlite3
import threading
from typing import Dict, List, Optional

from . import config
from .parser import to_number

_SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    goods_code   TEXT PRIMARY KEY,
    name         TEXT,
    title        TEXT,
    job          TEXT,
    price        REAL,
    server_id    TEXT,
    image        TEXT,
    web_status   INTEGER,
    listed_time  TEXT,
    offline_time TEXT,
    detail_ok    INTEGER DEFAULT 0,
    equip_tags   TEXT DEFAULT '',
    updated_at   TEXT
);
CREATE TABLE IF NOT EXISTS attrs (
    goods_code TEXT,
    name       TEXT,
    num        REAL,
    raw        TEXT,
    PRIMARY KEY (goods_code, name)
);
CREATE INDEX IF NOT EXISTS idx_attrs_name ON attrs(name, num);
CREATE INDEX IF NOT EXISTS idx_roles_server ON roles(server_id);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


class Db:
    def __init__(self, path=config.DB_PATH):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(_SCHEMA)
            cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(roles)")]
            if "equip_tags" not in cols:
                self.conn.execute(
                    "ALTER TABLE roles ADD COLUMN equip_tags TEXT DEFAULT ''")
            self.conn.commit()

    # ---------- 写入 ----------
    def upsert_roles(self, goods_items: List[dict]) -> None:
        """写入/更新角色基础信息（来自列表接口）。"""
        rows = []
        for g in goods_items:
            image = g.get("middleImage") or g.get("smallImage") or ""
            rows.append((
                str(g.get("goodsCode")),
                g.get("goodsName") or "",
                g.get("title") or "",
                g.get("job") or "",
                g.get("price"),
                str(g.get("serverId") or ""),
                image,
                g.get("webStatus"),
                g.get("saleTime") or g.get("createTime") or "",
                g.get("offlineTime") or "",
            ))
        with self._lock:
            self.conn.executemany(
                """INSERT INTO roles
                   (goods_code,name,title,job,price,server_id,image,web_status,
                    listed_time,offline_time,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
                   ON CONFLICT(goods_code) DO UPDATE SET
                     name=excluded.name, title=excluded.title, job=excluded.job,
                     price=excluded.price, server_id=excluded.server_id,
                     image=excluded.image, web_status=excluded.web_status,
                     listed_time=excluded.listed_time,
                     offline_time=excluded.offline_time,
                     updated_at=datetime('now','localtime')""",
                rows,
            )
            self.conn.commit()

    def save_attrs(self, goods_code: str, attrs: Dict[str, str],
                   equip_counts: Optional[Dict[str, int]] = None) -> None:
        rows = [(goods_code, k, to_number(v), str(v)) for k, v in attrs.items()]
        tags = ",".join(f"{k}:{v}" for k, v in (equip_counts or {}).items())
        with self._lock:
            self.conn.execute("DELETE FROM attrs WHERE goods_code=?", (goods_code,))
            self.conn.executemany(
                "INSERT OR REPLACE INTO attrs (goods_code,name,num,raw) VALUES (?,?,?,?)",
                rows,
            )
            self.conn.execute(
                "UPDATE roles SET detail_ok=1, equip_tags=?, "
                "updated_at=datetime('now','localtime') WHERE goods_code=?",
                (tags, goods_code),
            )
            self.conn.commit()

    def reset_details(self, server_ids: Optional[List[str]] = None) -> None:
        """把范围内角色的详情标记为待抓取（用于强制刷新）。"""
        with self._lock:
            if server_ids:
                marks = ",".join("?" * len(server_ids))
                self.conn.execute(
                    f"UPDATE roles SET detail_ok=0 WHERE server_id IN ({marks})",
                    server_ids,
                )
            else:
                self.conn.execute("UPDATE roles SET detail_ok=0")
            self.conn.commit()

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)", (key, value))
            self.conn.commit()

    def get_meta(self, key: str, default=None):
        with self._lock:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    # ---------- 查询 ----------
    def pending_details(self, server_ids: Optional[List[str]] = None) -> List[str]:
        sql = "SELECT goods_code FROM roles WHERE detail_ok=0"
        params: list = []
        if server_ids:
            sql += " AND server_id IN (%s)" % ",".join("?" * len(server_ids))
            params = list(server_ids)
        with self._lock:
            return [r["goods_code"] for r in self.conn.execute(sql, params)]

    def count_roles(self, server_ids: Optional[List[str]] = None) -> int:
        sql = "SELECT COUNT(*) AS c FROM roles"
        params: list = []
        if server_ids:
            sql += " WHERE server_id IN (%s)" % ",".join("?" * len(server_ids))
            params = list(server_ids)
        with self._lock:
            return self.conn.execute(sql, params).fetchone()["c"]

    def detail_progress(self, server_ids: Optional[List[str]] = None):
        """返回 (已抓详情数, 范围内总数)。"""
        where, params = "", []
        if server_ids:
            where = " WHERE server_id IN (%s)" % ",".join("?" * len(server_ids))
            params = list(server_ids)
        with self._lock:
            total = self.conn.execute(
                "SELECT COUNT(*) AS c FROM roles" + where, params).fetchone()["c"]
            done = self.conn.execute(
                "SELECT COUNT(*) AS c FROM roles" + where +
                (" AND " if where else " WHERE ") + "detail_ok=1",
                params).fetchone()["c"]
        return done, total

    def load_all(self) -> List[dict]:
        """加载全部角色 + 属性，供本地筛选。"""
        with self._lock:
            roles = [dict(r) for r in self.conn.execute("SELECT * FROM roles")]
            attr_rows = list(self.conn.execute(
                "SELECT goods_code, name, num, raw FROM attrs"))
        by_code: Dict[str, dict] = {}
        for a in attr_rows:
            by_code.setdefault(a["goods_code"], {})[a["name"]] = {
                "num": a["num"], "raw": a["raw"]}
        for role in roles:
            role["attrs"] = by_code.get(role["goods_code"], {})
            counts: Dict[str, int] = {}
            for part in (role.get("equip_tags") or "").split(","):
                if not part:
                    continue
                tag, _, n = part.partition(":")
                counts[tag] = int(n) if n.isdigit() else 1
            role["equip_counts"] = counts
        return roles

    def prune_roles(self, server_ids: Optional[List[str]] = None,
                    job_name: Optional[str] = None,
                    keep_codes=()) -> int:
        """删除范围内、已不在列表中的角色（已下架/已售），并清理其属性。

        仅在抓到非空列表后调用，避免误删。
        """
        keep = [str(c) for c in keep_codes]
        if not keep:
            return 0
        with self._lock:
            self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS _keep(code TEXT PRIMARY KEY)")
            self.conn.execute("DELETE FROM _keep")
            self.conn.executemany("INSERT OR IGNORE INTO _keep(code) VALUES (?)",
                                  [(c,) for c in keep])
            where, params = [], []
            if server_ids:
                where.append("server_id IN (%s)" % ",".join("?" * len(server_ids)))
                params += list(server_ids)
            if job_name:
                where.append("job=?")
                params.append(job_name)
            cond = (" AND " + " AND ".join(where)) if where else ""
            cur = self.conn.execute(
                "DELETE FROM roles WHERE goods_code NOT IN (SELECT code FROM _keep)" + cond,
                params)
            deleted = cur.rowcount
            self.conn.execute(
                "DELETE FROM attrs WHERE goods_code NOT IN (SELECT goods_code FROM roles)")
            self.conn.commit()
            return deleted
