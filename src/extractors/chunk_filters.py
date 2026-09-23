"""
chunk_filters.py — shared content-quality filter for the extraction
pipeline. Import this in EVERY extractor (pptx, ipynb, md, xlsx...),
not just the pptx one, since decorative/non-informative chunks (ASCII
art banners, separator lines, empty headers) can show up in any file
type — e.g. the "/\\_/\\ Hands-On" banner found in
HandsOn1_Window_Functions.md.

Usage in any extractor:
    from chunk_filters import is_low_content_chunk
    ...
    if is_low_content_chunk(chunk_text):
        excluded.append(chunk)   # log it, don't tag it
    else:
        chunks.append(chunk)
"""
import re

_WORD = re.compile(r"[A-Za-z\u0600-\u06FF]{2,}")


def is_low_content_chunk(text: str, min_words: int = 8, min_alpha_ratio: float = 0.35) -> bool:
    """True when a chunk is decoration/noise rather than real content:
    too few real words, or mostly symbols (=, -, \\, /, #...) rather
    than letters. Tuned so real short technical snippets still pass."""
    words = _WORD.findall(text)
    if len(words) < min_words:
        return True
    alpha_chars = sum(c.isalpha() for c in text)
    if len(text) == 0 or (alpha_chars / len(text)) < min_alpha_ratio:
        return True
    return False