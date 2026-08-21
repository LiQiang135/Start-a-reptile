# -*- coding: utf-8 -*-
"""Generate docs files to avoid content truncation."""
import os

# Write 02-config.md directly
with open("docs/02-config.md", "w", encoding="utf-8") as f:
    f.write("# Site Config\n\n")
    f.write("See scraper/config.py for full details.\n\n")
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", "scraper/config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    strategies = {}
    for k, v in mod.SITES.items():
        s = v.get("strategy", "?")
        strategies.setdefault(s, []).append((k, v.get("name", k), v.get("base_url", "")))
    for s in ["rss", "html", "wayback", "playwright"]:
        if s in strategies:
            f.write(f"\n## {s.upper()} ({len(strategies[s])})\n\n")
            f.write("| Key | Name | URL |\n|-----|------|-----|\n")
            for k, n, u in strategies[s]:
                f.write(f"| {k} | {n} | {u} |\n")

# Write 03-modules.md
with open("docs/03-modules.md", "w", encoding="utf-8") as f:
    f.write("# Modules\n\n")
    modules = [
        ("main.py", "Entry point, orchestrates crawlers"),
        ("config.py", "Site configuration (10 sites)"),
        ("base.py", "BaseCrawler class"),
        ("html_crawler.py", "HTML page parser crawler"),
        ("rss_crawler.py", "RSS feed crawler"),
        ("wayback_crawler.py", "Wayback Machine archive crawler"),
        ("playwright_crawler.py", "Playwright dynamic render crawler"),
        ("export_data.py", "Data export tool"),
        ("verify_data.py", "Data integrity verification"),
        ("verify_quality.py", "Data quality verification"),
        ("check_data.py", "Data check tool"),
        ("check_all_data.py", "Full data check tool"),
        ("check_encoding.py", "Encoding check"),
        ("find_mojibake.py", "Mojibake/garbled text detection"),
        ("lang_probe.py", "Language probe v1"),
        ("lang_probe2.py", "Language probe v2"),
        ("lang_probe3.py", "Language probe v3"),
        ("probe_langs.py", "Language probe tool"),
        ("probe_langs2.py", "Language probe tool v2"),
        ("probe_new_sites.py", "New site accessibility probe"),
        ("gen_config.py", "Config generator"),
        ("gen.py", "General generator script"),
        ("debug_sft.py", "SFT site debug tool"),
        ("_db_query.py", "Database query tool"),
    ]
    f.write("| File | Function |\n|------|----------|\n")
    for name, desc in modules:
        f.write(f"| {name} | {desc} |\n")

# Write 04-data.md
with open("docs/04-data.md", "w", encoding="utf-8") as f:
    f.write("# Data Directory\n\n")
    f.write("Path: `scraper/data/`\n\n")
    f.write("## Structure\n\n")
    if os.path.isdir("scraper/data"):
        items = sorted(os.listdir("scraper/data"))
        f.write("| Item | Type | Description |\n|------|------|-------------|\n")
        for item in items:
            path = os.path.join("scraper/data", item)
            if os.path.isdir(path):
                count = len(os.listdir(path))
                f.write(f"| {item}/ | dir | Site data ({count} items) |\n")
            else:
                size = os.path.getsize(path)
                f.write(f"| {item} | file | {size} bytes |\n")

print("All docs generated successfully.")