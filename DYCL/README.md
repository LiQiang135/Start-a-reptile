# DYCL-多语言处理项目接手指南

## 一、项目是什么

一个多语言新闻网站爬虫系统（Python），从约10个藏语/中文/英文新闻网站抓取文章，做语言检测、编码检查、质量验证后导出JSON/CSV。根目录的“需要爬取的网站.txt”列出了需求方给的33个目标网站（第一批），目前系统只覆盖了其中一部分。

## 二、目录结构

- docs\ —— 已生成的项目文档（架构、配置、模块、数据四份说明）
- scraper\ —— 核心代码（Python爬虫）
  - main.py：调度入口，支持命令行参数 --sites / --max
  - config.py：站点配置（注意：文件末尾不完整，见下方注意事项）
  - base.py：基类，封装HTTP请求、编码检测、去噪提取、SQLite存储、去重
  - rss_crawler.py：RSS策略爬虫
  - html_crawler.py：HTML直接解析爬虫
  - wayback_crawler.py：Wayback Machine存档爬虫（最大文件，344行）
  - playwright_crawler.py：Playwright动态渲染爬虫
  - export_data.py：导出工具，含简单语言检测
  - check_tibetan_urls.py、gen_config.py：辅助小工具
  - data\：数据存储
    - articles.db：SQLite数据库（当前共76篇文章）
    - 各站点子目录：每篇文章一个JSON，按url哈希命名
    - export\：按语言分目录导出（tibetan/chinese/english/other）
- gen_docs.py、gen_report.py：自动生成docs和项目报告的脚本
- 其他\：合同模板、设备登记表等行政文档
- 需要爬取的网站.txt：目标网站清单（需求输入）
- 1.DYCL-多语言处理.zip：项目打包副本

## 三、核心设计

1. 四种爬取策略：config.py里每个站点用strategy字段指定，main.py的STRATEGY_MAP负责分发。rss是解析feed获取文章列表再抓全文；html是直接解析列表页和详情页；wayback是通过web.archive.org抓已下线或被墙的站点；playwright是渲染JS后再抓。

2. 数据流：config.py到main.py到策略爬虫再到base.py统一存储。每篇文章存入SQLite的articles表（字段包括site、url、url_hash、title、author、published、scraped_at、content、raw_html、summary），用url的sha256前16位去重；同时写一份JSON到data目录下对应站点文件夹。

3. base.py亮点：
- 编码检测优先级是HTTP头charset、HTML meta、apparent_encoding、utf-8依次回退，并修复了chardet把UTF-8误判为ISO-8859-1的常见问题

- 内容提取有去噪逻辑，剔除导航、侧栏、广告、评论等噪音元素，多CSS选择器回退，最终回退到收集所有p标签

- 代理地址硬编码为 http://127.0.0.1:7897（Clash），用于访问被墙的web.archive.org，换机器必须改这里
4. export_data.py：按Unicode字符范围统计做语言分类，藏文字符超过50判为tibetan，汉字超过50判为chinese，字母超过200判为english，其余为other。导出总表加按语言分目录的JSON和CSV，CSV用utf-8-sig编码方便Excel打开。

## 四、当前数据状态（实测）

- tibetpost 23篇、xizangzhiye 19篇、phayul 10篇、tibetnet 10篇、dalailamaworld 5篇、shambalanews 5篇、tibetanparliament 2篇、vot 2篇，合计76篇。
- data\export下已有tibetan、chinese、english、other四个语言目录的导出文件。
- 对比配置中每站上限500
