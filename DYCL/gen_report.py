# -*- coding: utf-8 -*-
import os, glob

R = ["# DYCL-多语言处理 项目梳理报告\n\n> 生成时间：2026-08-04\n\n---\n"]

R.append("\n## 一、项目概述\n\n多语言新闻爬虫系统，支持RSS/HTML/Wayback/Playwright四种爬取策略，含语言探测、编码检查、质量验证。\n\n---\n")

R.append("\n## 二、Python文件清单\n\n")
for f in sorted(glob.glob("scraper/*.py")):
    R.append(f"- {os.path.basename(f)}\n")
for f in sorted(glob.glob("*.py")):
    if f != "gen_report.py":
        R.append(f"- {f}\n")

R.append("\n## 三、站点配置\n\n从 scraper/config.py 读取，共10个站点：\n\n")
R.append("| Key | 策略 |\n|-----|------|\n")
import importlib.util
spec = importlib.util.spec_from_file_location("config", "scraper/config.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for k, v in mod.SITES.items():
    R.append(f"| {k} | {v.get('strategy','?')} |\n")

R.append("\n## 四、依赖\n\n")
with open("scraper/requirements.txt", encoding="utf-8") as f:
    for line in f:
        R.append(f"- {line.strip()}\n")

R.append("\n## 五、报告文件\n\n")
for f in sorted(glob.glob("scraper/*.txt")):
    R.append(f"- {os.path.basename(f)}\n")

R.append("\n## 六、数据目录\n\n")
if os.path.isdir("scraper/data"):
    files = os.listdir("scraper/data")
    R.append(f"共 {len(files)} 个文件\n")

with open("项目梳理报告.md", "w", encoding="utf-8") as f:
    f.writelines(R)
print("报告已生成: 项目梳理报告.md")