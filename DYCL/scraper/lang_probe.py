"""
lang_probe.py

Language Probe V1
-----------------
基于 Unicode 字符范围进行简单语言检测。

当前支持：
- English
- Chinese
- Tibetan
- Hindi
- Nepali
- Arabic
- Russian
- Japanese
- Korean
- Unknown

用法：

1. 命令行测试文本：
    python lang_probe.py "This is an English article."

2. 测试文件：
    python lang_probe.py article.txt

3. Python 中调用：
    from lang_probe import detect_language

    result = detect_language("བོད་ཀྱི་ཡིག་རིགས")
    print(result)
"""

import sys
import re
import unicodedata
from collections import Counter


# ============================================================
# Unicode 范围
# ============================================================

RANGES = {
    "Chinese": [
        (0x4E00, 0x9FFF),       # CJK Unified Ideographs
        (0x3400, 0x4DBF),       # CJK Extension A
        (0x20000, 0x2A6DF),     # CJK Extension B
    ],

    "Tibetan": [
        (0x0F00, 0x0FFF),
    ],

    "Hindi": [
        (0x0900, 0x097F),       # Devanagari
    ],

    "Nepali": [
        (0x0900, 0x097F),       # Nepali 也主要使用 Devanagari
    ],

    "Arabic": [
        (0x0600, 0x06FF),
        (0x0750, 0x077F),
        (0x08A0, 0x08FF),
    ],

    "Russian": [
        (0x0400, 0x04FF),       # Cyrillic
    ],

    "Japanese": [
        (0x3040, 0x309F),       # Hiragana
        (0x30A0, 0x30FF),       # Katakana
    ],

    "Korean": [
        (0xAC00, 0xD7AF),       # Hangul syllables
        (0x1100, 0x11FF),       # Hangul Jamo
    ],
}


# ============================================================
# 基础工具
# ============================================================

def in_ranges(codepoint, ranges):
    """判断 Unicode codepoint 是否属于某个字符范围。"""
    for start, end in ranges:
        if start <= codepoint <= end:
            return True
    return False


def is_latin_char(char):
    """判断是否为拉丁字符。"""
    return "LATIN" in unicodedata.name(char, "")


def is_cyrillic_char(char):
    """判断是否为西里尔字符。"""
    return "CYRILLIC" in unicodedata.name(char, "")


def is_letter(char):
    """判断字符是否为 Unicode 字母。"""
    return unicodedata.category(char).startswith("L")


def clean_text(text):
    """
    基础文本清洗。

    V1 不进行复杂清洗，只：
    - Unicode 标准化
    - 删除控制字符
    - 合并空白
    """
    text = unicodedata.normalize("NFC", text)

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) not in {
            "Cc",
            "Cf",
        }
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# 字符分类
# ============================================================

def classify_char(char):
    """
    返回单个字符可能属于的语言。

    注意：
    一个字符可能属于多个语言。

    例如 Devanagari：
        Hindi / Nepali
    """

    codepoint = ord(char)

    # Tibetan
    if in_ranges(codepoint, RANGES["Tibetan"]):
        return "Tibetan"

    # Chinese
    if in_ranges(codepoint, RANGES["Chinese"]):
        return "Chinese"

    # Japanese
    if in_ranges(codepoint, RANGES["Japanese"]):
        return "Japanese"

    # Korean
    if in_ranges(codepoint, RANGES["Korean"]):
        return "Korean"

    # Arabic
    if in_ranges(codepoint, RANGES["Arabic"]):
        return "Arabic"

    # Devanagari
    if in_ranges(codepoint, RANGES["Hindi"]):
        return "Devanagari"

    # Cyrillic
    if is_cyrillic_char(char):
        return "Russian"

    # Latin
    if is_latin_char(char):
        return "English"

    return None


# ============================================================
# 统计
# ============================================================

def analyze_text(text):
    """
    对文本进行字符统计。
    """

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


# ============================================================
# 语言决策
# ============================================================

def decide_language(counts, total_letters):
    """
    根据字符占比决定语言。

    返回：
        language
        confidence
    """

    if total_letters == 0:
        return "Unknown", 0.0

    # --------------------------------------------------------
    # Devanagari 特殊处理
    # --------------------------------------------------------

    devanagari_count = counts.get("Devanagari", 0)

    if devanagari_count > 0:

        # V1 暂时不能仅凭 Unicode 区分 Hindi / Nepali。
        #
        # 所以先统一认为 Hindi/Nepali 家族。
        #
        # 后续 V2 可以加入：
        # - 常见词
        # - trigram
        # - 词典
        # - fastText
        #
        # 这里暂时返回 Hindi。
        if devanagari_count / total_letters >= 0.30:
            confidence = devanagari_count / total_letters
            return "Hindi", confidence

    # --------------------------------------------------------
    # 找主要语言
    # --------------------------------------------------------

    candidates = {
        language: count
        for language, count in counts.items()
        if language != "Devanagari"
    }

    if not candidates:
        return "Unknown", 0.0

    language, count = max(
        candidates.items(),
        key=lambda item: item[1]
    )

    confidence = count / total_letters

    # 太低说明文本可能是混合语言
    if confidence < 0.30:
        return "Unknown", confidence

    return language, confidence


# ============================================================
# 主检测函数
# ============================================================

def detect_language(text):
    """
    检测文本语言。

    返回：

    {
        "language": "English",
        "confidence": 0.95,
        "letters": 100,
        "counts": {
            "English": 95,
            "Chinese": 5
        }
    }
    """

    cleaned_text, counts, total_letters = analyze_text(text)

    language, confidence = decide_language(
        counts,
        total_letters,
    )

    return {
        "language": language,
        "confidence": round(confidence, 4),
        "letters": total_letters,
        "counts": dict(counts),
        "text_length": len(cleaned_text),
    }


# ============================================================
# 文件检测
# ============================================================

def detect_file(path):
    """
    从文本文件读取并检测语言。
    """

    encodings = [
        "utf-8",
        "utf-8-sig",
        "gb18030",
    ]

    text = None

    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as f:
                text = f.read()
            break

        except UnicodeDecodeError:
            continue

    if text is None:
        raise UnicodeDecodeError(
            "unknown",
            b"",
            0,
            1,
            f"无法读取文件：{path}"
        )

    return detect_language(text)


# ============================================================
# CLI
# ============================================================

def print_result(result):
    print()
    print("=" * 50)
    print("Language Probe V1")
    print("=" * 50)

    print(f"Language   : {result['language']}")
    print(f"Confidence : {result['confidence']:.2%}")
    print(f"Letters    : {result['letters']}")
    print(f"Text length: {result['text_length']}")

    print()
    print("Character statistics:")

    counts = result["counts"]

    if not counts:
        print("  No recognizable language characters.")
    else:
        for language, count in sorted(
            counts.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            ratio = count / result["letters"]

            print(
                f"  {language:12s}"
                f"{count:8d}"
                f"  ({ratio:.2%})"
            )

    print("=" * 50)
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print()
        print('  python lang_probe.py "text"')
        print("  python lang_probe.py article.txt")
        return

    target = sys.argv[1]

    # 判断是不是文件
    try:
        with open(target, "r", encoding="utf-8"):
            is_file = True
    except (OSError, UnicodeDecodeError):
        is_file = False

    if is_file:
        result = detect_file(target)
    else:
        result = detect_language(target)

    print_result(result)


if __name__ == "__main__":
    main()