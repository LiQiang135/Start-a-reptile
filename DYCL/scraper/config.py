BASE_SETTINGS = {"user_agent": "Mozilla/5.0", "timeout": 30, "max_retries": 3, "max_articles_per_site": 500}

SITES = {
    "phayul_bo": {"name": "Phayul Tibetan", "base_url": "https://phayul.com/bo/", "feed_url": "https://phayul.com/bo/feed/", "strategy": "rss", "delay": 2.0, "content_selectors": [".entry-content", "article"]},
    "phayul": {"name": "Phayul", "base_url": "https://phayul.com", "feed_url": "https://phayul.com/feed/", "strategy": "rss", "delay": 2.0, "content_selectors": [".entry-content", "article"]},
    "tibetpost_bo": {"name": "Tibet Post Tibetan", "base_url": "https://www.thetibetpost.com/bo", "strategy": "html", "delay": 2.0, "content_selectors": [".article-content-main", "article"]},
    "tibetpost": {"name": "Tibet Post", "base_url": "https://www.thetibetpost.com", "strategy": "html", "delay": 2.0, "content_selectors": [".article-content-main", "article"]},
    "dalailamaworld": {"name": "Dalai Lama World", "base_url": "http://www.dalailamaworld.com", "strategy": "wayback", "delay": 3.0, "content_selectors": ["#content", ".content"]},
    "xizangzhiye_bo": {"name": "Xizang Zhiye Tibetan", "base_url": "https://xizang-zhiye.org/bo/", "strategy": "wayback", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "xizangzhiye": {"name": "Xizang Zhiye", "base_url": "https://xizang-zhiye.org", "strategy": "wayback", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "vot_bo": {"name": "VOT Tibetan", "base_url": "https://www.vot.org/bo/", "strategy": "playwright", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "vot": {"name": "VOT Chinese", "base_url": "https://www.vot.org/cn/", "strategy": "playwright", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "tibetnet_bo": {"name": "Tibet.net Tibetan", "base_url": "https://tibet.net/bo/", "feed_url": "https://tibet.net/bo/feed/", "strategy": "rss", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "tibetnet": {"name": "Tibet.net", "base_url": "https://tibet.net", "feed_url": "https://tibet.net/feed/", "strategy": "rss", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "tibetanparliament": {"name": "Tibetan Parliament", "base_url": "https://tibetanparliament.org", "strategy": "wayback", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
    "tibetexpress": {"name": "Tibet Express", "base_url": "http://www.tibetexpress.net", "strategy": "wayback", "delay": 3.0, "content_selectors": [".entry-content", "article"]},
}

    # "sft": {"name": "Students for Free Tibet", "base_url": "https://students"},
