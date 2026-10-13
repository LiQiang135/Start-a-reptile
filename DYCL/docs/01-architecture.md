# 架构说明

> 核对日期：2026-10-12。

## 调度与数据流

```text
config.py / SITES
    ↓
main.py / STRATEGY_MAP
    ↓
策略模块 crawl_site(site_key, max_articles)
    ↓
base.py / save_article（SQLite + 逐篇 JSON）
    ↓
export_data.py（读取 SQLite、正文清洗、空正文过滤）
    ↓
lang_probe.py / detect_language
    ↓
data/export/（总表与按语言分组的 JSON、CSV）
```

`base.py` 是公共函数模块，各策略调用统一的存储、去重和提取函数；Playwright 自行通过浏览器获取页面。

## 五种策略

| 策略 | 模块 | 当前实现 |
| --- | --- | --- |
| `rss` | `rss_crawler.py` | 解析 RSS/Atom；优先使用可信的 feed 全文，否则请求详情页；清理 WordPress 摘录样板和分享文案 |
| `html` | `html_crawler.py` | 扫描首页及固定栏目路径，按 URL 模式筛选文章，解析标题、作者、日期和正文 |
| `wayback` | `wayback_crawler.py` | 使用 CDX 搜索与快照接口；CDX 无结果时回退到存档首页发现链接 |
| `playwright` | `playwright_crawler.py` | Chromium 无头浏览器渲染首页及详情页，再交给公共提取函数 |
| `html_bo` | `html_crawler_bo.py` | 按藏文主分类、子分类和文章三级路径发现链接，支持子分类分页、列表作者及日期提取 |

`main.py` 按配置顺序串行执行，单站异常被捕获后继续下一站；未知站点键会打印提示并跳过，未知策略会回退到普通 HTML 模块。

RSS 默认最多翻 10 页，连续 2 页没有新增保存记录会停止。普通 HTML 的候选链接默认上限为 100，入口的 `--max` 不会提高这个候选上限。`html_bo` 默认每个子分类最多扫描 8 页，发现候选上限为本次保存上限的 2 倍；当前分类列表为空，发现过程不会扫描任何分类。

## 请求、编码与提取

`base.fetch_html()` 使用 `requests.get()`，默认超时 30 秒，跟随重定向并检查 HTTP 状态。编码优先级为 HTTP charset、HTML 前 4 KB 的 meta charset、`apparent_encoding`、UTF-8；若 ISO-8859-1/Latin-1 检测结果实际可按 UTF-8 解码，则改用 UTF-8。解码失败字符使用替换字符处理。

公共请求及 Wayback API 显式使用 `base.PROXIES`，地址为 `http://127.0.0.1:7897`。Playwright 的浏览器启动没有显式设置代理，页面超时为 60 秒。公共请求函数没有统一重试循环；Wayback 的 `cdx_search()` 自带重试逻辑。

`extract_text()` 依次尝试配置的 CSS 选择器，删除导航、侧栏、评论、广告等噪音，再回退到段落或 body 文本。清理会修改传入的解析树。各策略通常拒绝少于 50 字符的正文，RSS 另外过滤仅含摘录样板的内容；这不能替代完整的数据质量审计。

## 存储与去重

URL 的 SHA-256 前 16 位作为 `url_hash`；数据库对此字段设置全局唯一约束，去重跨站点键生效，不做 URL 规范化。不同语言版本或别名若得到相同 URL，会共享去重结果。

`save_article()` 先以 `INSERT OR IGNORE` 写数据库，再写站点目录内的 JSON，已存在 JSON 不覆盖；两次写入并非一个原子事务，也不提供历史数据更新机制。正文和元数据更正后，重跑爬虫通常不会刷新旧记录。数据库与 JSON 的 `scraped_at` 分别生成，可能存在微小差异。


