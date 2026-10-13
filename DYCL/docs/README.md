# DYCL 项目文档

> 最后核对：2026-10-12。以本地源码和数据为依据，未重新验证外部站点连通性。

当前项目包含 33 个站点配置条目、5 种采集策略和 12 个 `scraper/` 顶层 Python 文件。数据库有 737 篇文章；已有导出有 735 篇，过滤了 2 篇空正文记录。逐篇 JSON 有 832 份，其中 95 份未进入数据库。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [项目 README](../README.md) | 项目状态、安装运行、接手事项 |
| [01-architecture.md](01-architecture.md) | 策略调度、请求与提取、去重、运行限制 |
| [02-config.md](02-config.md) | 全部 33 个配置条目、参数生效情况、需求覆盖 |
| [03-modules.md](03-modules.md) | 当前实际存在的模块和生成工具 |
| [04-data.md](04-data.md) | 数据库结构、逐站数量、导出分类和一致性 |

## 快速上手

从 `DYCL` 目录运行，需 Python 3.10+：

```powershell
cd scraper
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py --sites phayul tibettimes --max 20
python export_data.py
```

依赖文件列出 `requests>=2.28.0`、`beautifulsoup4>=4.11.0`、`lxml>=4.9.0`、`playwright>=1.40.0`。浏览器采集另需 Chromium。

先确认请求代理 `127.0.0.1:7897` 可用。`html_bo` 当前分类为空，需要补充后才能发现文章。配置数量、历史数据量和当前站点可用性是不同指标，具体限制见各专题文档。

