"""
Customer rate sheet generation.

Sell rate = LCR primary cost + the matching margin rule.
Every line is compared with the customer's previous sheet:
  New / Increase / Decrease / Unchanged, and prefixes no longer offered are listed as Removed.

Rate increases respect the customer's notice period (default 7 days): if the sheet
date is sooner, the increase is moved to issue date + notice days and flagged.
"""
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.models import ActivityLog
from apps.ratedecks.models import ChangeType

from ..models import LcrEntry, RateSheet, RateSheetLine
from .pricing import MarginResolver


class RateSheetError(Exception):
    pass


@transaction.atomic
def generate_rate_sheet(customer, lcr_run, effective_date, user=None, notes="", issue_date=None):
    if not customer.is_active:
        raise RateSheetError("This customer is inactive.")
    issue_date = issue_date or timezone.localdate()
    entries = list(
        lcr_run.entries.filter(status__in=[LcrEntry.Status.ROUTED, LcrEntry.Status.SINGLE])
        .select_related("primary_vendor", "backup_vendor")
    )
    if not entries:
        raise RateSheetError("The selected LCR run has no routable prefixes.")

    previous = customer.rate_sheets.order_by("-version").first()
    prev_lines = {}
    if previous:
        prev_lines = {l.prefix: l for l in previous.lines.exclude(change=ChangeType.REMOVED)}

    version = (previous.version + 1) if previous else 1
    sheet = RateSheet.objects.create(
        customer=customer, lcr_run=lcr_run, version=version, effective_date=effective_date,
        reference=f"{customer.code}-{effective_date:%Y%m%d}-v{version}", created_by=user, notes=notes,
    )

    resolver = MarginResolver(customer)
    notice_date = issue_date + timedelta(days=customer.notice_days)
    lines, counts = [], Counter()
    total_cost = total_sell = Decimal("0")

    for e in entries:
        rule = resolver.rule_for(e.prefix, e.country_id)
        sell = resolver.sell_rate(e.primary_rate, rule)
        prev = prev_lines.get(e.prefix)
        if prev is None:
            change = ChangeType.NEW
        elif sell > prev.rate:
            change = ChangeType.INCREASE
        elif sell < prev.rate:
            change = ChangeType.DECREASE
        else:
            change = ChangeType.UNCHANGED

        line_date = effective_date
        notice_applied = False
        if change == ChangeType.INCREASE and line_date < notice_date:
            line_date, notice_applied = notice_date, True
        if change == ChangeType.UNCHANGED and prev is not None:
            line_date = min(prev.effective_date, effective_date)

        counts[change] += 1
        total_cost += e.primary_rate
        total_sell += sell
        lines.append(RateSheetLine(
            sheet=sheet, prefix=e.prefix, country_id=e.country_id, destination=e.destination,
            rate=sell, previous_rate=prev.rate if prev else None, cost=e.primary_rate,
            vendor=e.primary_vendor, backup_vendor=e.backup_vendor, margin_rule=rule,
            increment=customer.billing_increment, effective_date=line_date, change=change,
            notice_applied=notice_applied,
        ))

    current_prefixes = {e.prefix for e in entries}
    for prefix, prev in prev_lines.items():
        if prefix not in current_prefixes:
            counts[ChangeType.REMOVED] += 1
            lines.append(RateSheetLine(
                sheet=sheet, prefix=prefix, country_id=prev.country_id, destination=prev.destination,
                rate=prev.rate, previous_rate=prev.rate, cost=None, increment=prev.increment,
                effective_date=effective_date, change=ChangeType.REMOVED,
            ))

    RateSheetLine.objects.bulk_create(lines, batch_size=1000)

    sheet.line_count = len(lines)
    sheet.new_count = counts[ChangeType.NEW]
    sheet.increase_count = counts[ChangeType.INCREASE]
    sheet.decrease_count = counts[ChangeType.DECREASE]
    sheet.unchanged_count = counts[ChangeType.UNCHANGED]
    sheet.removed_count = counts[ChangeType.REMOVED]
    sheet.notice_adjusted_count = sum(1 for l in lines if l.notice_applied)
    sheet.avg_cost = total_cost / len(entries)
    sheet.avg_sell = total_sell / len(entries)
    sheet.avg_margin_pct = ((total_sell - total_cost) / total_sell * 100).quantize(Decimal("0.01")) if total_sell else None
    sheet.save()

    ActivityLog.record(user, "ratesheet",
                       f"Generated rate sheet {sheet.reference} for {customer.name}: {sheet.line_count:,} lines, "
                       f"{sheet.increase_count} increases, {sheet.decrease_count} decreases")
    return sheet
