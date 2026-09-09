#!/usr/bin/env python3
"""Export all scraped articles to JSON and CSV formats with language tags."""
import sqlite3
import re
import os
import sys
import json
import csv
import html

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "articles.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "export")


def detect_language(content):
    """Detect the primary language of content."""
    if not content:
        return "unknown"
    tib_chars = len(re.findall(r'[\u0f00-\u0fff]', content))
    chi_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    eng_chars = len(re.findall(r'[a-zA-Z]', content))
    if tib_chars > 50:
        return "tibetan"
    if chi_chars > 50:
        return "chinese"
    if eng_chars > 200:
        return "english"
    return "other"


def clean_and_validate_content(text):
    """清理 HTML 标签并格式化文本"""
    if not text:
        return ""
    # 1. 移除所有 HTML 标签 (如 <p>, <br>, <div> 等)
    text = re.sub(r'<[^>]+>', '', text)
    # 2. 转换 HTML 转义字符 (如 &nbsp; 转换为普通空格, &amp; 转换为 &)
    text = html.unescape(text)
    # 3. 将连续的空白字符（包括换行、制表符）替换为单个空格，并去除首尾空白
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    c = db.cursor()

    # Get all articles
    c.execute("SELECT * FROM articles ORDER BY site, id")
    rows = c.fetchall()

    # Build export data
    articles = []
    invalid_count = 0  # 记录因为正文为空而被过滤的低质量数据

    for row in rows:
        raw_content = row["content"] or ""
        # 首先对正文进行 HTML 标签清洗
        cleaned_content = clean_and_validate_content(raw_content)

        # 质量验证：如果清洗标签后，正文变成了空字符串，说明是无效数据，直接跳过
        if len(cleaned_content) == 0:
            invalid_count += 1
            continue

        article = {
            "id": row["id"],
            "site": row["site"],
            "url": row["url"],
            "title": row["title"],
            "author": row["author"] or "",
            "published": row["published"] or "",
            "content": cleaned_content,  # 存入剥离标签后的干净正文
            "language": detect_language(cleaned_content),  # 基于干净正文进行语言检测，会准确很多
            "content_length": len(cleaned_content),
        }
        articles.append(article)

    print(f"数据清洗完毕: 拦截了 {invalid_count} 条无正文/纯标签数据。")

    # Export to JSON
    json_path = os.path.join(OUTPUT_DIR, "all_articles.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(articles)} articles to {json_path}")

    # Export to CSV
    csv_path = os.path.join(OUTPUT_DIR, "all_articles.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "site", "language", "title", "author", "published",
            "url", "content_length", "content"
        ])
        writer.writeheader()
        for a in articles:
            writer.writerow(a)
    print(f"Exported {len(articles)} articles to {csv_path}")

    # Export by language to subdirectories
    from collections import defaultdict
    lang_groups = defaultdict(list)
    for a in articles:
        lang_groups[a["language"]].append(a)

    print("\n=== Exporting by language ===")
    for lang, lang_articles in sorted(lang_groups.items()):
        lang_dir = os.path.join(OUTPUT_DIR, lang)
        os.makedirs(lang_dir, exist_ok=True)

        # JSON per language
        lang_json = os.path.join(lang_dir, "all_articles.json")
        with open(lang_json, "w", encoding="utf-8") as f:
            json.dump(lang_articles, f, ensure_ascii=False, indent=2)
        print(f"  {lang}/all_articles.json: {len(lang_articles)} articles")

        # CSV per language
        lang_csv = os.path.join(lang_dir, "all_articles.csv")
        with open(lang_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "site", "language", "title", "author", "published",
                "url", "content_length", "content"
            ])
            writer.writeheader()
            for a in lang_articles:
                writer.writerow(a)
        print(f"  {lang}/all_articles.csv: {len(lang_articles)} articles")

    # Summary by site and language
    from collections import Counter
    site_lang = Counter()
    for a in articles:
        site_lang[(a["site"], a["language"])] += 1

    print("\n=== Summary by site and language ===")
    for (site, lang), count in sorted(site_lang.items()):
        print(f"  {site}/{lang}: {count}")

    print(f"\nTotal articles exported: {len(articles)}")

    db.close()


if __name__ == "__main__":
    main()