#!/usr/bin/env python3
"""Generate config.py - run this to regenerate."""

import json
from datetime import datetime

# 源数据：每个元组 = (site_key, site_name, base_url, strategy, delay, feed_url, custom_selectors)
# custom_selectors 为 None 时默认使用 DEFAULT_SELECTORS，否则传入列表覆盖
S = [
    ("phayul_bo", "Phayul Tibetan", "https://phayul.com/bo/", "rss", 2.0, "https://phayul.com/bo/feed/", None),
    ("phayul", "Phayul", "https://phayul.com", "rss", 2.0, "https://phayul.com/feed/", None),
    ("tibetpost_bo", "Tibet Post Tibetan", "https://www.thetibetpost.com/bo", "html", 2.0, None, [".article-content-main", "article"]),
    ("tibetpost", "Tibet Post", "https://www.thetibetpost.com", "html", 2.0, None, [".article-content-main", "article"]),
    ("dalailamaworld", "Dalai Lama World", "http://www.dalailamaworld.com", "wayback", 3.0, None, ["#content", ".content"]),
    ("xizangzhiye_bo", "Xizang Zhiye Tibetan", "https://xizang-zhiye.org/bo/", "wayback", 3.0, None,None),
    ("xizangzhiye", "Xizang Zhiye", "https://xizang-zhiye.org", "wayback", 3.0, None,None),
    ("vot_bo", "VOT Tibetan", "https://www.vot.org/", "playwright", 3.0, None,None),
    ("vot", "VOT Chinese", "https://www.vot.org/cn/", "playwright", 3.0, None,None),
    ("tibetnet_bo", "Tibet.net Tibetan", "https://tibet.net/bo/", "rss", 3.0, "https://tibet.net/bo/feed/", None),
    ("tibetnet", "Tibet.net", "https://tibet.net", "rss", 3.0, "https://tibet.net/feed/", None),
    ("tibetanparliament", "Tibetan Parliament", "https://tibetanparliament.org", "wayback", 3.0, None,None),
    ("tibetexpress", "Tibet Express", "http://www.tibetexpress.net", "wayback", 3.0, None,None),
    ("sfft", "Students for Afree Tibetan", "https://studentsforafreetibet.org", "rss", 2.0, "https://studentsforafreetibet.org/feed",None),
    ("savetibet", "Save Tibetan", "https://www.savetibet.org", "rss", 2.0, "https://www.savetibet.org/feed", None),
    ("freetibet", "Free Tibet", "https://freetibet.org", "html", 2.0, None,None),
    ("tibetreview", "Tibetan Review", "https://www.tibetanreview.net", "rss", 2.0, "https://www.tibetanreview.net/feed", [".td-post-content",".tdb_single_content"]),
    ("tibettruth", "Tibetan Truth", "https://tibettruth.com", "rss", 2.0, "https://tibettruth.com/feed", None),
    ("tchrd","Tibetan Centre for Human Rights and Democracy","http://tchrd.org","rss",2.0,"http://tchrd.org/feed", [".td-post-content",".tdb_single_content"]),
    ("tibetinformation","Tibetan Information Office","http://tibetoffice.com.au","rss",2.0,"http://tibetoffice.com.au/feed",[".main-content",".entry-content"]),
    ("tibetoffice","The office of Tibetan","http://tibetoffice.org","rss",2.0,"http://tibetoffice.org/feed",[".entry",".post-inner"]),
    ("sherig","Department of education","https://sherig.org","rss",2.0,"https://sherig.org/?feed=rss2",[".w-post-elm.post_content",".post_content"]),
    ("indiatibet","India Tibet Coordination office","https://www.indiatibet.net","rss",2.0,"https://www.indiatibet.net/feed",None),
    ("nalanda","Buddhist News Nalanda","https://nalanda.news/","rss",2.0,"https://nalanda.news/rssdzen.xml",None),
    ("tibethouse_jp","Tibet House Japan","https://www.tibethouse.jp/","rss",2.0,"https://www.tibethouse.jp/feed",None),
    ("tibetbureau","Bureau of His Holiness The Dalai Lama","https://tibetbureau.in/","rss",2.0,"https://tibetbureau.in/feed",None),
    ("officeoftibet","Office of Tibet Pretoria","https://officeoftibet.com/","rss",2.0,"https://officeoftibet.com/feed",[".article-contents","article"]),
    ("tibetinf_au","Tibetan Information Office,Australia","http://tibetoffice.com.au/","rss",2.0,"http://tibetoffice.com.au/feed",None),
    ("tibetgeneva","The Tibet Bureau Geneva","https://www.tibetoffice.ch/","rss",2.0,"https://www.tibetoffice.ch/feed",None),
]

# 为不同策略配置默认的 content_selectors
DEFAULT_SELECTORS = {
    "rss": [".entry-content", "article"],
    "html": [".article-content-main", "article"],
    "wayback": ["#content", ".content", ".entry-content", "article"],
    "playwright": [".entry-content", "article", ".content"],
}


def generate_config():
    """生成 config.py 文件"""
    sites = {}

    for item in S:
        # 兼容 6 个或 7 个参数的情况
        if len(item) == 7:
            key, name, base_url, strategy, delay, feed_url, custom_selectors = item
        elif len(item) == 6:
            key, name, base_url, strategy, delay, feed_url = item
            custom_selectors = None
        else:
            raise ValueError(f"Invalid tuple length in S: {item}")

        # 基础配置
        site_config = {
            "name": name,
            "base_url": base_url,
            "strategy": strategy,
            "delay": delay,
        }

        # 添加 feed_url（仅 RSS 策略需要）
        if strategy == "rss" and feed_url:
            site_config["feed_url"] = feed_url

        # 确定 content_selectors 优先级：自定义 -> 策略默认 -> 通用兜底
        if custom_selectors:
            site_config["content_selectors"] = custom_selectors
        else:
            site_config["content_selectors"] = DEFAULT_SELECTORS.get(
                strategy, [".entry-content", "article", ".content"]
            )

        sites[key] = site_config

    base_settings = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "timeout": 30,
        "max_retries": 3,
        "max_articles_per_site": 500,
    }

    with open("config.py", "w", encoding="utf-8") as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""Configuration for all sites. Auto-generated by gen_config.py"""\n')
        f.write(f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')

        f.write("BASE_SETTINGS = ")
        f.write(json.dumps(base_settings, ensure_ascii=False, indent=2))
        f.write("\n\n")

        f.write("SITES = {\n")
        for k, v in sites.items():
            f.write(f'  "{k}": {json.dumps(v, ensure_ascii=False)},\n')
        f.write("}\n")

    print(f"✅ config.py generated successfully with {len(sites)} sites")


if __name__ == "__main__":
    generate_config()