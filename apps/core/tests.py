"""End-to-end workflow and role-based access tests using Django's test client."""
import io
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.testing import PASSWORD, load_countries, make_user, make_vendor
from apps.ratedecks.models import ColumnMapping, RateDeck, VendorRate
from apps.routing.models import Customer, LcrRun, MarginRule, RateSheet

SAMPLES = Path(settings.BASE_DIR) / "sample_data"


class RoleAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_countries()
        for role in ("admin", "analyst", "viewer"):
            make_user(role, role)
        cls.vendor = make_vendor()

    def client_for(self, username):
        self.client.login(username=username, password=PASSWORD)
        return self.client

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/")

    def test_viewer_is_read_only(self):
        c = self.client_for("viewer")
        for name in ("core:dashboard", "core:reports", "routing:compare", "routing:lcr_list", "ratedecks:history"):
            self.assertEqual(c.get(reverse(name)).status_code, 200, name)
        for name in ("ratedecks:upload", "vendors:create", "routing:ratesheet_create", "accounts:user_list"):
            self.assertEqual(c.get(reverse(name)).status_code, 403, name)
        self.assertEqual(c.post(reverse("routing:lcr_list"), {"as_of_date": "2026-01-01"}).status_code, 403)
        self.assertFalse(LcrRun.objects.exists())

    def test_analyst_cannot_manage_users_or_delete_vendors(self):
        c = self.client_for("analyst")
        self.assertEqual(c.get(reverse("ratedecks:upload")).status_code, 200)
        self.assertEqual(c.get(reverse("accounts:user_list")).status_code, 403)
        self.assertEqual(c.post(reverse("vendors:delete", args=[self.vendor.pk])).status_code, 403)

    def test_admin_can_manage_users(self):
        c = self.client_for("admin")
        response = c.post(reverse("accounts:user_create"), {
            "username": "newbie", "first_name": "New", "last_name": "User", "email": "n@example.com",
            "role": "viewer", "is_active": "on", "password": "Strong@Pass99"})
        self.assertRedirects(response, reverse("accounts:user_list"))


class EndToEndTests(TestCase):
    """Upload -> map -> process -> activate -> LCR -> rate sheet -> Excel export, through the web UI."""

    @classmethod
    def setUpTestData(cls):
        load_countries()
        cls.user = make_user("analyst", "analyst")
        cls.kst = make_vendor("KST", priority=1)
        cls.orc = make_vendor("ORC", priority=2)
        cls.customer = Customer.objects.create(name="Harbor", code="HRB")
        MarginRule.objects.create(name="Default", kind="percent", value=Decimal("12"))

    def upload_and_activate(self, vendor, filename, effective):
        with open(SAMPLES / "rate_decks" / filename, "rb") as fh:
            response = self.client.post(reverse("ratedecks:upload"), {
                "vendor": vendor.pk, "file": fh, "deck_type": "full",
                "default_effective_date": effective, "duplicate_policy": "lowest"})
        deck = RateDeck.objects.latest("id")
        self.assertRedirects(response, reverse("ratedecks:map", args=[deck.pk]))

        page = self.client.get(reverse("ratedecks:map", args=[deck.pk]))
        self.assertEqual(page.status_code, 200)
        form = page.context["form"]
        data = {name: form[name].value() or "" for name in form.fields}
        data.update(process="1", save_mapping="on")
        self.client.post(reverse("ratedecks:map", args=[deck.pk]), data)
        deck.refresh_from_db()
        self.assertEqual(deck.status, RateDeck.Status.VALIDATED, list(deck.logs.values_list("message", flat=True)))

        self.client.post(reverse("ratedecks:activate", args=[deck.pk]))
        deck.refresh_from_db()
        self.assertEqual(deck.status, RateDeck.Status.ACTIVE)
        return deck

    def test_full_workflow(self):
        self.client.login(username="analyst", password=PASSWORD)
        kst = self.upload_and_activate(self.kst, "01_kestrel_voice_full_az.csv", "2026-08-01")
        orc = self.upload_and_activate(self.orc, "02_orchid_telecom_rates.xlsx", "2026-08-15")
        self.assertGreater(orc.expanded_count, 0)          # grouped "Dial Codes" cells were split
        self.assertTrue(ColumnMapping.objects.filter(vendor=self.orc).exists())   # mapping remembered

        response = self.client.post(reverse("routing:lcr_list"), {"as_of_date": "2026-09-01"})
        run = LcrRun.objects.get()
        self.assertRedirects(response, reverse("routing:lcr_detail", args=[run.pk]))
        self.assertEqual(run.vendor_count, 2)
        self.assertGreater(run.routed_count, 50)

        self.client.post(reverse("routing:ratesheet_create"), {
            "customer": self.customer.pk, "lcr_run": run.pk, "effective_date": "2026-09-02"})
        sheet = RateSheet.objects.get()
        self.assertEqual(sheet.line_count, run.routed_count + run.single_route_count)
        line = sheet.lines.first()
        self.assertGreater(line.rate, line.cost)

        export = self.client.get(reverse("routing:ratesheet_export", args=[sheet.pk]), {"fmt": "xlsx"})
        self.assertEqual(export.status_code, 200)
        wb = load_workbook(io.BytesIO(export.content))
        values = [c.value for row in wb.active.iter_rows(max_row=8) for c in row]
        self.assertIn("Rate (USD/min)", values)
        self.assertNotIn("Cost", values)                    # customer file never shows our cost

        internal = self.client.get(reverse("routing:ratesheet_export", args=[sheet.pk]), {"fmt": "csv", "view": "internal"})
        self.assertIn("Margin %", internal.content.decode("utf-8-sig").splitlines()[0])
        self.assertEqual(VendorRate.objects.filter(deck=kst).count(), kst.prefix_count)

    def test_upload_rejects_wrong_file_type(self):
        self.client.login(username="analyst", password=PASSWORD)
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(reverse("ratedecks:upload"), {
            "vendor": self.kst.pk, "file": SimpleUploadedFile("rates.pdf", b"%PDF"), "deck_type": "full",
            "default_effective_date": "2026-01-01", "duplicate_policy": "lowest"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(RateDeck.objects.exists())
