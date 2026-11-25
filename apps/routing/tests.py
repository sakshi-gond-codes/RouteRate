from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.models import Country
from apps.core.testing import load_countries, load_rates, make_user, make_vendor

from .models import BlockedDestination, Customer, LcrEntry, MarginRule
from .services.lcr import build_matrix, run_lcr
from .services.pricing import MarginResolver
from .services.ratesheet import generate_rate_sheet

DAY = date(2026, 2, 1)


class LcrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_countries()
        cls.user = make_user()
        cls.a = make_vendor("AAA", priority=1)
        cls.b = make_vendor("BBB", priority=2)
        cls.c = make_vendor("CCC", priority=3)
        load_rates(cls.a, {"44": "0.0040", "447": "0.0100", "1": "0.0040"}, cls.user)
        load_rates(cls.b, {"44": "0.0035", "447": "0.0110", "4475": "0.0090", "1876": "0.1300"}, cls.user)
        load_rates(cls.c, {"447": "0.0100", "1876": "0.1400"}, cls.user)

    def row(self, prefix):
        _, rows = build_matrix(DAY, prefix_search=prefix)
        return next(r for r in rows if r.prefix == prefix)

    def test_cheapest_vendor_is_primary(self):
        self.assertEqual([q.vendor.code for q in self.row("44").ranked], ["BBB", "AAA"])

    def test_tie_is_broken_by_vendor_priority(self):
        self.assertEqual([q.vendor.code for q in self.row("447").ranked], ["AAA", "CCC", "BBB"])

    def test_longest_prefix_fallback(self):
        row = self.row("4475")
        self.assertEqual(row.ranked[0].vendor.code, "BBB")
        a_quote = row.quotes[self.a.id]
        self.assertFalse(a_quote.exact)
        self.assertEqual(a_quote.via, "447")

    def test_no_fallback_across_country_codes(self):
        """Vendor AAA only has '1' (USA & Canada); that is not a price for Jamaica (1876)."""
        row = self.row("1876")
        self.assertNotIn(self.a.id, row.quotes)
        self.assertEqual(row.ranked[0].vendor.code, "BBB")

    def test_blocks(self):
        BlockedDestination.objects.create(prefix="447", vendor=self.a, reason="Quality")
        self.assertEqual([q.vendor.code for q in self.row("447").ranked], ["CCC", "BBB"])
        BlockedDestination.objects.create(prefix="44", reason="Not sold")
        self.assertTrue(self.row("4475").blocked_reason)

    def test_saved_run_statuses(self):
        run = run_lcr(DAY, self.user)
        self.assertEqual(run.prefix_count, 5)  # 1, 44, 447, 4475, 1876
        self.assertEqual(run.entries.get(prefix="1").status, LcrEntry.Status.SINGLE)
        self.assertEqual(run.entries.get(prefix="447").backup_vendor, self.c)


class PricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_countries()
        cls.cust = Customer.objects.create(name="Cust", code="CST", rate_decimals=4)
        cls.other = Customer.objects.create(name="Other", code="OTH")
        uk = Country.objects.get(dial_code="44")
        MarginRule.objects.create(name="global", kind="percent", value=Decimal("10"))
        MarginRule.objects.create(name="uk", country=uk, kind="percent", value=Decimal("20"))
        MarginRule.objects.create(name="uk mobile", prefix="447", kind="fixed", value=Decimal("0.0020"))
        MarginRule.objects.create(name="cust default", customer=cls.cust, kind="percent", value=Decimal("5"),
                                  min_margin=Decimal("0.0010"))
        cls.uk = uk

    def test_most_specific_rule_wins(self):
        r = MarginResolver(self.other)
        self.assertEqual(r.rule_for("4475", self.uk.id).name, "uk mobile")
        self.assertEqual(r.rule_for("44", self.uk.id).name, "uk")
        self.assertEqual(r.rule_for("49", None).name, "global")
        self.assertEqual(MarginResolver(self.cust).rule_for("4475", self.uk.id).name, "cust default")

    def test_markup_min_margin_and_round_up(self):
        r = MarginResolver(self.other)
        self.assertEqual(r.sell_rate(Decimal("0.0100"), r.rule_for("44", self.uk.id)), Decimal("0.0120"))
        self.assertEqual(r.sell_rate(Decimal("0.01001"), r.rule_for("49", None)), Decimal("0.0111"))  # ceiling
        rc = MarginResolver(self.cust)
        # 5% of 0.0100 is 0.0005, below the 0.0010 minimum margin
        self.assertEqual(rc.sell_rate(Decimal("0.0100"), rc.rule_for("49", None)), Decimal("0.0110"))


class RateSheetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_countries()
        cls.user = make_user()
        cls.vendor = make_vendor("AAA")
        cls.cust = Customer.objects.create(name="Cust", code="CST", notice_days=7)
        MarginRule.objects.create(name="global", kind="percent", value=Decimal("10"))

    def test_versions_changes_and_notice_period(self):
        load_rates(self.vendor, {"44": "0.0040", "447": "0.0100", "49": "0.0050"}, self.user, DAY)
        sheet1 = generate_rate_sheet(self.cust, run_lcr(DAY, self.user), DAY, self.user, issue_date=DAY)
        self.assertEqual((sheet1.version, sheet1.new_count), (1, 3))

        later = DAY + timedelta(days=30)
        load_rates(self.vendor, {"44": "0.0040", "447": "0.0120", "33": "0.0060"}, self.user, later)
        sheet2 = generate_rate_sheet(self.cust, run_lcr(later, self.user), later, self.user, issue_date=later)
        self.assertEqual(sheet2.version, 2)
        self.assertEqual(sheet2.reference, f"CST-{later:%Y%m%d}-v2")
        self.assertEqual((sheet2.new_count, sheet2.increase_count, sheet2.unchanged_count, sheet2.removed_count),
                         (1, 1, 1, 1))
        increase = sheet2.lines.get(prefix="447")
        self.assertTrue(increase.notice_applied)
        self.assertEqual(increase.effective_date, later + timedelta(days=7))
        self.assertEqual(increase.rate, Decimal("0.0132"))
