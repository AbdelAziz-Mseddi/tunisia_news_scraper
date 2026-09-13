"""Shared text normalization helpers used by both region and urgency detection."""

import unicodedata


def strip_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) and normalize alef/ya variants
    so matching isn't defeated by optional vowel marks or spelling
    variants that don't change meaning."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    return text
