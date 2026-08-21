# 架构说明

## 爬取策略

系统支持4种爬取策略，由 `config.py` 中每个站点的 `strategy` 字段决定：

| 策略 | 实现文件 | 说明 |
|------|----------|------|
| rss | rss_crawler.py | 解析RSS feed获取文章列表，再抓取全文 |
| html | html_crawler.py | 直接解析HTML页面，提取文章链接和内容 |
| wayback | wayback_crawler.py | 通过Wayback Machine存档抓取（适用于已下线站点） |
| playwright | playwright_crawler.py | 使用Playwright动态渲染JS页面后抓取 |

## 数据流向

```
config.py (站点配置)
    ↓
main.py (调度入口)
    ↓
base.py (BaseCrawler 基类)
    ↓
策略爬虫 (rss/html/wayback/playwright)
    ↓
scraper/data/ (按站点存储)
    ↓
质量检查 (verify_data / verify_quality / check_encoding / find_mojibake)
    ↓
export_data.py (导出)
```

## 全局设置 (BASE_SETTINGS)

| 参数 | 值 | 说明 |
|------|-----|------|
| user_agent | Mozilla/5.0 | HTTP请求头 |
| timeout | 30 | 请求超时(秒) |
| max_retries | 3 | 最大重试次数 |
| max_articles_per_site | 500 | 每站最大文章数 |

## 质量检查流程

1. **check_encoding.py** - 检查文件编码是否正确
2. **find_mojibake.py** - 检测乱码（mojibake）
3. **verify_data.py** - 验证数据完整性
4. **verify_quality.py** - 验证数据质量
5. **check_data.py / check_all_data.py** - 数据检查工具
6. **lang_probe.py** - 语言探测（确认文章语言）

## 基类设计 (base.py)

`BaseCrawler` 是所有爬虫的基类，提供：
- HTTP请求封装（含重试、超时、User-Agent）
- 内容提取（通过CSS选择器）
- 数据存储（按站点目录）
- 延时控制（避免请求过快）