# 数据说明

> 本地快照核对日期：2026-10-12。数据库以只读方式查询；未重新采集、合并或导出数据。

## 存储结构

```text
scraper/data/
├── articles.db                    # SQLite，7,884,800 字节
├── <site>/<url_hash>.json          # 逐篇原始采集记录
└── export/
    ├── all_articles.json
    ├── all_articles.csv
    ├── tibetan/all_articles.{json,csv}
    ├── chinese/all_articles.{json,csv}
    ├── english/all_articles.{json,csv}
    └── other/all_articles.{json,csv}
```

数据库共 737 篇、26 个站点键；逐篇 JSON 共 832 份、29 个站点目录。导出目录不计入逐篇 JSON 统计。

## 逐站数量

| 站点键 | 数据库记录 | 逐篇 JSON | 差额（JSON − 数据库） |
| --- | --- | --- | --- |
| `dalailamaworld` | 9 | 9 | 0 |
| `freetibet` | 14 | 14 | 0 |
| `indiatibet` | 12 | 12 | 0 |
| `nalanda` | 20 | 20 | 0 |
| `officeoftibet` | 10 | 36 | 26 |
| `phayul` | 70 | 70 | 0 |
| `sambhota` | 0 | 10 | 10 |
| `savetibet` | 7 | 7 | 0 |
| `sfft` | 10 | 10 | 0 |
| `shambalanews` | 150 | 150 | 0 |
| `sherig` | 72 | 72 | 0 |
| `tchrd` | 10 | 10 | 0 |
| `tibetanparliament` | 2 | 2 | 0 |
| `tibetbureau` | 14 | 14 | 0 |
| `tibetexpress` | 38 | 38 | 0 |
| `tibetgeneva` | 10 | 10 | 0 |
| `tibethouse_jp` | 18 | 18 | 0 |
| `tibetinformation` | 10 | 10 | 0 |
| `tibetnet` | 20 | 20 | 0 |
| `tibetoffice` | 6 | 6 | 0 |
| `tibetpost` | 53 | 53 | 0 |
| `tibetreview` | 20 | 20 | 0 |
| `tibetsun` | 12 | 12 | 0 |
| `tibettimes` | 119 | 119 | 0 |
| `tibettruth` | 10 | 10 | 0 |
| `voachinese` | 0 | 57 | 57 |
| `vot` | 2 | 2 | 0 |
| `vot_bo` | 0 | 2 | 2 |
| `xizangzhiye` | 19 | 19 | 0 |
| **合计** | **737** | **832** | **95** |

全部数据库 URL 哈希都有对应 JSON 文件；另有 95 个 JSON 文件哈希不在数据库中，分别来自 `officeoftibet`（26）、`sambhota`（10）、`voachinese`（57）、`vot_bo`（2）。这里验证的是文件存在与哈希集合，不代表逐篇元数据/正文完全相同；差异形成原因未确定。

## 数据库字段

表名 `articles`，由 `base.init_db()` 创建：

| 字段 | 含义 |
| --- | --- |
| `id` | 自增主键 |
| `site` | 站点键，非空，建有索引 |
| `url` | 原始文章 URL，非空 |
| `url_hash` | URL 的 SHA-256 前 16 位，全局唯一且非空，建有索引 |
| `title`、`author`、`published` | 标题、作者、来源发布时间 |
| `scraped_at` | 抓取时生成的 UTC ISO 时间，非空，未带时区后缀 |
| `content`、`raw_html`、`summary` | 正文、原始 HTML、摘要；raw_html 虽有字段，各策略并不保证保存原页 |

逐篇 JSON 包含 `site`、`url`、`title`、`author`、`published`、`scraped_at`、`content`、`summary`，不包含数据库的 `id`、`url_hash`、`raw_html`。语言标签不在数据库表或逐篇 JSON 保存接口中生成。

本地数据库抓取时间范围为 `2026-08-02T07:19:25.343723` 至 `2026-10-12T06:41:51.601222`（UTC；末条对应北京时间 14:41:51）。来源 `published` 保留各策略提取结果，未统一成一种日期格式。

## 导出行为与当前结果

从 `scraper/` 目录执行 `python export_data.py`。工具仅读取数据库，按 `site, id` 排序，剥离正文 HTML 标签、解码 HTML 实体、压缩空白，过滤清洗后为空的正文，再调用 `lang_probe.detect_language()`。

总表和语言分组同时写 JSON 与 CSV；JSON 使用 UTF-8，CSV 使用 UTF-8 BOM（`utf-8-sig`）。字段为 `id`、`site`、`url`、`title`、`author`、`published`、`content`、`language`、`content_length`；不导出 `raw_html`、`summary`、`scraped_at` 和 `url_hash`。`content_length` 为清洗后字符串的字符数。

| 语言目录 | JSON 篇数 | CSV 数据行数 |
| --- | --- | --- |
| `tibetan` | 341 | 341 |
| `english` | 316 | 316 |
| `chinese` | 28 | 28 |
| `other` | 50 | 50 |
| **总表** | **735** | **735** |

总表 JSON 的本地修改时间为 2026-10-12 14:49:12（北京时间）。核对确认总表 ID 集合与当前数据库清洗后的非空记录一致，总表正文和语言标签符合当前清洗/检测逻辑，各 CSV 行数与 JSON 数量一致。

737 条数据库记录中，`sfft` 的 ID 113、`tibettruth` 的 ID 148 正文为空，因此导出 735 条。95 份仅存在于 JSON 的记录不会自动进入导出。重新导出会覆盖总表及本次出现的语言分组，不会主动清除已无数据的旧语言目录。

## 当前语言检测规则

正文先做 NFC 规范化、去除控制/格式字符，再按 Unicode 范围统计字母。占比的分母是全部字母数量，规则按以下顺序判断：

| 顺序 | 条件 | 返回值 |
| --- | --- | --- |
| 1 | 藏文字母 ≥20 且占比 ≥25% | `tibetan` |
| 2 | 日语假名 ≥10 或占比 ≥8% | `other` |
| 3 | 汉字 ≥30 且占比 ≥35% | `chinese` |
| 4 | 拉丁字母 ≥50 且占比 ≥40% | `english` |
| 5 | 无字母或其他情况 | `other` |

