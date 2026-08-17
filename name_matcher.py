"""
Implements the Chen Name Matching specification.
"""
import re
import unicodedata

def normalize_name(name: str) -> str:
    """
    1. Removes text in brackets/quotes.
    2. Maps special non-decomposable Unicode characters (Đ, Ł, Ø, etc.).
    3. Decomposes accents and strips non-ASCII.
    4. Strips non-alphabetic chars, trims, lowercases, and removes intra-word whitespace.
    """
    if not name:
        return ""

    # Remove nicknames in parentheses, brackets, or quotes
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|".*?"|\'.*?\'', '', name)

    # Manual replacements for special characters
    special_map = {
        'đ': 'd', 'Đ': 'd', 'ð': 'd', 'Ð': 'd',
        'ł': 'l', 'Ł': 'l', 'ø': 'o', 'Ø': 'o'
    }
    for k, v in special_map.items():
        cleaned = cleaned.replace(k, v)

    # Strip Unicode diacritics
    cleaned = unicodedata.normalize('NFKD', cleaned).encode('ASCII', 'ignore').decode('utf-8')

    # Remove non-letters and spaces
    cleaned = re.sub(r'[^a-zA-Z]', '', cleaned)

    return cleaned.lower().strip()