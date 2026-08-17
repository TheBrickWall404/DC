"""
Implements the Chen Name Matcher specification.
"""
import re
import unicodedata
from typing import Set

def clean_base_name(name: str) -> str:
    """Removes nicknames in quotes/brackets, handles special Latin diacritics, and strips non-ASCII accents."""
    if not name:
        return ""
    cleaned = re.sub(r'\(.*?\)|\[.*?\]|".*?"|\'.*?\'', '', str(name))
    
    custom_map = {
        'đ': 'd', 'Đ': 'd', 'ð': 'd', 'Ð': 'd',
        'ł': 'l', 'Ł': 'l', 'ø': 'o', 'Ø': 'o'
    }
    for char, rep in custom_map.items():
        cleaned = cleaned.replace(char, rep)
    
    cleaned = unicodedata.normalize('NFKD', cleaned).encode('ASCII', 'ignore').decode('utf-8')
    cleaned = re.sub(r'[^a-zA-Z\s]', ' ', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip().lower()

def normalize_name(name: str) -> str:
    """Produces the singular stripped match key."""
    cleaned = clean_base_name(name)
    return re.sub(r'\s+', '', cleaned)

def get_name_variations(name: str) -> Set[str]:
    """
    Per Chen spec: when name has > 2 words, generates match keys for:
    - Entire name
    - First and last word
    - First two words
    """
    base = clean_base_name(name)
    if not base:
        return set()
    
    tokens = base.split()
    variations = {re.sub(r'\s+', '', base)}
    
    if len(tokens) > 2:
        variations.add(f"{tokens[0]}{tokens[-1]}")
        variations.add(f"{tokens[0]}{tokens[1]}")
        
    return variations