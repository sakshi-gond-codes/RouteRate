"""
Prefix-based vendor comparison and Least Cost Routing (LCR).

For every prefix that any active vendor sells, we find each vendor's price using
the *longest matching prefix* in that vendor's deck. Example: for 4475 a vendor
that only quotes 447 still has a price (its 447 rate), shown as "via 447".
A fallback never crosses a country boundary: the vendor's "1" (USA & Canada)
rate is NOT a price for 1876 (Jamaica), which has its own country code.

Vendors are then ranked by price (tie-breaker: vendor priority, then name).
Rank 1 is the primary route, rank 2 the backup, rank 3 a second backup.

Blocked destinations:
  * without a vendor  -> the prefix (and everything under it) is not routed at all
  * with a vendor     -> only that vendor is skipped for the prefix
"""
import time
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg

from apps.core.countries import CountryIndex
from apps.core.models import ActivityLog
from apps.ratedecks.models import VendorRate
from apps.vendors.models import Vendor

from ..models import BlockedDestination, LcrEntry, LcrRun


@dataclass
class Quote:
    vendor: Vendor
    rate: Decimal
    matched_prefix: str
    destination: str
    exact: bool
    blocked_reason: str = ""

    @property
    def via(self):
        return "" if self.exact else self.matched_prefix


@dataclass
class MatrixRow:
    prefix: str
    country: object
    destination: str
    quotes: dict = field(default_factory=dict)      # vendor_id -> Quote
    ranked: list = field(default_factory=list)      # usable quotes, cheapest first
    blocked_reason: str = ""

    @property
    def status(self):
        if self.blocked_reason:
            return LcrEntry.Status.BLOCKED
        if not self.ranked:
            return LcrEntry.Status.NO_ROUTE
        if len(self.ranked) == 1:
            return LcrEntry.Status.SINGLE
        return LcrEntry.Status.ROUTED

    def rank_of(self, vendor_id):
        for i, q in enumerate(self.ranked, start=1):
            if q.vendor.id == vendor_id:
                return i
        return None

    @property
    def spread_pct(self):
        """Difference between the most and least expensive usable vendor."""
        if len(self.ranked) < 2:
            return None
        low, high = self.ranked[0].rate, self.ranked[-1].rate
        return float((high - low) / low * 100) if low else None


def longest_match(prefix, table):
    """Return the longest key of `table` that the prefix starts with, or None."""
    for n in range(len(prefix), 0, -1):
        if prefix[:n] in table:
            return prefix[:n]
    return None


class BlockIndex:
    def __init__(self):
        self.global_blocks = {}
        self.vendor_blocks = {}
        for b in BlockedDestination.objects.filter(is_active=True):
            if b.vendor_id:
                self.vendor_blocks.setdefault(b.vendor_id, {})[b.prefix] = b.reason
            else:
                self.global_blocks[b.prefix] = b.reason

    def global_reason(self, prefix):
        hit = longest_match(prefix, self.global_blocks)
        return self.global_blocks[hit] if hit else ""

    def vendor_reason(self, vendor_id, prefix):
        table = self.vendor_blocks.get(vendor_id, {})
        hit = longest_match(prefix, table)
        return table[hit] if hit else ""


def load_vendor_tables(as_of, vendors):
    """{vendor_id: {prefix: (rate, destination)}} for rates live on `as_of`."""
    tables = {v.id: {} for v in vendors}
    rows = (VendorRate.objects.active_on(as_of).filter(vendor__in=vendors)
            .values_list("vendor_id", "prefix", "rate", "destination"))
    for vendor_id, prefix, rate, destination in rows:
        tables[vendor_id][prefix] = (rate, destination)
    return tables


def build_matrix(as_of, country_id=None, prefix_search="", vendors=None):
    """Compare every active vendor on every prefix. Returns (vendors, rows)."""
    vendors = list(vendors if vendors is not None else Vendor.objects.filter(is_active=True).order_by("priority", "name"))
    tables = load_vendor_tables(as_of, vendors)
    countries = CountryIndex()
    blocks = BlockIndex()

    universe = set()
    for table in tables.values():
        universe.update(table)
    if prefix_search:
        universe = {p for p in universe if p.startswith(prefix_search)}

    rows = []
    for prefix in sorted(universe):
        country = countries.resolve(prefix)
        if country_id and (country is None or country.id != int(country_id)):
            continue
        row = MatrixRow(prefix=prefix, country=country, destination="")
        row.blocked_reason = blocks.global_reason(prefix)

        for v in vendors:
            table = tables[v.id]
            hit = longest_match(prefix, table)
            if hit is None:
                continue
            # Never fall back across a country boundary: a vendor with only "1" (USA & Canada)
            # does not sell Jamaica (1876), and its US rate must not be used for it.
            if country and hit != prefix and len(hit) < len(country.dial_code):
                continue
            rate, destination = table[hit]
            row.quotes[v.id] = Quote(v, rate, hit, destination, exact=(hit == prefix),
                                     blocked_reason=blocks.vendor_reason(v.id, prefix))

        # Destination name: the most preferred vendor that quotes this exact prefix
        exact = [q for q in row.quotes.values() if q.exact]
        row.destination = (min(exact, key=lambda q: (q.vendor.priority, q.vendor.name)).destination
                           if exact else (country.name if country else prefix))

        if not row.blocked_reason:
            usable = [q for q in row.quotes.values() if not q.blocked_reason]
            row.ranked = sorted(usable, key=lambda q: (q.rate, q.vendor.priority, q.vendor.name))
        rows.append(row)
    return vendors, rows


@transaction.atomic
def run_lcr(as_of, user=None, notes=""):
    """Calculate LCR for all prefixes and save it as an LcrRun with one entry per prefix."""
    started = time.monotonic()
    vendors, rows = build_matrix(as_of)
    run = LcrRun.objects.create(as_of_date=as_of, created_by=user, notes=notes, vendor_count=len(vendors))

    entries = []
    for row in rows:
        r = row.ranked
        entries.append(LcrEntry(
            run=run, prefix=row.prefix, country=row.country, destination=row.destination,
            status=row.status, vendor_count=len(r),
            primary_vendor=r[0].vendor if r else None, primary_rate=r[0].rate if r else None,
            primary_via=r[0].via if r else "",
            backup_vendor=r[1].vendor if len(r) > 1 else None, backup_rate=r[1].rate if len(r) > 1 else None,
            backup_via=r[1].via if len(r) > 1 else "",
            third_vendor=r[2].vendor if len(r) > 2 else None, third_rate=r[2].rate if len(r) > 2 else None,
            note=row.blocked_reason[:200],
        ))
    LcrEntry.objects.bulk_create(entries, batch_size=1000)

    status_counts = {s: 0 for s in LcrEntry.Status.values}
    for e in entries:
        status_counts[e.status] += 1
    run.prefix_count = len(entries)
    run.routed_count = status_counts[LcrEntry.Status.ROUTED]
    run.single_route_count = status_counts[LcrEntry.Status.SINGLE]
    run.no_route_count = status_counts[LcrEntry.Status.NO_ROUTE]
    run.blocked_count = status_counts[LcrEntry.Status.BLOCKED]
    run.avg_primary_rate = run.entries.filter(primary_rate__isnull=False).aggregate(a=Avg("primary_rate"))["a"]
    run.duration_ms = int((time.monotonic() - started) * 1000)
    run.save()

    ActivityLog.record(user, "lcr", f"LCR run #{run.pk} as of {as_of}: {run.prefix_count:,} prefixes, "
                                    f"{run.single_route_count} without backup, {run.blocked_count} blocked")
    return run
