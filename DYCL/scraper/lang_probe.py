"""
lang_probe.py

Language Probe V1.1 (improved)
-----------------
基于 Unicode 字符范围进行简单语言检测。

对外只返回：
- chinese
- english
- tibetan
- other

改进点：
1. 日语优先通过平假名/片假名识别，避免被汉字拖进 chinese
2. 藏文使用更高优先级 + 绝对数量门槛，减少中英文混入
3. 混合文本更保守地归为 other
"""

import sys
import re
import unicodedata
from collections import Counter


# ============================================================
# Unicode 范围
# ============================================================

RANGES = {
    "chinese": [
        (0x4E00, 0x9FFF),       # CJK Unified Ideographs
        (0x3400, 0x4DBF),       # CJK Extension A
        (0x20000, 0x2A6DF),     # CJK Extension B
    ],
    "tibetan": [
        (0x0F00, 0x0FFF),
    ],
    "japanese_kana": [          # 平假名 + 片假名（日语强特征）
        (0x3040, 0x309F),       # Hiragana
        (0x30A0, 0x30FF),       # Katakana
    ],
    "korean": [
        (0xAC00, 0xD7AF),
        (0x1100, 0x11FF),
    ],
    "arabic": [
        (0x0600, 0x06FF),
        (0x0750, 0x077F),
        (0x08A0, 0x08FF),
    ],
    "hindi": [
        (0x0900, 0x097F),
    ],
    "russian": [
        (0x0400, 0x04FF),
    ],
}


def in_ranges(codepoint, ranges):
    for start, end in ranges:
        if start <= codepoint <= end:
            return True
    return False


def is_latin_char(char):
    return "LATIN" in unicodedata.name(char, "")


def is_cyrillic_char(char):
    return "CYRILLIC" in unicodedata.name(char, "")


def is_letter(char):
    return unicodedata.category(char).startswith("L")


def clean_text(text):
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        char for char in text
        if unicodedata.category(char) not in {"Cc", "Cf"}
    )
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_char(char):
    codepoint = ord(char)

    if in_ranges(codepoint, RANGES["tibetan"]):
        return "tibetan"
    if in_ranges(codepoint, RANGES["japanese_kana"]):
        return "japanese_kana"
    if in_ranges(codepoint, RANGES["chinese"]):
        return "chinese"
    if in_ranges(codepoint, RANGES["korean"]):
        return "korean"
    if in_ranges(codepoint, RANGES["arabic"]):
        return "arabic"
    if in_ranges(codepoint, RANGES["hindi"]):
        return "hindi"
    if is_cyrillic_char(char):
        return "russian"
    if is_latin_char(char):
        return "english"
    return None


def analyze_text(text):
    text = clean_text(text)
    counts = Counter()
    total_letters = 0

    for char in text:
        if not is_letter(char):
            continue
        total_letters += 1
        language = classify_char(char)
        if language:
            counts[language] += 1

    return text, counts, total_letters


def decide_language(counts, total_letters):
    """
    只返回 chinese / english / tibetan / other
    """
    if total_letters == 0:
        return "other"

    tibetan_count     = counts.get("tibetan", 0)
    chinese_count     = counts.get("chinese", 0)
    english_count     = counts.get("english", 0)
    kana_count        = counts.get("japanese_kana", 0)   # 日语强特征

    tibetan_ratio     = tibetan_count / total_letters
    chinese_ratio     = chinese_count / total_letters
    english_ratio     = english_count / total_letters
    kana_ratio        = kana_count / total_letters

    # --------------------------------------------------------
    # 1. 藏文：高优先级 + 绝对数量门槛，防止少量藏文被忽略，
    #    同时要求藏文占比足够高，减少中英文混入
    # --------------------------------------------------------
    if tibetan_count >= 20 and tibetan_ratio >= 0.25:
        return "tibetan"

    # --------------------------------------------------------
    # 2. 日语：只要出现一定数量的平假名/片假名，就判定为日语
    #    （最终归到 other），避免被汉字拖进 chinese
    # --------------------------------------------------------
    if kana_count >= 10 or kana_ratio >= 0.08:
        return "other"          # 日语 → other

    # --------------------------------------------------------
    # 3. 中文：汉字占比高，且没有明显的日语假名
    # --------------------------------------------------------
    if chinese_count >= 30 and chinese_ratio >= 0.35:
        return "chinese"

    # --------------------------------------------------------
    # 4. 英文
    # --------------------------------------------------------
    if english_count >= 50 and english_ratio >= 0.40:
        return "english"

    # --------------------------------------------------------
    # 5. 其他情况（包括韩语、阿拉伯语、俄语、混合文本等）
    # --------------------------------------------------------
    return "other"


def detect_language(text):
    """
    对外接口：直接返回字符串
    "chinese" | "english" | "tibetan" | "other"
    """
    if not text:
        return "other"

    _, counts, total_letters = analyze_text(text)
    return decide_language(counts, total_letters)


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print('Usage: python lang_probe.py "text"  or  python lang_probe.py file.txt')
        return

    target = sys.argv[1]
    try:
        with open(target, "r", encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError):
        text = target

    lang = detect_language(text)
    print(lang)


if __name__ == "__main__":
    main()