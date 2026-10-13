# DYCL 多语言新闻采集项目

> 状态核对日期：2026-10-12。依据本地代码、SQLite、逐篇 JSON 和已有导出文件；未重新执行联网爬取。

DYCL 使用 Python 采集新闻文章，支持 RSS、HTML、Wayback、Playwright 和藏文路径 CMS（`html_bo`）共 5 种策略。导出时清理正文，并按藏文、中文、英文和其他语言分组。

## 当前状态

| 项目 | 当前结果 |
| --- | --- |
| 站点配置条目 | 33 个：RSS 20、HTML 4、Wayback 6、Playwright 2、html_bo 1 |
| 数据库 | 737 篇，涉及 26 个站点键 |
| 逐篇 JSON | 832 份，涉及 29 个站点目录 |
| 已有导出 | 735 篇：藏文 341、英文 316、中文 28、其他 50 |
| 数据差异 | 95 份 JSON 未进入数据库；2 篇数据库空正文记录被导出过滤 |

配置条目包括语言版本和同站别名，不能当作 33 个独立网站或全部已验证可用。需求清单也包含重复地址，详细配置及采集覆盖见 [站点配置](docs/02-config.md)，数据核对见 [数据说明](docs/04-data.md)。

## 目录结构

```text
DYCL/
├── README.md
├── 需要爬取的网站.txt       # 第一批需求与后续站点，含重复地址
├── docs/                    # 架构、配置、模块、数据说明
├── gen_docs.py              # 旧文档生成器，含过时描述
├── gen_report.py            # 旧报告生成器，含固定日期/旧数量
└── scraper/
    ├── main.py              # 调度入口：--sites / --max
    ├── config.py            # 当前 33 个配置条目
    ├── gen_config.py        # 配置生成源
    ├── base.py              # 请求、编码、提取、存储、去重函数
    ├── rss_crawler.py
    ├── html_crawler.py
    ├── html_crawler_bo.py
    ├── wayback_crawler.py
    ├── playwright_crawler.py
    ├── export_data.py
    ├── lang_probe.py
    ├── check_tibetan_urls.py # 地址清单，尚无实际检查逻辑
    ├── requirements.txt
    ├── tmp/                 # 临时探测/验证脚本及页面样本
    └── data/                # articles.db、站点 JSON、export/
```

完整模块说明见 [模块清单](docs/03-modules.md)。

## 安装与运行

使用 Python 3.10 或更高版本（代码包含 `dict | None` 等类型语法）。以下命令从 `DYCL` 目录执行：

```powershell
cd scraper
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py 
python export_data.py
```

Chromium 用于 Playwright 策略。`python main.py` 会遍历全部配置；`--max` 实际默认值为 **150**，表示本次每站最多新增保存的篇数，并非数据库总量。命令行帮助仍写着默认 50，以代码实际值为准。候选链接和分页限制可能使实际保存数低于上限。

请求函数和 Wayback API 使用硬编码代理 `http://127.0.0.1:7897`，运行前需确保该代理可用或调整代码。Playwright 未显式配置此代理。更多运行行为见 [架构说明](docs/01-architecture.md)。


文档索引：[docs/README.md](docs/README.md)。
