"""全局配置与常量。"""
import sys
from pathlib import Path

APP_NAME = "畅易阁角色筛选器-v0.0.3"

# 目标游戏：新水浒Q传
GAME_ID = 16
GAME_NAME = "新水浒Q传，公众号关注：拙耳"
GOODS_TYPE = 1  # 1 = 角色

BASE_URL = "http://cyg.changyou.com"
PUBLIC_URL = "http://public.npt.changyou.com"

# 角色详情页（静态 HTML，无需登录）
DETAIL_URL = PUBLIC_URL + "/details/{game_id}/{goods_code}.html"

# 数据目录：打包成 exe 后放在 exe 同级目录，源码运行时放在项目根目录
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "cyg.db"
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

LIST_PAGE_SIZE = 20
DETAIL_CONCURRENCY = 5  # 详情页并发数（礼貌抓取）

# 职业（新水浒Q传），来自官方筛选配置
JOB_NAMES = {
    1: "剑客", 2: "武师", 3: "医师", 4: "术士", 5: "道士",
    6: "浪子", 7: "弓手", 8: "禁卫", 9: "墨者", 10: "巫煞",
    11: "魂武", 12: "寒星", 13: "花间舞", 14: "剑九", 15: "魔刀",
}

GENDER_NAMES = {"1": "男", "0": "女"}

# 卡片上展示的属性：(显示名, 属性键, 是否用原始文本)
CARD_FIELDS = [
    ("等级", "等级", False),
    ("生命值", "生命值", False),
    ("攻击力", "攻击力", False),
    ("精神力", "精神力", False),
    ("灵巧", "灵巧度", False),
    ("VIP等级", "VIP等级", True),
    ("装备总评分", "装备总评分", False),
    ("铭石总等级", "铭石总等级", False),
    ("星石总等级", "星石总等级", False),
]

# 筛选面板里优先展示的数值属性（其余属性折叠在“更多属性”里）
FILTER_PRIMARY_ATTRS = [
    "装备总评分", "铭石总等级", "星石总等级", "等级",
    "力量", "体质", "心力", "耐力", "敏捷",
    "攻击力", "防御力", "命中率", "闪避率", "精神力",
    "物理抗性", "法术抗性", "异常抗性",
    "5V5跨服积分", "3V3跨服积分", "连环绝杀积分", "绑定元宝",
]

# 装备筛选：详情页装备条的 type 编码 → 部位大类
# 1=头 2=衣服 3=项链 4=武器 5=戒指 8=腰带 9=鞋 11=护腕
EQUIP_SLOT_TYPES = {
    "1": "防具", "2": "防具", "8": "防具", "9": "防具", "11": "防具",
    "3": "项链", "5": "戒指",
    "4": "武器",
}

# 装备筛选的可选项（前缀 + 部位大类），每项可选「至少 N 件」
EQUIP_TAGS = [
    "至尊武器", "神佑武器",
    "至尊项链", "神佑项链",
    "至尊戒指", "神佑戒指",
    "至尊防具", "神佑防具",
]
EQUIP_MAX_COUNT = 5

