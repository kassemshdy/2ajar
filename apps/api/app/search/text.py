"""Text normalisation shared by the parser and the location index."""

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")  # tashkeel + tatweel
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_LETTER_FOLDS = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}
)
_PUNCT = re.compile(r"[^\w\s$.,/+-]")
_SPACES = re.compile(r"\s+")
# Commas/periods are kept only inside numbers ("1,200", "1.5k"); elsewhere they separate words.
_LOOSE_SEPARATORS = re.compile(r"(?<!\d)[.,]|[.,](?!\d)")
# Arabic attaches short words to the next one: و (and), ب (with/in), ل (for), ف (so), ك (like), + ال (the).
_AR_PROCLITICS = r"(?:[وبلفك]?(?:ال)?|لل)"


def normalize(text: str) -> str:
    """Lowercase, fold Arabic letter variants and digits, drop diacritics and noise punctuation."""
    # NFKD splits accents off (e.g. "é" becomes "e" plus a combining mark), so they are dropped below.
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text).translate(_ARABIC_DIGITS).translate(_LETTER_FOLDS).lower()
    text = text.replace("،", ",").replace("؟", " ").replace("–", "-")
    text = _PUNCT.sub(" ", text)
    text = _LOOSE_SEPARATORS.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase)
    if is_arabic(phrase):
        bare = re.escape(phrase[2:]) if phrase.startswith("ال") else escaped
        return re.compile(rf"(?:^|\s){_AR_PROCLITICS}(?:{escaped}|{bare})(?=\s|$)")
    return re.compile(rf"(?:^|\s){escaped}(?=\s|$)")


_PATTERNS: dict[str, re.Pattern[str]] = {}


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Whole-word pattern; Arabic phrases also match with attached prefixes (بالحمرا, وبغرفتين...)."""
    pattern = _PATTERNS.get(phrase)
    if pattern is None:
        # Vocabulary is written naturally (على, آمنة); fold it exactly like the user's text.
        pattern = _PATTERNS[phrase] = _phrase_pattern(normalize(phrase))
    return pattern


def contains_phrase(haystack: str, phrase: str) -> bool:
    return phrase_pattern(phrase).search(haystack) is not None


def consume_phrase(haystack: str, phrase: str) -> str:
    """Blank out the first occurrence (keeps positions stable for later rules)."""
    m = phrase_pattern(phrase).search(haystack)
    if m is None:
        return haystack
    return haystack[: m.start()] + " " * (m.end() - m.start()) + haystack[m.end() :]


def is_arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)
