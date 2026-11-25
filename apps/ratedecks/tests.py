from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from apps.core.testing import csv_deck, load_countries, load_rates, make_user, make_vendor, process

from .models import ChangeType, DeckIssue, RateDeck, VendorRate
from .services import reader
from .services.activation import ActivationError, activate_deck, discard_deck
from .services.mapping import suggest_mapping
from .services.normalize import NormalizeError, parse_date, parse_increment, parse_prefixes, parse_rate

SAMPLES = Path(settings.BASE_DIR) / "sample_data"


class NormalizePrefixTests(SimpleTestCase):
    def test_plain_and_international_formats(self):
        self.assertEqual(parse_prefixes("447"), ["447"])
        self.assertEqual(parse_prefixes("+44 7"), ["447"])
        self.assertEqual(parse_prefixes("0049 151"), ["49151"])
        self.assertEqual(parse_prefixes("(44) 7.1"), ["4471"])

    def test_lists_and_ranges(self):
        self.assertEqual(parse_prefixes("44, 447; 4471"), ["44", "447", "4471"])
        self.assertEqual(parse_prefixes("4470-4473"), ["4470", "4471", "4472", "4473"])
        self.assertEqual(parse_prefixes("44, 44"), ["44"])

    def test_invalid_prefixes(self):
        for bad in ["ABC", "", "052", "4479-4470", "447-44799", "1" * 16, "4400-4999"]:
            with self.subTest(bad=bad), self.assertRaises(NormalizeError):
                parse_prefixes(bad)


class NormalizeValueTests(SimpleTestCase):
    def test_rates(self):
        self.assertEqual(parse_rate("0.0125"), Decimal("0.012500"))
        self.assertEqual(parse_rate("$0.0125"), Decimal("0.012500"))
        self.assertEqual(parse_rate("0,0125"), Decimal("0.012500"))
        self.assertEqual(parse_rate(" 0.0125 USD"), Decimal("0.012500"))
        self.assertEqual(parse_rate("1.234,50".replace("1.234", "1")), Decimal("1.500000"))
        for bad in ["", "-0.01", "0", "free", "12.5"]:
            with self.subTest(bad=bad), self.assertRaises(NormalizeError):
                parse_rate(bad)

    def test_dates(self):
        default = date(2026, 1, 1)
        self.assertEqual(parse_date("", default), default)
        self.assertEqual(parse_date("Immediate", default), default)
        self.assertEqual(parse_date("2026-10-05", default), date(2026, 10, 5))  # ISO is never day-first
        self.assertEqual(parse_date("05/10/2026", default, "DMY"), date(2026, 10, 5))
        self.assertEqual(parse_date("10/05/2026", default, "MDY"), date(2026, 10, 5))
        self.assertEqual(parse_date("15.10.2026", default), date(2026, 10, 15))
        self.assertEqual(parse_date("15-Oct-2026", default), date(2026, 10, 15))
        self.assertEqual(parse_date("46310", default), date(2026, 10, 15))     # Excel serial number
        for bad in ["31/02/2026", "2026-13-01", "soon"]:
            with self.subTest(bad=bad), self.assertRaises(NormalizeError):
                parse_date(bad, default)

    def test_increments(self):
        self.assertEqual(parse_increment("", "60/60"), "60/60")
        self.assertEqual(parse_increment("1/1", "60/60"), "1/1")
        self.assertEqual(parse_increment("60-60", "60/60"), "60/60")
        self.assertEqual(parse_increment("30", "60/60"), "30/30")
        with self.assertRaises(NormalizeError):
            parse_increment("sixty", "60/60")


class MappingTests(SimpleTestCase):
    def test_suggests_by_alias(self):
        cols = ["Country", "Description", "Dial Codes", "Price USD/min", "Valid From", "Interval"]
        self.assertEqual(suggest_mapping(cols), {
            "prefix": "Dial Codes", "rate": "Price USD/min", "destination": "Description",
            "country": "Country", "effective_date": "Valid From", "increment": "Interval"})

    def test_breakout_is_a_destination_and_old_rate_is_ignored(self):
        m = suggest_mapping(["Breakout", "Code", "Old Rate", "New Rate"])
        self.assertEqual(m["destination"], "Breakout")
        self.assertEqual(m["prefix"], "Code")
        self.assertEqual(m["rate"], "New Rate")

    def test_saved_mapping_wins(self):
        m = suggest_mapping(["Code", "Price", "Cost"], saved={"rate": "cost"})
        self.assertEqual(m["rate"], "Cost")


class ReaderTests(SimpleTestCase):
    def test_semicolon_csv_with_title_rows(self):
        raw, info = reader.read_raw(SAMPLES / "rate_decks/03_tidewater_carrier_deck.csv", "csv")
        self.assertEqual(info["delimiter"], ";")
        header = reader.detect_header_row(raw)
        self.assertEqual(header, 4)
        self.assertEqual(reader.column_labels(raw, header), ["Code", "Description", "Cost", "Billing"])

    def test_excel_with_title_rows_and_numbers(self):
        raw, info = reader.read_raw(SAMPLES / "rate_decks/04_quillon_wholesale_az.xlsx", "xlsx")
        body = reader.data_frame(raw, reader.detect_header_row(raw))
        self.assertTrue(body["Prefix"].str.fullmatch(r"\d+").all())  # 447 not 447.0

    def test_rejects_xls(self):
        with self.assertRaises(reader.DeckReadError):
            reader.file_type_from_name("old.xls")


class ProcessingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_countries()
        cls.user = make_user()

    def test_messy_rows_are_rejected_with_reasons(self):
        vendor = make_vendor()
        rows = [
            ("UK", "44", "0.004", "2026-01-01"),
            ("Unknown", "ABC", "0.01", ""),
            ("Nowhere", "999123", "0.02", ""),
            ("Spain", "34", "-0.01", ""),
            ("Italy", "39", "", ""),
            ("Portugal", "3519", "0.016", "31/02/2026"),
            ("France", "4916", "0.022", ""),          # name mismatch -> warning, kept
        ]
        deck = process(csv_deck(vendor, rows, self.user))
        self.assertEqual(deck.total_rows, 7)
        self.assertEqual(deck.error_rows, 5)
        self.assertEqual(deck.prefix_count, 2)
        messages = list(deck.issues.filter(level="error").values_list("message", flat=True))
        self.assertTrue(any("not digits" in m for m in messages))
        self.assertTrue(any("known country" in m for m in messages))
        self.assertTrue(any("negative" in m for m in messages))
        self.assertTrue(deck.issues.filter(level="warning", field="destination").exists())

    def test_duplicate_policies(self):
        rows = [("UK", "447", "0.0120", ""), ("UK", "447", "0.0100", ""), ("UK", "447", "0.0110", "")]
        expected = {"lowest": Decimal("0.0100"), "highest": Decimal("0.0120"), "last": Decimal("0.0110")}
        for i, (policy, rate) in enumerate(expected.items()):
            with self.subTest(policy=policy):
                deck = process(csv_deck(make_vendor(f"D{i}"), rows, self.user, policy=policy))
                self.assertEqual(deck.lines.get().rate, rate)
                self.assertEqual(deck.duplicate_count, 2)
        deck = process(csv_deck(make_vendor("DR"), rows, self.user, policy="reject"))
        self.assertEqual(deck.prefix_count, 0)
        self.assertEqual(deck.status, RateDeck.Status.FAILED)

    def test_lists_and_ranges_expand(self):
        deck = process(csv_deck(make_vendor(), [("UK", "4470-4472, 447", "0.01", "")], self.user))
        self.assertEqual(sorted(deck.lines.values_list("prefix", flat=True)), ["447", "4470", "4471", "4472"])
        self.assertEqual(deck.expanded_count, 3)


class EffectiveDateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_countries()
        cls.user = make_user()

    def setUp(self):
        self.vendor = make_vendor()
        load_rates(self.vendor, {"44": "0.0040", "447": "0.0100", "49": "0.0050"}, self.user, date(2026, 1, 1))

    def rate(self, prefix, day):
        r = VendorRate.objects.filter(vendor=self.vendor, prefix=prefix).active_on(day).first()
        return r.rate if r else None

    def test_partial_update_closes_old_period_and_keeps_history(self):
        deck = load_rates(self.vendor, {"447": "0.0120"}, self.user, date(2026, 3, 1), deck_type="partial")
        self.assertEqual(self.rate("447", date(2026, 2, 28)), Decimal("0.0100"))
        self.assertEqual(self.rate("447", date(2026, 3, 1)), Decimal("0.0120"))
        self.assertEqual(self.rate("44", date(2026, 3, 1)), Decimal("0.0040"))   # untouched
        self.assertEqual(deck.increase_count, 1)
        self.assertEqual(VendorRate.objects.filter(vendor=self.vendor, prefix="447").count(), 2)

    def test_full_deck_removes_missing_prefixes(self):
        deck = load_rates(self.vendor, {"44": "0.0039", "447": "0.0100"}, self.user, date(2026, 4, 1))
        self.assertEqual(deck.removed_count, 1)
        self.assertEqual(self.rate("49", date(2026, 3, 31)), Decimal("0.0050"))
        self.assertIsNone(self.rate("49", date(2026, 4, 1)))
        self.assertEqual(deck.decrease_count, 1)
        self.assertEqual(deck.unchanged_count, 1)

    def test_future_rate_is_scheduled_then_older_deck_fills_the_gap(self):
        load_rates(self.vendor, {"447": "0.0150"}, self.user, date(2026, 6, 1), deck_type="partial")
        load_rates(self.vendor, {"447": "0.0110"}, self.user, date(2026, 5, 1), deck_type="partial")
        self.assertEqual(self.rate("447", date(2026, 4, 30)), Decimal("0.0100"))
        self.assertEqual(self.rate("447", date(2026, 5, 15)), Decimal("0.0110"))
        self.assertEqual(self.rate("447", date(2026, 6, 1)), Decimal("0.0150"))

    def test_same_date_correction_supersedes(self):
        load_rates(self.vendor, {"447": "0.0150"}, self.user, date(2026, 6, 1), deck_type="partial")
        load_rates(self.vendor, {"447": "0.0140"}, self.user, date(2026, 6, 1), deck_type="partial")
        self.assertEqual(self.rate("447", date(2026, 6, 1)), Decimal("0.0140"))
        superseded = [r for r in VendorRate.objects.filter(prefix="447") if r.is_superseded]
        self.assertEqual(len(superseded), 1)

    def test_cannot_activate_twice_or_discard_active(self):
        deck = RateDeck.objects.filter(status="active").first()
        with self.assertRaises(ActivationError):
            activate_deck(deck, self.user)
        with self.assertRaises(ActivationError):
            discard_deck(deck, self.user)

    def test_short_notice_increase_warning(self):
        from django.utils import timezone
        today = timezone.localdate()
        deck = process(csv_deck(self.vendor, [("UK", "447", "0.0200", today.isoformat())], self.user,
                                deck_type="partial", effective=today))
        self.assertEqual(deck.lines.get().change, ChangeType.INCREASE)
        self.assertTrue(deck.issues.filter(level=DeckIssue.Level.WARNING, message__contains="notice").exists())
