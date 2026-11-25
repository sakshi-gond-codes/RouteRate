"""
Effective-date management: applying a validated deck to the live routing table.

Rates are stored as periods [effective_from, effective_to). Activating a deck never
deletes history. For every prefix in the deck, starting on date S:

  * the rate that is live on S is closed on S (effective_to = S)
  * a rate that was scheduled to start exactly on S is superseded
  * a rate scheduled for a later date is kept, and the new rate ends when it starts

For a FULL (A-Z) deck, vendor prefixes missing from the file are closed on the
deck's main effective date. A PARTIAL deck only changes the prefixes it contains.
"""
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.core.models import ActivityLog
from apps.vendors.models import Vendor

from ..models import ChangeType, DeckLog, RateDeck, RateDeckLine, VendorRate
from .processor import rate_on


class ActivationError(Exception):
    pass


@transaction.atomic
def activate_deck(deck: RateDeck, user):
    deck = RateDeck.objects.select_for_update().get(pk=deck.pk)
    if not deck.can_activate:
        raise ActivationError("Only validated decks with at least one valid rate can be activated.")
    vendor = Vendor.objects.select_for_update().get(pk=deck.vendor_id)

    lines = list(deck.lines.order_by("prefix", "effective_date"))
    existing = defaultdict(list)
    for r in VendorRate.objects.filter(vendor=vendor):
        if not r.is_superseded:
            existing[r.prefix].append(r)

    dirty = {}          # saved rows whose effective_to changed
    new_rows = []
    counts = defaultdict(int)

    for line in lines:
        rows = existing[line.prefix]
        start = line.effective_date
        current = rate_on(rows, start)

        if current is None:
            change, previous = ChangeType.NEW, None
        elif line.rate > current.rate:
            change, previous = ChangeType.INCREASE, current.rate
        elif line.rate < current.rate:
            change, previous = ChangeType.DECREASE, current.rate
        else:
            change, previous = ChangeType.UNCHANGED, current.rate
        counts[change] += 1
        line.change, line.previous_rate = change, previous

        for r in rows:
            if r.is_superseded:
                continue
            if r.effective_from == start:
                r.effective_to = r.effective_from          # replaced before / on its first day
            elif r.effective_from < start and (r.effective_to is None or r.effective_to > start):
                r.effective_to = start                     # close the running rate
            else:
                continue
            if r.pk:
                dirty[r.pk] = r

        next_start = min((r.effective_from for r in rows
                          if not r.is_superseded and r.effective_from > start), default=None)
        new = VendorRate(
            vendor=vendor, deck=deck, prefix=line.prefix, country_id=line.country_id,
            destination=line.destination, rate=line.rate, increment=line.increment,
            effective_from=start, effective_to=next_start, change=change, previous_rate=previous,
        )
        rows.append(new)
        new_rows.append(new)

    removed = 0
    if deck.deck_type == RateDeck.DeckType.FULL:
        close_on = deck.effective_date or deck.default_effective_date
        in_deck = {l.prefix for l in lines}
        for prefix, rows in existing.items():
            if prefix in in_deck:
                continue
            closed = False
            for r in rows:
                if r.is_superseded:
                    continue
                if r.effective_from >= close_on:
                    r.effective_to = r.effective_from
                elif r.effective_to is None or r.effective_to > close_on:
                    r.effective_to = close_on
                    closed = True
                else:
                    continue
                if r.pk:
                    dirty[r.pk] = r
            removed += int(closed)

    VendorRate.objects.bulk_update(list(dirty.values()), ["effective_to"], batch_size=1000)
    VendorRate.objects.bulk_create(new_rows, batch_size=1000)
    RateDeckLine.objects.bulk_update(lines, ["change", "previous_rate"], batch_size=1000)

    now = timezone.now()
    deck.status = RateDeck.Status.ACTIVE
    deck.activated_at = now
    deck.activated_by = user
    deck.new_count = counts[ChangeType.NEW]
    deck.increase_count = counts[ChangeType.INCREASE]
    deck.decrease_count = counts[ChangeType.DECREASE]
    deck.unchanged_count = counts[ChangeType.UNCHANGED]
    deck.removed_count = removed
    deck.save()
    vendor.last_deck_at = now
    vendor.save(update_fields=["last_deck_at"])

    DeckLog.objects.create(
        deck=deck, level="success",
        message=(f"Activated by {getattr(user, 'username', 'system')}: {len(new_rows):,} rates added, "
                 f"{len(dirty):,} existing periods closed, {removed:,} prefixes removed."),
    )
    ActivityLog.record(user, "activate",
                       f"Activated {vendor.code} deck #{deck.pk} ({len(new_rows):,} rates, "
                       f"{counts[ChangeType.INCREASE]} increases, {counts[ChangeType.DECREASE]} decreases)")
    return deck


def discard_deck(deck: RateDeck, user):
    if deck.status == RateDeck.Status.ACTIVE:
        raise ActivationError("An active deck cannot be discarded. Upload a newer deck instead.")
    deck.status = RateDeck.Status.DISCARDED
    deck.save(update_fields=["status"])
    DeckLog.objects.create(deck=deck, level="warning", message=f"Discarded by {getattr(user, 'username', 'system')}.")
    ActivityLog.record(user, "discard", f"Discarded {deck.vendor.code} deck #{deck.pk} ({deck.original_filename})")
