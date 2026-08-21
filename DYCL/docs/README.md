# DYCL-多语言处理 项目文档

> 最后更新：2026-08-04

## 项目简介

多语言新闻爬虫系统，从10个新闻网站抓取文章内容。支持4种爬取策略，含语言探测、编码检查、质量验证等数据质量流程。

## 快速上手

```bash
cd scraper
pip install -r requirements.txt
python main.py
```

## 文档导航

| 文档 | 内容 |
|------|------|
| [01-architecture.md](01-architecture.md) | 架构说明：爬取策略、数据流向、质量检查 |
| [02-config.md](02-config.md) | 站点配置：10个站点详情 |
| [03-modules.md](03-modules.md) | 模块清单：24个Python文件功能说明 |
| [04-data.md](04-data.md) | 数据说明：目录结构、数据库、导出 |

## 依赖

- requests>=2.28.0
- beautifulsoup4>=4.11.0
- lxml>=4.9.0
- playwright>=1.40.0