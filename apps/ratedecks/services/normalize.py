"""
Normalization rules for the values found in vendor rate decks.

Each parser returns a clean value or raises NormalizeError with a message
that is shown to the user in the error report.
"""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings


class NormalizeError(ValueError):
    pass


# ---------------------------------------------------------------- prefixes
PREFIX_LIST_SPLIT = re.compile(r"[,;|\n]+")
RANGE_RE = re.compile(r"^(\d+)\s*(?:-|–|to)\s*(\d+)$", re.IGNORECASE)
MAX_PREFIX_LEN = 15  # E.164 maximum


def _clean_prefix_token(token):
    t = token.strip()
    t = re.sub(r"[\s().'\"]", "", t)
    if t.startswith("+"):
        t = t[1:]
    elif t.startswith("00"):
        t = t[2:]
    return t


def parse_prefixes(raw):
    """
    '447'            -> ['447']
    '+44 7, 0044 1'  -> ['447', '441']
    '4470-4473'      -> ['4470', '4471', '4472', '4473']
    Raises NormalizeError for letters, empty values or bad ranges.
    """
    text = str(raw or "").strip()
    if not text:
        raise NormalizeError("Prefix is empty")

    max_range = settings.ROUTERATE["MAX_RANGE_EXPANSION"]
    prefixes = []
    for token in PREFIX_LIST_SPLIT.split(text):
        if not token.strip():
            continue
        range_match = RANGE_RE.match(re.sub(r"[+]", "", token.strip()))
        if range_match:
            start, end = (_clean_prefix_token(p) for p in range_match.groups())
            if len(start) != len(end):
                raise NormalizeError(f"Range '{token.strip()}' must have prefixes of the same length")
            if int(end) < int(start):
                raise NormalizeError(f"Range '{token.strip()}' ends before it starts")
            count = int(end) - int(start) + 1
            if count > max_range:
                raise NormalizeError(f"Range '{token.strip()}' would create {count} prefixes (max {max_range})")
            prefixes.extend(str(n).zfill(len(start)) for n in range(int(start), int(end) + 1))
            continue

        prefix = _clean_prefix_token(token)
        if not prefix:
            continue
        if not prefix.isdigit():
            raise NormalizeError(f"Prefix '{token.strip()}' contains characters that are not digits")
        if prefix.startswith("0"):
            raise NormalizeError(f"Prefix '{token.strip()}' starts with 0 (use the international format)")
        prefixes.append(prefix)

    if not prefixes:
        raise NormalizeError("Prefix is empty")
    for p in prefixes:
        if len(p) > MAX_PREFIX_LEN:
            raise NormalizeError(f"Prefix '{p}' is longer than {MAX_PREFIX_LEN} digits")
    # keep order, drop repeats inside the same cell
    return list(dict.fromkeys(prefixes))


# ---------------------------------------------------------------- rates
CURRENCY_RE = re.compile(r"(usd|us\$|\$|€|eur|£|gbp|/min|per\s*min)", re.IGNORECASE)


def parse_rate(raw):
    """'$0.0125', '0,0125', ' 0.0125 USD' -> Decimal('0.0125')"""
    text = str(raw or "").strip()
    if not text:
        raise NormalizeError("Rate is empty")
    cleaned = CURRENCY_RE.sub("", text).replace(" ", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        # The last separator is the decimal point: 1,234.50 or 1.234,50
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")  # decimal comma (European decks)
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise NormalizeError(f"Rate '{text}' is not a number") from None
    if not value.is_finite():
        raise NormalizeError(f"Rate '{text}' is not a number")
    if value < 0:
        raise NormalizeError(f"Rate {value} is negative")
    if value == 0:
        raise NormalizeError("Rate is zero")
    max_rate = Decimal(str(settings.ROUTERATE["MAX_RATE_PER_MIN"]))
    if value > max_rate:
        raise NormalizeError(f"Rate {value} is above the maximum allowed ({max_rate} per minute)")
    return value.quantize(Decimal("0.000001"))


# ---------------------------------------------------------------- dates
ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$")
DMY_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
               "%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d", "%Y%m%d"]
MDY_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%m/%d/%y", "%m-%d-%y",
               "%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d", "%Y%m%d"]
IMMEDIATE_WORDS = {"immediate", "immediately", "now", "asap", "current", "today"}
EXCEL_EPOCH = date(1899, 12, 30)


def parse_date(raw, default, date_order="DMY"):
    """Returns a date. Blank cells and words like 'Immediate' use the deck default date."""
    text = str(raw or "").strip()
    if not text or text.lower() in IMMEDIATE_WORDS:
        return default

    iso = ISO_RE.match(text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            raise NormalizeError(f"Date '{text}' does not exist") from None

    # Excel serial number stored as plain number, e.g. 46310
    if text.isdigit() and 30000 <= int(text) <= 80000:
        return EXCEL_EPOCH + timedelta(days=int(text))

    formats = MDY_FORMATS if date_order == "MDY" else DMY_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise NormalizeError(f"Date '{text}' is not a recognised date")


# ---------------------------------------------------------------- billing increment
INCREMENT_RE = re.compile(r"^(\d{1,4})\s*[/\-+x: ]\s*(\d{1,4})$")


def parse_increment(raw, default):
    text = str(raw or "").strip().lower().replace("sec", "").replace("s", "").strip()
    if not text:
        return default
    match = INCREMENT_RE.match(text)
    if match:
        first, nxt = int(match.group(1)), int(match.group(2))
    elif text.isdigit():
        first = nxt = int(text)
    else:
        raise NormalizeError(f"Billing increment '{raw}' is not in the format 60/60")
    if not (1 <= first <= 3600 and 1 <= nxt <= 3600):
        raise NormalizeError(f"Billing increment '{raw}' is out of range")
    return f"{first}/{nxt}"


SMALL_WORDS = {"and", "of", "the", "de", "la"}


def _smart_title(text):
    """'UNITED KINGDOM - MOBILE' -> 'United Kingdom - Mobile', keeps short codes like USA or UAE."""
    words = []
    for word in text.split(" "):
        if word.lower() in SMALL_WORDS:
            words.append(word.lower())
        elif len(word) <= 3:
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words)


def clean_destination(raw):
    text = re.sub(r"\s+", " ", str(raw or "")).strip(" -")
    if text and text == text.upper() and any(ch.isalpha() for ch in text):
        text = _smart_title(text)
    return text[:120]
