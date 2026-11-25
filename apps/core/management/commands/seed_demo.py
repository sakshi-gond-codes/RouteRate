"""
Load the RouteRate demo: countries, users, vendors, customers, margin rules, blocks,
and a realistic history built by running the sample rate decks through the REAL
processing pipeline (upload -> map -> validate -> activate), then LCR and rate sheets.

    python manage.py seed_demo            # load demo data (refuses if data exists)
    python manage.py seed_demo --reset    # wipe everything and load again
    python manage.py seed_demo --if-empty # do nothing when data already exists (used by setup.bat)

All vendors, customers, people and rates are fictional.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.data.countries import COUNTRIES
from apps.core.models import ActivityLog, Country
from apps.ratedecks.models import ColumnMapping, DeckLog, RateDeck, VendorRate
from apps.ratedecks.services import reader
from apps.ratedecks.services.activation import activate_deck, discard_deck
from apps.ratedecks.services.mapping import suggest_mapping
from apps.ratedecks.services.processor import process_deck
from apps.routing.models import BlockedDestination, Customer, LcrRun, MarginRule, RateSheet
from apps.routing.services.lcr import run_lcr
from apps.routing.services.ratesheet import generate_rate_sheet
from apps.vendors.models import Vendor

SAMPLES = Path(settings.BASE_DIR) / "sample_data"
DEMO_PASSWORD = "RouteRate@123"

USERS = [
    ("admin", "Aarav", "Shah", "admin", "aarav.shah@routerate.example.com"),
    ("analyst", "Nadia", "Rahman", "analyst", "nadia.rahman@routerate.example.com"),
    ("viewer", "Leo", "Fernandes", "viewer", "leo.fernandes@routerate.example.com"),
]

VENDORS = [
    # name, code, priority, increment, contact
    ("Kestrel Voice Networks", "KST", 1, "60/60", "Maya Collins", "rates@kestrel-voice.example.com"),
    ("Orchid Telecom", "ORC", 2, "1/1", "Ken Watanabe", "pricing@orchid-telecom.example.com"),
    ("Tidewater Carrier", "TDW", 3, "60/60", "Amara Okafor", "noc@tidewater-carrier.example.com"),
    ("Quillon Wholesale", "QLN", 4, "60/60", "Ravi Menon", "ratedesk@quillon.example.com"),
    ("Zephyr Route", "ZPH", 5, "60/60", "Elena Petrova", "ratedecks@zephyr-route.example.com"),
]

CUSTOMERS = [
    # name, code, increment, notice days, email
    ("Harborline Communications", "HRB", "60/60", 7, "voice.buying@harborline.example.com"),
    ("Saffron Contact Centre", "SAF", "1/1", 7, "telecom@saffron-cc.example.com"),
    ("Mapleview VoIP", "MPV", "60/60", 14, "carrier@mapleview.example.com"),
]

# file, vendor, deck type, default effective date, upload date, duplicate policy, uploaded by, action
DECKS = [
    ("rate_decks/01_kestrel_voice_full_az.csv", "KST", "full", date(2026, 8, 1), date(2026, 7, 29), "lowest", "analyst", "activate"),
    ("rate_decks/02_orchid_telecom_rates.xlsx", "ORC", "full", date(2026, 8, 15), date(2026, 8, 12), "lowest", "analyst", "activate"),
    ("rate_decks/03_tidewater_carrier_deck.csv", "TDW", "full", date(2026, 8, 20), date(2026, 8, 18), "lowest", "admin", "activate"),
    ("rate_decks/04_quillon_wholesale_az.xlsx", "QLN", "full", date(2026, 9, 1), date(2026, 8, 28), "lowest", "analyst", "activate"),
    ("rate_decks/05_zephyr_route_full.csv", "ZPH", "full", date(2026, 9, 5), date(2026, 9, 2), "lowest", "analyst", "activate"),
    ("rate_decks/06_kestrel_voice_update_partial.csv", "KST", "partial", date(2026, 10, 1), date(2026, 9, 24), "lowest", "analyst", "activate"),
    ("try_it_yourself/messy_vendor_deck.csv", "QLN", "partial", None, None, "lowest", "analyst", "discard"),
    ("try_it_yourself/orchid_price_update.xlsx", "ORC", "partial", None, None, "lowest", "analyst", "leave"),
]


def at(day, hour=10, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class Command(BaseCommand):
    help = "Load fictional demo data (users, vendors, rate decks, LCR runs and rate sheets)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing data first")
        parser.add_argument("--if-empty", action="store_true", help="Skip when data already exists")

    def handle(self, *args, **opts):
        has_data = Vendor.objects.exists() or RateDeck.objects.exists()
        if has_data and opts["if_empty"]:
            self.stdout.write("Demo data already present, nothing to do. Use reset_demo.bat to reload it.")
            return
        if has_data and not opts["reset"]:
            raise CommandError("Data already exists. Run with --reset to wipe it and load the demo again.")
        if opts["reset"]:
            self.wipe()

        self.today = timezone.localdate()
        self.load_reference()
        self.load_decks()
        self.load_routing()
        self.print_summary()

    # ------------------------------------------------------------ helpers
    def wipe(self):
        self.stdout.write("Removing existing data...")
        for model in (RateSheet, LcrRun, MarginRule, BlockedDestination, Customer, VendorRate, RateDeck,
                      ColumnMapping, Vendor, ActivityLog, Country):
            model.objects.all().delete()
        User.objects.filter(username__in=[u[0] for u in USERS]).delete()

    def backdate_log(self, when):
        """Move the newest activity entry to a past time so the demo history reads naturally."""
        last = ActivityLog.objects.order_by("-id").first()
        if last:
            ActivityLog.objects.filter(pk=last.pk).update(created_at=when)

    @transaction.atomic
    def load_reference(self):
        for name, iso, code, region, aliases in COUNTRIES:
            Country.objects.update_or_create(dial_code=code, defaults={
                "name": name, "iso_code": iso, "region": region, "aliases": aliases})
        self.stdout.write(f"  {len(COUNTRIES)} countries and dial codes")

        self.users = {}
        for username, first, last, role, email in USERS:
            user = User(username=username, first_name=first, last_name=last, role=role, email=email,
                        is_staff=(role == "admin"), is_superuser=(role == "admin"))
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.users[username] = user
        self.stdout.write(f"  {len(USERS)} users (password {DEMO_PASSWORD})")

        self.vendors = {}
        for name, code, priority, inc, contact, email in VENDORS:
            v = Vendor.objects.create(name=name, code=code, priority=priority, default_increment=inc,
                                      contact_name=contact, contact_email=email,
                                      notes="Fictional demo vendor.")
            Vendor.objects.filter(pk=v.pk).update(created_at=at(date(2026, 7, 20)))
            self.vendors[code] = v
        self.stdout.write(f"  {len(VENDORS)} vendors")

    # ------------------------------------------------------------ decks
    def load_decks(self):
        for path, code, deck_type, default_date, upload_day, policy, who, action in DECKS:
            vendor = self.vendors[code]
            user = self.users[who]
            upload_day = upload_day or self.today - timedelta(days=1 if action == "discard" else 0)
            default_date = default_date or self.today
            uploaded_at = at(upload_day, 9 if action != "leave" else 8, 30)
            src = SAMPLES / path

            deck = RateDeck(vendor=vendor, original_filename=src.name, file_type=reader.file_type_from_name(src.name),
                            deck_type=deck_type, default_effective_date=default_date, duplicate_policy=policy,
                            uploaded_by=user)
            with open(src, "rb") as fh:
                deck.file.save(src.name, File(fh), save=True)
            RateDeck.objects.filter(pk=deck.pk).update(uploaded_at=uploaded_at)
            deck.refresh_from_db()
            ActivityLog.record(user, "upload", f"Uploaded {deck.original_filename} for {vendor.name}")
            self.backdate_log(uploaded_at)

            raw, info = reader.read_raw(deck.file.path, deck.file_type)
            header = reader.detect_header_row(raw)
            columns = suggest_mapping(reader.column_labels(raw, header))
            options = {"columns": columns, "header_row": header, "sheet": info["sheet"], "date_order": "DMY"}
            process_deck(deck, options)
            ColumnMapping.objects.update_or_create(vendor=vendor, defaults={
                "columns": columns, "header_row": header, "sheet_name": info["sheet"], "date_order": "DMY"})
            processed_at = uploaded_at + timedelta(minutes=4)
            RateDeck.objects.filter(pk=deck.pk).update(processed_at=processed_at)
            DeckLog.objects.filter(deck=deck).update(created_at=processed_at)
            deck.refresh_from_db()
            ActivityLog.record(user, "process", f"Processed {code} deck #{deck.pk}: {deck.prefix_count} prefixes, "
                                                f"{deck.error_rows} rejected rows")
            self.backdate_log(processed_at)

            if action == "activate":
                activate_deck(deck, user)
                activated_at = uploaded_at + timedelta(minutes=12)
                RateDeck.objects.filter(pk=deck.pk).update(activated_at=activated_at)
                Vendor.objects.filter(pk=vendor.pk).update(last_deck_at=activated_at)
                DeckLog.objects.filter(deck=deck, level="success", message__startswith="Activated").update(created_at=activated_at)
                self.backdate_log(activated_at)
            elif action == "discard":
                discard_deck(deck, user)
                self.backdate_log(uploaded_at + timedelta(minutes=20))
            deck.refresh_from_db()
            self.stdout.write(f"  deck #{deck.pk} {code} {src.name}: {deck.get_status_display()}, "
                              f"{deck.prefix_count} prefixes, {deck.error_rows} rejected, {deck.warning_count} warnings")

    # ------------------------------------------------------------ routing
    def load_routing(self):
        admin, analyst = self.users["admin"], self.users["analyst"]
        customers = {}
        for name, code, inc, notice, email in CUSTOMERS:
            customers[code] = Customer.objects.create(name=name, code=code, billing_increment=inc, notice_days=notice,
                                                      contact_email=email, notes="Fictional demo customer.")
        country = {c.dial_code: c for c in Country.objects.all()}
        D = Decimal
        rules = [
            ("Standard markup", None, None, "", "percent", D("12"), D("0.0005")),
            ("India - competitive", None, country["91"], "", "percent", D("6"), D("0.0004")),
            ("UK mobile - fixed uplift", None, None, "447", "fixed", D("0.0018"), D("0")),
            ("Nigeria - risk premium", None, country["234"], "", "percent", D("15"), D("0.0020")),
            ("Harborline volume deal", customers["HRB"], None, "", "percent", D("9"), D("0.0004")),
            ("Saffron India mobile", customers["SAF"], None, "91", "percent", D("4"), D("0.0003")),
            ("Mapleview North America", customers["MPV"], country["1"], "", "fixed", D("0.0008"), D("0")),
        ]
        for name, cust, ctry, prefix, kind, value, min_margin in rules:
            MarginRule.objects.create(name=name, customer=cust, country=ctry, prefix=prefix, kind=kind, value=value,
                                      min_margin=min_margin)
        blocks = [
            ("8816", None, "Satellite (Iridium) is not offered to customers"),
            ("870", None, "Satellite (Inmarsat) is not offered to customers"),
            ("2348", self.vendors["TDW"], "High call failure rate on Nigeria mobile (fictional test result)"),
            ("9665", self.vendors["ORC"], "Caller ID not delivered on Saudi mobile (fictional test result)"),
        ]
        for prefix, vendor, reason in blocks:
            BlockedDestination.objects.create(prefix=prefix, vendor=vendor, reason=reason, created_by=analyst)
        self.stdout.write(f"  {len(customers)} customers, {len(rules)} margin rules, {len(blocks)} blocked destinations")

        # Historic LCR and first rate sheets (before the Kestrel price update)
        past_day = date(2026, 9, 15)
        run1 = run_lcr(past_day, analyst, "Monthly pricing review - September")
        LcrRun.objects.filter(pk=run1.pk).update(created_at=at(past_day, 11))
        self.backdate_log(at(past_day, 11))
        for code in ("HRB", "SAF", "MPV"):
            sheet = generate_rate_sheet(customers[code], run1, past_day + timedelta(days=1), analyst,
                                        "September price list", issue_date=past_day)
            RateSheet.objects.filter(pk=sheet.pk).update(created_at=at(past_day, 11, 30))
            self.backdate_log(at(past_day, 11, 30))

        # Current LCR and updated sheets for two customers
        run2 = run_lcr(self.today, admin, "Routing refresh after Kestrel price update")
        for code in ("HRB", "SAF"):
            generate_rate_sheet(customers[code], run2, self.today + timedelta(days=1), admin, "Updated price list")
        self.stdout.write(f"  LCR runs #{run1.pk} (as of {past_day}) and #{run2.pk} (today), 5 rate sheets")

    def print_summary(self):
        live = VendorRate.objects.active_on(self.today).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nDemo ready: {live:,} live vendor rates. Log in as admin / analyst / viewer "
            f"with password {DEMO_PASSWORD}"))
