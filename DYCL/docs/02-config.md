# 站点配置

> 核对日期：2026-10-12。实际配置以 `scraper/config.py` 的 `SITES` 为准。

## 配置概况

当前共 33 个站点键：RSS 20、HTML 4、Wayback 6、Playwright 2、html_bo 1。站点键包含语言版本和同站别名，数量不等于独立域名数量。“数据库篇数”为已有本地记录，0 不代表确认站点故障。

## rss（20 个）

| 站点键 | 名称 | 基础地址 | 数据库篇数 |
| --- | --- | --- | --- |
| `phayul_bo` | Phayul Tibetan | `https://phayul.com/bo/` | 0 |
| `phayul` | Phayul | `https://phayul.com` | 70 |
| `tibetnet_bo` | Tibet.net Tibetan | `https://tibet.net/bo/` | 0 |
| `tibetnet` | Tibet.net | `https://tibet.net` | 20 |
| `sfft` | Students for Afree Tibetan | `https://studentsforafreetibet.org` | 10 |
| `savetibet` | Save Tibetan | `https://www.savetibet.org` | 7 |
| `tibetreview` | Tibetan Review | `https://www.tibetanreview.net` | 20 |
| `tibettruth` | Tibetan Truth | `https://tibettruth.com` | 10 |
| `tchrd` | Tibetan Centre for Human Rights and Democracy | `http://tchrd.org` | 10 |
| `tibetinformation` | Tibetan Information Office | `http://tibetoffice.com.au` | 10 |
| `tibetoffice` | The office of Tibetan | `http://tibetoffice.org` | 6 |
| `sherig` | Department of education | `https://sherig.org` | 72 |
| `indiatibet` | India Tibet Coordination office | `https://www.indiatibet.net` | 12 |
| `nalanda` | Buddhist News Nalanda | `https://nalanda.news/` | 20 |
| `tibethouse_jp` | Tibet House Japan | `https://www.tibethouse.jp/` | 18 |
| `tibetbureau` | Bureau of His Holiness The Dalai Lama | `https://tibetbureau.in/` | 14 |
| `officeoftibet` | Office of Tibet Pretoria | `https://officeoftibet.com/` | 10 |
| `tibetinf_au` | Tibetan Information Office,Australia | `http://tibetoffice.com.au/` | 0 |
| `tibetgeneva` | The Tibet Bureau Geneva | `https://www.tibetoffice.ch/` | 10 |
| `tibettimes` | Tibet Times | `https://tibettimes.net` | 119 |

## html（4 个）

| 站点键 | 名称 | 基础地址 | 数据库篇数 |
| --- | --- | --- | --- |
| `tibetpost_bo` | Tibet Post Tibetan | `https://www.thetibetpost.com/bo` | 0 |
| `tibetpost` | Tibet Post | `https://www.thetibetpost.com` | 53 |
| `freetibet` | Free Tibet | `https://freetibet.org` | 14 |
| `voachinese` | Voice of America Chinese | `https://www.voachinese.com` | 0 |

## wayback（6 个）

| 站点键 | 名称 | 基础地址 | 数据库篇数 |
| --- | --- | --- | --- |
| `dalailamaworld` | Dalai Lama World | `http://www.dalailamaworld.com` | 9 |
| `xizangzhiye_bo` | Xizang Zhiye Tibetan | `https://xizang-zhiye.org/bo/` | 0 |
| `xizangzhiye` | Xizang Zhiye | `https://xizang-zhiye.org` | 19 |
| `tibetanparliament` | Tibetan Parliament | `https://tibetanparliament.org` | 2 |
| `tibetexpress` | Tibet Express | `http://www.tibetexpress.net` | 38 |
| `tibetsun` | Tibet Sun | `https://www.tibetsun.com/` | 12 |

## playwright（2 个）

| 站点键 | 名称 | 基础地址 | 数据库篇数 |
| --- | --- | --- | --- |
| `vot_bo` | VOT Tibetan | `https://www.vot.org/` | 0 |
| `vot` | VOT Chinese | `https://www.vot.org/cn/` | 2 |

## html_bo（1 个）

| 站点键 | 名称 | 基础地址 | 数据库篇数 |
| --- | --- | --- | --- |
| `shambalanews` | Shambala News | `http://www.shambalanews.com/` | 150 |

## 参数及生效情况

| 参数 | 当前含义 |
| --- | --- |
| `name` | 日志中的站点名称 |
| `base_url` | 文章发现和相对路径拼接的基础地址 |
| `strategy` | 调度到对应策略模块 |
| `delay` | 站点采集间隔，当前配置为 2 或 3 秒；发现链接时也可能使用模块内固定等待 |
| `feed_url` | RSS 入口；例如 Tibet Times 使用 `/category/news/feed/` |
| `content_selectors` | 正文选择器按顺序回退；`html_bo` profile 可覆盖 |

`BASE_SETTINGS` 声明了 User-Agent、30 秒超时、3 次重试及每站上限 500，但当前模块未读取此字典。实际请求头在 `base.HEADERS` 中，超时由请求函数决定，本次保存上限由 `main.py --max` 决定（默认 150）。

## 配置生成与站点差异

`gen_config.py` 的 `S` 元组列表和 `DEFAULT_SELECTORS` 是生成源。从 `scraper/` 目录执行 `python gen_config.py` 会覆盖当前目录的 `config.py`；修改站点配置时应同步生成源，尤其是自定义正文选择器。

`html_crawler_bo.py` 的 `BO_SITE_PROFILES` 保存藏文 CMS 的分类、正文、日期与作者规则。`shambalanews` profile 的 `categories` 为 `None`，回退到目前为空的 `TIBETAN_CATEGORIES`，因此当前不会发现文章。使用前需填入站点真实分类路径。
