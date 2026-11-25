"""
Turns an uploaded vendor file into validated, normalized rate lines.

Pipeline
  1. Read the file (CSV or Excel) as raw text            -> reader.py
  2. Apply the user's column mapping
  3. Normalize every value and validate it               -> normalize.py
       prefix lists/ranges, rate formats, dates, increments,
       country lookup from the prefix, destination name check
  4. Resolve duplicate prefixes with the chosen policy   (Pandas groupby)
  5. Compare with the vendor's current rates             -> New / Increase / Decrease / Unchanged
  6. Save lines, issues (error report) and a processing log

Nothing here touches the live routing table. That only happens on activation.
"""
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.countries import CountryIndex

from ..models import ChangeType, DeckIssue, DeckLog, RateDeck, RateDeckLine, VendorRate
from . import reader
from .mapping import REQUIRED_FIELDS
from .normalize import (
    NormalizeError, clean_destination, parse_date, parse_increment, parse_prefixes, parse_rate,
)


@dataclass
class Candidate:
    row_number: int
    prefix: str
    country: object
    destination: str
    rate: Decimal
    increment: str
    effective_date: object


class DeckProcessor:
    def __init__(self, deck: RateDeck, options: dict):
        self.deck = deck
        self.columns = options["columns"]
        self.header_row = int(options["header_row"])
        self.sheet = options.get("sheet") or ""
        self.date_order = options.get("date_order", "DMY")
        self.cfg = settings.ROUTERATE
        self.today = timezone.localdate(deck.uploaded_at) if deck.uploaded_at else timezone.localdate()
        self.issues = []
        self.logs = []
        self.error_rows = 0
        self.warning_rows = set()
        self.expanded = 0
        self.backdated = []

    # ------------------------------------------------------------ helpers
    def log(self, message, level="info"):
        self.logs.append(DeckLog(deck=self.deck, level=level, message=message[:300]))

    def issue(self, level, row, field, value, message):
        self.issues.append(DeckIssue(
            deck=self.deck, row_number=row, level=level, field=field,
            value=str(value or "")[:200], message=message[:300],
        ))
        if level == DeckIssue.Level.WARNING and row:
            self.warning_rows.add(row)

    # ------------------------------------------------------------ main
    def run(self):
        started = time.monotonic()
        deck = self.deck
        missing = [f for f in REQUIRED_FIELDS if not self.columns.get(f)]
        if missing:
            raise ValueError(f"Required columns not mapped: {', '.join(missing)}")

        raw, info = reader.read_raw(deck.file.path, deck.file_type, self.sheet or None)
        body = reader.data_frame(raw, self.header_row)
        where = f"sheet '{info['sheet']}'" if info["sheet"] else f"CSV (delimiter '{info['delimiter']}')"
        self.log(f"Read {len(body):,} data rows from {where}, header on row {self.header_row}.")
        mapped = ", ".join(f"{field} ← '{col}'" for field, col in self.columns.items() if col)
        self.log(f"Column mapping: {mapped}. Date order: {self.date_order}.")

        candidates = self.validate_rows(body)
        lines = self.resolve_duplicates(candidates)
        self.detect_changes(lines)
        self.save(body, lines, started)
        return deck

    # ------------------------------------------------------------ step 3: row validation
    def validate_rows(self, body):
        countries = CountryIndex()
        vendor_increment = self.deck.vendor.default_increment
        max_future = self.today + timedelta(days=self.cfg["MAX_FUTURE_DAYS"])
        backdated = self.today - timedelta(days=self.cfg["BACKDATED_WARNING_DAYS"])
        high_rate = Decimal(str(self.cfg["HIGH_RATE_WARNING"]))
        default_date = self.deck.default_effective_date

        def cell(row, field):
            col = self.columns.get(field)
            return row[col] if col else ""

        candidates = []
        for row_number, row in body.iterrows():
            errors = []
            prefixes, rate, eff, inc = [], None, None, None
            try:
                prefixes = parse_prefixes(cell(row, "prefix"))
            except NormalizeError as exc:
                errors.append(("prefix", cell(row, "prefix"), str(exc)))
            try:
                rate = parse_rate(cell(row, "rate"))
            except NormalizeError as exc:
                errors.append(("rate", cell(row, "rate"), str(exc)))
            try:
                eff = parse_date(cell(row, "effective_date"), default_date, self.date_order)
                if eff > max_future:
                    errors.append(("effective_date", cell(row, "effective_date"),
                                   f"Effective date {eff} is more than {self.cfg['MAX_FUTURE_DAYS']} days ahead"))
            except NormalizeError as exc:
                errors.append(("effective_date", cell(row, "effective_date"), str(exc)))
            try:
                inc = parse_increment(cell(row, "increment"), vendor_increment)
            except NormalizeError as exc:
                errors.append(("increment", cell(row, "increment"), str(exc)))

            resolved = []
            for prefix in prefixes:
                country = countries.resolve(prefix)
                if country is None:
                    errors.append(("prefix", prefix, f"Prefix {prefix} does not start with any known country dial code"))
                else:
                    resolved.append((prefix, country))

            if errors:
                self.error_rows += 1
                for field, value, message in errors:
                    self.issue(DeckIssue.Level.ERROR, row_number, field, value, message)
                continue

            # Warnings: the row is kept
            dest_raw = clean_destination(cell(row, "destination"))
            country_raw = clean_destination(cell(row, "country"))
            name_text = f"{country_raw} {dest_raw}".strip()
            for country in {c for _, c in resolved}:
                if name_text and not countries.destination_matches(country, name_text):
                    self.issue(DeckIssue.Level.WARNING, row_number, "destination", name_text,
                               f"Destination '{name_text}' does not match the prefix country "
                               f"{country.name} (+{country.dial_code})")
            if eff < backdated:
                self.backdated.append((row_number, eff))
            if rate > high_rate:
                self.issue(DeckIssue.Level.WARNING, row_number, "rate", rate,
                           f"High rate {rate} per minute, check it is correct")
            if len(prefixes) > 1:
                self.expanded += len(prefixes) - 1

            for prefix, country in resolved:
                if dest_raw and country_raw:
                    destination = dest_raw if country_raw.lower() in dest_raw.lower() else f"{country_raw} - {dest_raw}"
                else:
                    destination = dest_raw or country_raw or country.name
                candidates.append(Candidate(row_number, prefix, country, destination, rate, inc, eff))

        if self.backdated:
            # One summary warning instead of one per row (full decks often share one old date)
            first_row, earliest = min(self.backdated, key=lambda item: item[1])
            self.issue(DeckIssue.Level.WARNING, None, "effective_date", earliest,
                       f"{len(self.backdated):,} rows have an effective date more than "
                       f"{self.cfg['BACKDATED_WARNING_DAYS']} days in the past (earliest {earliest}, row {first_row})")
        self.log(f"Validated rows: {len(body) - self.error_rows:,} accepted, {self.error_rows:,} rejected.",
                 "warning" if self.error_rows else "info")
        if self.expanded:
            self.log(f"Expanded prefix lists and ranges into {self.expanded:,} extra prefixes.")
        return candidates

    # ------------------------------------------------------------ step 4: duplicates
    def resolve_duplicates(self, candidates):
        if not candidates:
            return []
        df = pd.DataFrame({
            "idx": range(len(candidates)),
            "prefix": [c.prefix for c in candidates],
            "eff": [c.effective_date for c in candidates],
            "rate": [float(c.rate) for c in candidates],
            "row": [c.row_number for c in candidates],
        })
        sizes = df.groupby(["prefix", "eff"])["idx"].transform("size")
        dupes = df[sizes > 1]
        if dupes.empty:
            return candidates

        policy = self.deck.duplicate_policy
        policy_label = RateDeck.DuplicatePolicy(policy).label.lower()
        drop = set()
        for (prefix, eff), group in dupes.groupby(["prefix", "eff"]):
            rows = ", ".join(str(r) for r in sorted(group["row"].unique()))
            if group["rate"].nunique() == 1:
                keep = group.sort_values("row").iloc[0]
                for _, g in group.iterrows():
                    if g["idx"] != keep["idx"]:
                        drop.add(int(g["idx"]))
                        self.issue(DeckIssue.Level.DUPLICATE, int(g["row"]), "prefix", prefix,
                                   f"Exact duplicate of prefix {prefix} (rows {rows}); one copy kept")
                continue
            if policy == RateDeck.DuplicatePolicy.REJECT:
                for _, g in group.iterrows():
                    drop.add(int(g["idx"]))
                    self.issue(DeckIssue.Level.DUPLICATE, int(g["row"]), "prefix", prefix,
                               f"Prefix {prefix} has different rates in rows {rows}; all rejected")
                continue
            if policy == RateDeck.DuplicatePolicy.LOWEST:
                keep = group.sort_values(["rate", "row"]).iloc[0]
            elif policy == RateDeck.DuplicatePolicy.HIGHEST:
                keep = group.sort_values(["rate", "row"], ascending=[False, True]).iloc[0]
            else:  # LAST
                keep = group.sort_values("row").iloc[-1]
            for _, g in group.iterrows():
                if g["idx"] != keep["idx"]:
                    drop.add(int(g["idx"]))
                    self.issue(DeckIssue.Level.DUPLICATE, int(g["row"]), "prefix", prefix,
                               f"Duplicate prefix {prefix} (rows {rows}): kept {keep['rate']:.6f} from row "
                               f"{int(keep['row'])} ({policy_label})")

        self.log(f"Resolved {dupes.groupby(['prefix', 'eff']).ngroups:,} duplicated prefixes, "
                 f"removed {len(drop):,} lines ({policy_label}).", "warning")
        return [c for i, c in enumerate(candidates) if i not in drop]

    # ------------------------------------------------------------ step 5: change detection
    def detect_changes(self, lines):
        self.changes = compare_with_live(self.deck, lines)
        notice = self.cfg["INCREASE_NOTICE_DAYS"]
        for line, (change, previous) in zip(lines, self.changes):
            if change == ChangeType.INCREASE:
                days = (line.effective_date - self.today).days
                if days < notice:
                    self.issue(DeckIssue.Level.WARNING, line.row_number, "effective_date", line.effective_date,
                               f"Increase on {line.prefix} ({previous:.4f} → {line.rate:.4f}) with "
                               f"{max(days, 0)} days notice (minimum {notice})")

    # ------------------------------------------------------------ step 6: save
    @transaction.atomic
    def save(self, body, lines, started):
        deck = self.deck
        objs = []
        counts = defaultdict(int)
        for line, (change, previous) in zip(lines, self.changes):
            counts[change] += 1
            objs.append(RateDeckLine(
                deck=deck, row_number=line.row_number, prefix=line.prefix, country=line.country,
                destination=line.destination, rate=line.rate, increment=line.increment,
                effective_date=line.effective_date, change=change, previous_rate=previous,
            ))
        RateDeckLine.objects.bulk_create(objs, batch_size=1000)
        DeckIssue.objects.bulk_create(self.issues, batch_size=1000)

        removed = removed_prefix_count(deck, lines) if deck.deck_type == RateDeck.DeckType.FULL else 0
        main_date = pd.Series([l.effective_date for l in lines]).mode().iloc[0] if lines else deck.default_effective_date

        deck.total_rows = len(body)
        deck.error_rows = self.error_rows
        deck.valid_rows = len(body) - self.error_rows
        deck.warning_count = sum(1 for i in self.issues if i.level == DeckIssue.Level.WARNING)
        deck.duplicate_count = sum(1 for i in self.issues if i.level == DeckIssue.Level.DUPLICATE)
        deck.prefix_count = len(lines)
        deck.expanded_count = self.expanded
        deck.new_count = counts[ChangeType.NEW]
        deck.increase_count = counts[ChangeType.INCREASE]
        deck.decrease_count = counts[ChangeType.DECREASE]
        deck.unchanged_count = counts[ChangeType.UNCHANGED]
        deck.removed_count = removed
        deck.effective_date = main_date
        deck.processed_at = timezone.now()
        deck.processing_ms = int((time.monotonic() - started) * 1000)
        deck.status = RateDeck.Status.VALIDATED if lines else RateDeck.Status.FAILED

        self.log(
            f"Changes vs current rates: {deck.new_count} new, {deck.increase_count} increases, "
            f"{deck.decrease_count} decreases, {deck.unchanged_count} unchanged"
            + (f", {removed} prefixes will be removed (full deck)." if removed else "."),
        )
        if lines:
            self.log(f"Ready to activate: {len(lines):,} prefixes, main effective date {main_date}.", "success")
        else:
            self.log("No valid rates found. Check the column mapping and the error report.", "error")
        deck.save()
        DeckLog.objects.bulk_create(self.logs)


# ---------------------------------------------------------------- shared helpers
def live_rows_by_prefix(vendor, prefixes=None):
    qs = VendorRate.objects.filter(vendor=vendor)
    if prefixes is not None:
        qs = qs.filter(prefix__in=list(prefixes))
    grouped = defaultdict(list)
    for r in qs.only("id", "prefix", "rate", "effective_from", "effective_to"):
        if not r.is_superseded:
            grouped[r.prefix].append(r)
    return grouped


def rate_on(rows, day):
    for r in rows:
        if r.effective_from <= day and (r.effective_to is None or r.effective_to > day):
            return r
    return None


def compare_with_live(deck, lines):
    """Return [(change, previous_rate)] for each line compared with the vendor's rate on that date."""
    existing = live_rows_by_prefix(deck.vendor, {l.prefix for l in lines})
    result = []
    for line in lines:
        current = rate_on(existing.get(line.prefix, []), line.effective_date)
        if current is None:
            result.append((ChangeType.NEW, None))
        elif line.rate > current.rate:
            result.append((ChangeType.INCREASE, current.rate))
        elif line.rate < current.rate:
            result.append((ChangeType.DECREASE, current.rate))
        else:
            result.append((ChangeType.UNCHANGED, current.rate))
    return result


def removed_prefix_count(deck, lines):
    """For a full deck: vendor prefixes live on the deck date that are missing from the new file."""
    if not lines:
        return 0
    start = pd.Series([l.effective_date for l in lines]).mode().iloc[0]
    deck_prefixes = {l.prefix for l in lines}
    live = (VendorRate.objects.filter(vendor=deck.vendor).active_on(start)
            .values_list("prefix", flat=True).distinct())
    return sum(1 for p in live if p not in deck_prefixes)


def clear_results(deck):
    deck.lines.all().delete()
    deck.issues.all().delete()
    deck.logs.all().delete()


def process_deck(deck, options):
    clear_results(deck)
    deck.mapping = options
    try:
        return DeckProcessor(deck, options).run()
    except (reader.DeckReadError, ValueError) as exc:
        deck.status = RateDeck.Status.FAILED
        deck.processed_at = timezone.now()
        deck.save()
        DeckLog.objects.create(deck=deck, level="error", message=f"Processing failed: {exc}"[:300])
        raise
