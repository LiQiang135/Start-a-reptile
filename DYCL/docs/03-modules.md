# 模块清单

> 核对日期：2026-10-12。`scraper/` 顶层实际有 12 个 `.py` 文件。

## 当前模块

| 文件（相对 scraper/） | 职责与状态 |
| --- | --- |
| `main.py` | CLI 与串行调度；注册 5 种策略，`--max` 实际默认 150 |
| `config.py` | 当前 33 个站点条目和未接入执行链的 `BASE_SETTINGS` |
| `base.py` | 数据库初始化、URL 哈希去重、SQLite/JSON 保存、HTTP 请求、编码检测、正文去噪、等待；没有 `BaseCrawler` 类 |
| `rss_crawler.py` | RSS/Atom 解析、WordPress feed 分页、feed 全文可信度判断、详情回退与样板清理 |
| `html_crawler.py` | 固定栏目扫描、文章链接过滤、标题/日期/作者/正文提取；AFP 专用流程只发现首页新闻卡片，校验文章模板并提取 `.afp-story-page__body`，不扫描服务页或猜测栏目 |
| `html_crawler_bo.py` | 藏文路径 CMS 的分类分页、站点 profile、作者和日期提取；当前分类列表为空 |
| `wayback_crawler.py` | Wayback CDX/快照发现与抓取、存档首页回退 |
| `playwright_crawler.py` | Chromium 动态渲染和文章提取；同域文章路径筛选、HTTP 状态及重定向检查、严格正文容器提取。RFI 仅接受中文日期标题路径，排除年月归档；需另装浏览器 |
| `export_data.py` | 读取 SQLite，正文清洗、空正文过滤、调用语言检测、导出总表与语言分组 |
| `lang_probe.py` | Unicode 字符统计与语言分类 CLI，返回 chinese/english/tibetan/other |
| `gen_config.py` | 根据内置站点元组和策略默认选择器生成当前工作目录的 config.py |
| `check_tibetan_urls.py` | 定义请求库、代理、请求头和地址列表；目前没有请求循环或检测输出，地址也需核对 |

## 辅助文件

| 文件或目录（相对 DYCL/） | 说明 |
| --- | --- |
| `scraper/requirements.txt` | 4 项 Python 依赖；Chromium 需单独安装 |
| `scraper/tmp/` | 临时 live probe、正文/日期/去噪检查脚本和 HTML 样本，部分脚本会联网；不是统一测试入口 |
| `scraper/tmp/html_crawler_bo_guide.md` | 藏文 CMS 的补充说明，实际运行规则以当前代码为准 |
| `scraper/wayback_c` | 无扩展名的辅助文件，未被 main.py 注册为策略模块 |
| `gen_docs.py` | 旧文档生成器，覆盖 docs/02-config.md、03-modules.md、04-data.md；硬编码旧模块清单并遗漏 html_bo |
| `gen_report.py` | 旧报告生成器，写出项目梳理报告.md；仍有固定的 2026-08-04 日期、10 站点和 4 策略描述 |
| `需要爬取的网站.txt` | 需求地址清单，含重复地址和后续站点 |
