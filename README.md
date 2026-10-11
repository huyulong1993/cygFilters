# 畅易阁角色筛选器（新水浒Q传）

一个用于 **畅易阁（cyg.changyou.com）** 的桌面版角色筛选工具。针对《新水浒Q传》角色，
支持按大区/职业批量拉取角色数据后，在本地做**多维度数值区间筛选**，弥补官网只能设「≥下限」的不足。

> 技术栈：Python + PySide6 + SQLite　|　打包：PyInstaller（单文件 exe）

---

## 功能特性

- **批量拉取**：按大区（可「全部大区」）+ 职业拉取角色，列表与详情分离抓取，支持增量/断点续抓
- **数值区间筛选**：装备总评分、铭石/星石总等级、抗性、各类积分、等级、力量… 支持 `min–max`
  （官网数值项只能填下限，不支持下限+上限组合）
- **属性模糊搜索**：属性太多时，输入关键词（如「评分」「抗性」「积分」）快速过滤出目标属性项
- **多选筛选**：职业多选、区服（serverId）多选
- **其他筛选**：关键词（角色名）、价格区间
- **卡片展示**：大区、等级、生命值、攻击力、精神力、灵巧、VIP等级、装备总评分、铭石总等级、星石总等级
- **一键跳转**：点击卡片用系统默认浏览器打开详情页购买
- **排序**：默认「价格 低→高」，可切换价格/上架时间/任意属性
- **本地缓存**：抓取结果存本地 SQLite，图片本地缓存

---

## 运行环境

- Windows
- Python 3.10+（开发环境为 3.13）

依赖见 [`requirements.txt`](requirements.txt)：`PySide6-Essentials`、`requests`

---

## 快速开始（源码运行）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

---

## 打包成 exe

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller 畅易阁角色筛选器.spec
# 产物：dist\畅易阁角色筛选器.exe（单文件，免安装）
```

打包配置见 [`畅易阁角色筛选器.spec`](畅易阁角色筛选器.spec)（已排除 Qt WebEngine/Quick/3D 等未用模块以减小体积）。

---

## 使用说明

1. 顶部选择「大区」（默认全部大区）与「职业」
2. 点击 **拉取 / 更新数据**，等待进度条完成
3. 在左侧面板筛选：关键词 / 价格 / 职业 / 区服 / 角色属性区间 / 排序
4. 点击卡片 → 浏览器打开详情页

> 未抓取详情的角色，其数值属性会显示为 `-`。首次使用需先拉取。

---

## 数据来源

| 用途 | 接口 |
|---|---|
| 角色列表 | `POST http://cyg.changyou.com/list/filterSortGoods.json` |
| 区服列表 | `GET  http://cyg.changyou.com/gameServer.json?gameId=16` |
| 角色详情 | `GET  http://public.npt.changyou.com/details/16/{goodsCode}.html`（静态页，无需登录） |

- 装备总评分、铭石/星石总等级等数值属性**只存在于详情页**，因此区间筛选依赖抓取详情。
- 详情页约 **160–440 KB/条**；全大区角色约 2900 条，**首次全量约 1 GB+ 流量、耗时较长**。
  建议先按单个大区拉取，数据会本地缓存并增量更新。

---

## 数据目录

| 运行方式 | 数据位置 |
|---|---|
| 源码运行 | 项目根目录 `data/` |
| 打包 exe | exe 同级目录 `data/` |

`data/` 内含 `cyg.db`（SQLite）与图片缓存。**移动 exe 时请连同 `data/` 一起移动**，否则会新建空数据目录。

---

## 项目结构

```
main.py                  程序入口
cyg/
  config.py              全局配置与常量
  api.py                 畅易阁接口封装（列表 / 区服 / 详情）
  parser.py              角色详情 HTML 解析
  db.py                  SQLite 存储层
  crawler.py             爬虫线程（列表分页 + 并发抓详情）
  filters.py             本地筛选与排序
  imageloader.py         异步图片加载
  ui/
    main_window.py       主窗口
    filter_panel.py      左侧筛选面板
    card_list.py         卡片列表
    card.py              角色卡片
requirements.txt
畅易阁角色筛选器.spec      PyInstaller 打包配置
```

---

## 免责声明

本工具仅供个人学习与查询使用，请合理控制抓取频率、避免对目标站点造成压力；
数据版权归畅易阁 / 畅游所有。
