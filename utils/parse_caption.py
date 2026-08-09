import re
import unicodedata


FILE_INFO_PATTERNS = [
    r"\baudio\b", r"\bsubtitle\b", r"\besub\b", r"\bsub\b",
    r"\baac\b", r"\bac3\b", r"\be-?ac3\b", r"\bddp?\b",
    r"\bdts\b", r"\batmos\b", r"\bflac\b", r"\bmp3\b",
    r"\bx264\b", r"\bx265\b", r"\bhevc\b", r"\bavc\b",
    r"\bweb[- ]?dl\b", r"\bwebrip\b", r"\bbluray\b",
    r"\bhdrip\b", r"\bremux\b", r"\b2160p\b", r"\b1080p\b",
    r"\b720p\b", r"\b480p\b", r"\bhindi\b", r"\benglish\b",
    r"\btamil\b", r"\btelugu\b", r"\bmalayalam\b",
    r"\bkannada\b", r"\bjapanese\b", r"\bkorean\b",
    r"\bchinese\b", r"\bdual audio\b", r"\bmulti\b",
    r"\bchapters?\b"
]


def remove_emojis(text):
    # Removes all standard emojis, symbols, and pictographs
    emoji_pattern = re.compile(
        r"["
        r"\U0001f300-\U0001f5ff"  # Symbols & Pictographs
        r"\U0001f600-\U0001f64f"  # Emoticons
        r"\U0001f680-\U0001f6ff"  # Transport & Map Symbols
        r"\U0001f1e0-\U0001f1ff"  # Flags (iOS)
        r"\U00002702-\U000027b0"  # Dingbats
        r"\U000024c2-\U0001f251"
        r"\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
        r"\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
        r"\U00002600-\U000026ff"  # Miscellaneous Symbols
        r"]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text)


def remove_fancy_fonts(text):
    result = []
    for ch in text:
        cp = ord(ch)
        name = unicodedata.name(ch, "")

        # Mathematical Alphanumeric Symbols
        if 0x1D400 <= cp <= 0x1D7FF:
            continue

        # Fullwidth ASCII
        if 0xFF01 <= cp <= 0xFF5E:
            continue

        # Enclosed Alphanumerics
        if 0x2460 <= cp <= 0x24FF:
            continue

        # Enclosed Alphanumeric Supplement
        if 0x1F100 <= cp <= 0x1F1FF:
            continue

        # Squared / Negative Squared letters
        if (
            "SQUARED LATIN" in name
            or "NEGATIVE SQUARED LATIN" in name
            or "CIRCLED LATIN" in name
            or "PARENTHESIZED LATIN" in name
            or "MATHEMATICAL" in name
            or "FULLWIDTH" in name
        ):
            continue
        result.append(ch)
    return "".join(result)
    
def is_file_info(text):
    text = text.lower()
    return any(re.search(pattern, text) for pattern in FILE_INFO_PATTERNS)
    
    
def extract_caption(file_name):
    """Clean and format the file name."""

    file_name = str(file_name)
    
    # Remove all types of emojis first
    file_name = remove_emojis(file_name)
    
    file_name = remove_fancy_fonts(str(file_name))

    # Keep filename + file info blocks, remove promotional blocks
    parts = re.split(r"\r?\n\s*\r?\n", file_name.strip())
    cleaned_parts = [parts[0]]

    for part in parts[1:]:
        if is_file_info(part):  # Imported from FILE_INFO_PATTERNS
            cleaned_parts.append(part)
        else:
            break

    file_name = "\n\n".join(cleaned_parts)

    # Remove links anywhere in the text
    file_name = re.sub(
        r"https?://\S+|www\.\S+|t\.me/\S+", "", file_name, flags=re.I
    )

    # Remove usernames in brackets
    file_name = re.sub(r"\[\s*@[^]]+\]", "", file_name)
    file_name = re.sub(r"\(\s*@[^)]+\)", "", file_name)
    # (2025) -> 2025
    # (1950) -> 1950
    file_name = re.sub(r"\(((?:19|20)\d{2})\)", r"\1", file_name)
    
    # Remove username at the beginning
    file_name = re.sub(r"^\s*@\S+\s*[-:|]?\s*", "", file_name)

    # ---------------- Protect patterns ----------------

    # Protect audio channels: 5.1, 2.0, 7.1
    file_name = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", file_name)

    # Protect episode ranges:
    # E45-50, E45 - 50, Ep01-06, Episode 57 - 67, 56-89
    file_name = re.sub(
        r"(?i)\b(?:"
        r"s\d+\s*e(?:p)?\d+"            # S01E06, S01Ep06
        r"|s\d+\s*e(?:p)?\d+\s*-\s*e?(?:p)?\d+"  # S01E06-E10
        r"|e(?:p(?:isode)?)?\s*\d+"     # E06, Ep06, Episode 06
        r"|\d+"                         # 06
        r")\s*-\s*\d+\b",
        lambda m: m.group(0).replace("-", "<DASH>"),
        file_name,
    )

    # Protect language blocks inside [] and ()
    def protect_language_block(match):
        text = match.group(0)
        text = text.replace("-", "<DASH>")
        text = text.replace("+", "<PLUS>")
        return text

    LANG_WORDS = (
        r"Hindi|English|Tamil|Telugu|Malayalam|Kannada|Japanese|Korean|Chinese|"
        r"French|German|Spanish|Italian|Russian|Arabic|Punjabi|Bengali|Gujarati|"
        r"Marathi|Urdu|Odia|Line|Thai|Indonesian|"
        r"Hin|Eng|Tam|Tel|Mal|Jap|Kor|Thai"
    )

    file_name = re.sub(
        rf"\[[^\]]*(?:{LANG_WORDS})[^\]]*\]",
        protect_language_block,
        file_name,
        flags=re.I,
    )

    file_name = re.sub(
        rf"\([^\)]*(?:{LANG_WORDS})[^\)]*\)",
        protect_language_block,
        file_name,
        flags=re.I,
    )

    # Protect short-word pairs like HE-AAC, WEB-DL, HD-TC
    file_name = re.sub(
        r"\b(?!@)([A-Za-z]{1,5})-([A-Za-z]{1,5})\b",
        lambda m: f"{m.group(1)}<DASH>{m.group(2)}",
        file_name,
    )

    # ---------------- Replace separators ----------------

    file_name = re.sub(r"[_.+-]", " ", file_name)

    # ---------------- Restore protected patterns ----------------

    file_name = (
        file_name.replace("<DOT>", ".")
        .replace("<DASH>", "-")
        .replace("<PLUS>", "+")
    )
    # Remove any remaining @user tokens
    file_name = " ".join(
        word for word in file_name.split() if not word.startswith("@")
    )

    return file_name.strip()
