"""
Flexible column mapping: every vendor names its columns differently
("Dial Code", "Code", "Prefixes", "Breakout"...). We suggest a mapping
from known aliases and remember the user's choice per vendor.
"""
import re

FIELDS = [
    # key, label, required, help
    ("prefix", "Prefix / dial code", True, "Digits the call starts with. Lists (44, 447) and ranges (4470-4479) are allowed."),
    ("rate", "Rate per minute", True, "Price in USD per minute. $, spaces and decimal commas are cleaned."),
    ("destination", "Destination", False, "Destination name, e.g. Germany - Mobile."),
    ("country", "Country", False, "Country name, if the deck has a separate column for it."),
    ("effective_date", "Effective date", False, "When the rate starts. Blank rows use the deck's default date."),
    ("increment", "Billing increment", False, "e.g. 60/60 or 1/1. Blank rows use the vendor default."),
]
FIELD_KEYS = [f[0] for f in FIELDS]
REQUIRED_FIELDS = [f[0] for f in FIELDS if f[2]]

ALIASES = {
    "prefix": ["prefix", "prefixes", "dial code", "dialcode", "dial codes", "code", "codes", "dialing code",
               "area code", "country code", "number range", "e164", "routing code", "cc+ndc"],
    "rate": ["rate", "price", "cost", "rate usd", "usd", "per min", "per minute", "price/min", "rate/min",
             "rate per minute", "new rate", "tariff", "charge", "amount"],
    "destination": ["destination", "description", "desc", "zone", "route", "name", "destination name",
                    "breakout", "breakout name", "network"],
    "country": ["country", "country name", "nation"],
    "effective_date": ["effective date", "effective", "effective from", "valid from", "start date", "start", "date",
                       "effective_date", "eff date", "eff. date", "from date", "activation date"],
    "increment": ["increment", "billing increment", "billing", "interval", "billing interval", "pulse",
                  "billing unit", "min/inc", "rounding"],
}

# Words that suggest a column is *not* the main rate (e.g. "Old Rate", "Connection fee")
RATE_EXCLUDE = ["old", "previous", "prev", "connection", "setup", "conn"]


def _norm(text):
    return re.sub(r"[^a-z0-9/+]+", " ", str(text).lower()).strip()


def _match_score(field, header):
    h = _norm(header)
    if not h:
        return 0
    if field == "rate" and any(word in h.split() for word in RATE_EXCLUDE):
        return 0
    best = 0
    for alias in ALIASES[field]:
        a = _norm(alias)
        if h == a:
            best = max(best, 100)
        elif re.search(rf"\b{re.escape(a)}\b", h):
            best = max(best, 60 + len(a))  # longer alias match = more specific
    return best


def header_score(values):
    """How many different fields a row of cell values looks like (used to find the header row)."""
    found = set()
    for value in values:
        for field in FIELD_KEYS:
            if _match_score(field, value) >= 60:
                found.add(field)
    if "prefix" in found and "rate" in found:
        return len(found) + 1
    return len(found)


def suggest_mapping(columns, saved=None):
    """
    Return {field: column_label}. Saved vendor mapping wins when its column still exists
    (case-insensitive); otherwise each field gets the best alias match, never re-using a column.
    """
    saved = saved or {}
    lower_to_col = {c.lower(): c for c in columns}
    mapping, used = {}, set()

    for field in FIELD_KEYS:
        col = lower_to_col.get(str(saved.get(field, "")).lower())
        if col and col not in used:
            mapping[field] = col
            used.add(col)

    for field in FIELD_KEYS:
        if field in mapping:
            continue
        scored = sorted(
            ((c, _match_score(field, c)) for c in columns if c not in used),
            key=lambda item: item[1], reverse=True,
        )
        if scored and scored[0][1] >= 60:
            mapping[field] = scored[0][0]
            used.add(scored[0][0])
    return mapping
