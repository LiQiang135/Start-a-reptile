import requests, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
H = {"User-Agent": "Mozilla/5.0"}
SITES = [
 "http://www.thetibetpost.com","http://www.phayul.com","http://www.dalailamaworld.com",
 "http://xizang-zhiye.org","https://www.vot.org","https://tibetanparliament.org",
 "http://www.tibetexpress.net","https://studentsforefreetibet.org","https://www.savetibet.org",
 "https://www.tibetsun.com","http://www.freetibet.org","https://www.tibetanreview.net",
 "https://tibettruth.com","http://tibet.net"]