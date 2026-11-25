"""Shared helpers for the test suite."""
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.core.data.countries import COUNTRIES
from apps.core.models import Country
from apps.ratedecks.models import RateDeck
from apps.ratedecks.services.activation import activate_deck
from apps.ratedecks.services.processor import process_deck
from apps.vendors.models import Vendor

PASSWORD = "Test@Pass123"


def load_countries():
    Country.objects.bulk_create([
        Country(name=n, iso_code=iso, dial_code=code, region=region, aliases=aliases)
        for n, iso, code, region, aliases in COUNTRIES
    ])


def make_user(username="analyst", role="analyst"):
    user = User(username=username, role=role, first_name=username.title())
    user.set_password(PASSWORD)
    user.save()
    return user


def make_vendor(code="AAA", priority=5, **kw):
    return Vendor.objects.create(name=kw.pop("name", f"Vendor {code}"), code=code, priority=priority, **kw)


def csv_deck(vendor, rows, user=None, deck_type="full", effective=date(2026, 1, 1), policy="lowest",
             header=("Destination", "Prefix", "Rate", "Effective Date")):
    """Create a RateDeck from a list of rows (tuples matching `header`)."""
    text = ",".join(header) + "\n" + "\n".join(",".join(f'"{c}"' if "," in str(c) else str(c) for c in r) for r in rows)
    deck = RateDeck(vendor=vendor, original_filename="test.csv", file_type="csv", deck_type=deck_type,
                    default_effective_date=effective, duplicate_policy=policy, uploaded_by=user)
    deck.file.save("test.csv", SimpleUploadedFile("test.csv", text.encode()), save=True)
    return deck


DEFAULT_COLUMNS = {"destination": "Destination", "prefix": "Prefix", "rate": "Rate", "effective_date": "Effective Date"}


def process(deck, columns=None, header_row=1, date_order="DMY"):
    process_deck(deck, {"columns": columns or DEFAULT_COLUMNS, "header_row": header_row, "sheet": "",
                        "date_order": date_order})
    deck.refresh_from_db()
    return deck


def load_rates(vendor, rates, user=None, effective=date(2026, 1, 1), deck_type="full"):
    """Upload, process and activate a simple deck: rates = {prefix: rate}."""
    rows = [("", p, r, effective.isoformat()) for p, r in rates.items()]
    deck = process(csv_deck(vendor, rows, user, deck_type=deck_type, effective=effective))
    return activate_deck(deck, user)


D = Decimal
