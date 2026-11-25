from datetime import date

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import admin_required, rate_manager_required
from apps.core.exports import export_response
from apps.core.models import ActivityLog, Country
from apps.ratedecks.models import ChangeType

from .forms import BlockedDestinationForm, CustomerForm, LcrRunForm, MarginRuleForm, RateSheetForm
from .models import BlockedDestination, Customer, LcrEntry, LcrRun, MarginRule, RateSheet
from .services.lcr import build_matrix, run_lcr
from .services.ratesheet import RateSheetError, generate_rate_sheet


def parse_day(value, default):
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        return default


# ---------------------------------------------------------------- vendor comparison
@login_required
def compare(request):
    today = timezone.localdate()
    as_of = parse_day(request.GET.get("as_of"), today)
    country = request.GET.get("country") or ""
    q = "".join(ch for ch in request.GET.get("q", "") if ch.isdigit())
    only = request.GET.get("only", "")

    vendors, rows = build_matrix(as_of, country_id=country or None, prefix_search=q)
    if only == "single":
        rows = [r for r in rows if r.status in (LcrEntry.Status.SINGLE, LcrEntry.Status.NO_ROUTE)]
    elif only == "fallback":
        rows = [r for r in rows if any(not qt.exact for qt in r.quotes.values())]
    elif only == "blocked":
        rows = [r for r in rows if r.blocked_reason or any(qt.blocked_reason for qt in r.quotes.values())]

    if request.GET.get("fmt") in ("csv", "xlsx"):
        records = []
        for r in rows:
            rec = {"Prefix": r.prefix, "Country": r.country.name if r.country else "", "Destination": r.destination}
            for v in vendors:
                qt = r.quotes.get(v.id)
                rec[f"{v.code} rate"] = float(qt.rate) if qt else None
            rec["Primary"] = r.ranked[0].vendor.code if r.ranked else ""
            rec["Primary rate"] = float(r.ranked[0].rate) if r.ranked else None
            rec["Backup"] = r.ranked[1].vendor.code if len(r.ranked) > 1 else ""
            rec["Spread %"] = round(r.spread_pct, 1) if r.spread_pct is not None else None
            rec["Status"] = LcrEntry.Status(r.status).label
            records.append(rec)
        return export_response(pd.DataFrame(records), request.GET["fmt"], f"vendor_comparison_{as_of}",
                               sheet_title="Comparison", title=f"Vendor comparison - rates as of {as_of}")

    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    for row in page.object_list:
        row.cells = []
        for v in vendors:
            qt = row.quotes.get(v.id)
            row.cells.append({"quote": qt, "rank": row.rank_of(v.id) if qt else None})
    return render(request, "routing/compare.html", {
        "vendors": vendors, "page": page, "total": len(rows), "as_of": as_of, "today": today,
        "countries": Country.objects.order_by("name"), "country": country, "q": q, "only": only,
    })


# ---------------------------------------------------------------- LCR
@login_required
def lcr_list(request):
    form = LcrRunForm(request.POST or None)
    if request.method == "POST":
        if not request.user.can_manage_rates:
            raise PermissionDenied("Only Admins and Rate Analysts can run LCR.")
        if form.is_valid():
            run = run_lcr(form.cleaned_data["as_of_date"], request.user, form.cleaned_data["notes"])
            messages.success(request, f"LCR calculated for {run.prefix_count:,} prefixes in {run.duration_ms} ms.")
            return redirect("routing:lcr_detail", pk=run.pk)
    runs = LcrRun.objects.select_related("created_by")
    return render(request, "routing/lcr_list.html", {"form": form, "page": Paginator(runs, 20).get_page(request.GET.get("page"))})


@login_required
def lcr_detail(request, pk):
    run = get_object_or_404(LcrRun.objects.select_related("created_by"), pk=pk)
    entries = run.entries.select_related("country", "primary_vendor", "backup_vendor", "third_vendor")
    status = request.GET.get("status")
    vendor = request.GET.get("vendor")
    country = request.GET.get("country")
    q = request.GET.get("q", "").strip()
    if status in LcrEntry.Status.values:
        entries = entries.filter(status=status)
    if vendor:
        entries = entries.filter(primary_vendor_id=vendor)
    if country:
        entries = entries.filter(country_id=country)
    if q:
        entries = entries.filter(Q(prefix__startswith=q) | Q(destination__icontains=q))

    if request.GET.get("fmt") in ("csv", "xlsx"):
        df = pd.DataFrame([{
            "Prefix": e.prefix, "Country": e.country.name if e.country else "", "Destination": e.destination,
            "Status": e.get_status_display(),
            "Primary vendor": e.primary_vendor.name if e.primary_vendor else "", "Primary rate": e.primary_rate,
            "Primary via": e.primary_via,
            "Backup vendor": e.backup_vendor.name if e.backup_vendor else "", "Backup rate": e.backup_rate,
            "Backup via": e.backup_via,
            "3rd vendor": e.third_vendor.name if e.third_vendor else "", "3rd rate": e.third_rate,
            "Vendors": e.vendor_count, "Note": e.note,
        } for e in entries])
        return export_response(df, request.GET["fmt"], f"lcr_run{run.pk}_{run.as_of_date}", sheet_title="LCR",
                               title=f"Least Cost Routing - run #{run.pk}",
                               subtitle_lines=[f"Rates in force on {run.as_of_date}",
                                               f"Generated {timezone.localtime(run.created_at):%Y-%m-%d %H:%M}"])

    wins = (run.entries.exclude(primary_vendor=None).values("primary_vendor__name")
            .annotate(n=Count("id")).order_by("-n"))
    vendors_in_run = (run.entries.exclude(primary_vendor=None)
                      .values_list("primary_vendor_id", "primary_vendor__name").distinct())
    return render(request, "routing/lcr_detail.html", {
        "run": run, "page": Paginator(entries, 50).get_page(request.GET.get("page")),
        "statuses": LcrEntry.Status.choices, "wins": list(wins),
        "vendors": sorted(set(vendors_in_run), key=lambda v: v[1]),
        "countries": Country.objects.filter(id__in=run.entries.values("country_id")).order_by("name"),
    })


@require_POST
@admin_required
def lcr_delete(request, pk):
    run = get_object_or_404(LcrRun, pk=pk)
    run.delete()
    messages.success(request, f"LCR run #{pk} deleted.")
    return redirect("routing:lcr_list")


# ---------------------------------------------------------------- generic CRUD helpers
def _crud_list(request, template, queryset, extra=None):
    return render(request, template, {"objects": queryset, **(extra or {})})


def _crud_form(request, form_class, instance, title, list_url, action, describe, initial=None, intro=""):
    form = form_class(request.POST or None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if hasattr(obj, "created_by_id") and not obj.created_by_id:
            obj.created_by = request.user
        obj.save()
        ActivityLog.record(request.user, action, f"{'Updated' if instance else 'Created'} {describe(obj)}")
        messages.success(request, f"{describe(obj)} saved.")
        return redirect(list_url)
    return render(request, "core/form_page.html", {
        "form": form, "title": title, "cancel_url": list_url, "intro": intro,
        "submit_label": "Save changes" if instance else "Create",
    })


def _crud_delete(request, obj, list_url, action, describe):
    if request.method == "POST":
        label = describe(obj)
        obj.delete()
        ActivityLog.record(request.user, action, f"Deleted {label}")
        messages.success(request, f"{label} deleted.")
        return redirect(list_url)
    return render(request, "core/confirm_delete.html", {"object_name": describe(obj), "cancel_url": list_url})


# ---------------------------------------------------------------- customers
@login_required
def customer_list(request):
    customers = Customer.objects.annotate(
        sheet_count=Count("rate_sheets", distinct=True), rule_count=Count("margin_rules", distinct=True))
    latest = {}
    for sheet in RateSheet.objects.order_by("customer_id", "-version"):
        latest.setdefault(sheet.customer_id, sheet)
    for c in customers:
        c.latest_sheet = latest.get(c.id)
    return _crud_list(request, "routing/customer_list.html", customers)


@rate_manager_required
def customer_form(request, pk=None):
    obj = get_object_or_404(Customer, pk=pk) if pk else None
    return _crud_form(request, CustomerForm, obj, f"Edit customer: {obj}" if obj else "Add customer",
                      "routing:customer_list", "customer", lambda o: f"Customer {o.name}",
                      intro="Customers receive rate sheets. Their margin rules decide the sell price.")


# ---------------------------------------------------------------- margin rules
@login_required
def margin_list(request):
    rules = MarginRule.objects.select_related("customer", "country")
    return _crud_list(request, "routing/margin_list.html", rules)


@rate_manager_required
def margin_form(request, pk=None):
    obj = get_object_or_404(MarginRule, pk=pk) if pk else None
    return _crud_form(request, MarginRuleForm, obj, "Edit margin rule" if obj else "Add margin rule",
                      "routing:margin_list", "margin", lambda o: f"Margin rule '{o.name}'",
                      intro="The most specific rule wins: customer before global, prefix before country, "
                            "country before default.")


@rate_manager_required
def margin_delete(request, pk):
    return _crud_delete(request, get_object_or_404(MarginRule, pk=pk), "routing:margin_list", "margin",
                        lambda o: f"Margin rule '{o.name}'")


# ---------------------------------------------------------------- blocked destinations
@login_required
def blocked_list(request):
    blocks = BlockedDestination.objects.select_related("vendor", "created_by")
    countries = Country.objects.all()
    from apps.core.countries import CountryIndex
    index = CountryIndex(countries)
    for b in blocks:
        b.country = index.resolve(b.prefix)
    return _crud_list(request, "routing/blocked_list.html", blocks)


@rate_manager_required
def blocked_form(request, pk=None):
    obj = get_object_or_404(BlockedDestination, pk=pk) if pk else None
    initial = {"prefix": request.GET.get("prefix", "")} if not obj else None
    return _crud_form(request, BlockedDestinationForm, obj, "Edit blocked destination" if obj else "Block a destination",
                      "routing:blocked_list", "block", lambda o: f"Block on {o}", initial=initial,
                      intro="Without a vendor the prefix is not routed or sold at all. With a vendor, only that "
                            "vendor is skipped (for example because of poor call quality).")


@rate_manager_required
def blocked_delete(request, pk):
    return _crud_delete(request, get_object_or_404(BlockedDestination, pk=pk), "routing:blocked_list", "block",
                        lambda o: f"Block on {o}")


# ---------------------------------------------------------------- rate sheets
@login_required
def ratesheet_list(request):
    sheets = RateSheet.objects.select_related("customer", "created_by", "lcr_run")
    customer = request.GET.get("customer")
    if customer:
        sheets = sheets.filter(customer_id=customer)
    return render(request, "routing/ratesheet_list.html", {
        "page": Paginator(sheets, 25).get_page(request.GET.get("page")),
        "customers": Customer.objects.order_by("name"),
    })


@rate_manager_required
def ratesheet_create(request):
    initial = {"customer": request.GET.get("customer")} if request.GET.get("customer") else None
    form = RateSheetForm(request.POST or None, initial=initial)
    if not LcrRun.objects.exists():
        messages.info(request, "Run LCR first. Rate sheets are priced from an LCR run.")
        return redirect("routing:lcr_list")
    if request.method == "POST" and form.is_valid():
        try:
            sheet = generate_rate_sheet(form.cleaned_data["customer"], form.cleaned_data["lcr_run"],
                                        form.cleaned_data["effective_date"], request.user, form.cleaned_data["notes"])
        except RateSheetError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Rate sheet {sheet.reference} generated with {sheet.line_count:,} lines.")
            return redirect("routing:ratesheet_detail", pk=sheet.pk)
    return render(request, "core/form_page.html", {
        "form": form, "title": "Generate customer rate sheet", "submit_label": "Generate rate sheet",
        "cancel_url": "routing:ratesheet_list",
        "intro": "Sell rate = primary LCR cost + the customer's margin rule, rounded up. Each line is compared "
                 "with the customer's previous sheet to show New, Increase, Decrease, Unchanged and Removed.",
    })


@login_required
def ratesheet_detail(request, pk):
    sheet = get_object_or_404(RateSheet.objects.select_related("customer", "lcr_run", "created_by"), pk=pk)
    lines = sheet.lines.select_related("country", "vendor", "margin_rule")
    change = request.GET.get("change")
    q = request.GET.get("q", "").strip()
    if change in ChangeType.values:
        lines = lines.filter(change=change)
    if q:
        lines = lines.filter(Q(prefix__startswith=q) | Q(destination__icontains=q))
    return render(request, "routing/ratesheet_detail.html", {
        "sheet": sheet, "page": Paginator(lines, 50).get_page(request.GET.get("page")),
        "change_filter": change, "changes": ChangeType.choices,
    })


@login_required
def ratesheet_export(request, pk):
    sheet = get_object_or_404(RateSheet.objects.select_related("customer"), pk=pk)
    fmt = request.GET.get("fmt", "xlsx")
    internal = request.GET.get("view") == "internal"
    lines = sheet.lines.select_related("country", "vendor", "backup_vendor", "margin_rule").order_by("prefix")
    records = []
    for l in lines:
        rec = {
            "Destination": l.destination, "Country": l.country.name if l.country else "", "Prefix": l.prefix,
            "Rate (USD/min)": float(l.rate), "Billing increment": l.increment,
            "Effective date": l.effective_date, "Change": l.get_change_display(),
            "Previous rate": float(l.previous_rate) if l.previous_rate is not None else None,
        }
        if internal:
            rec.update({
                "Cost": float(l.cost) if l.cost is not None else None,
                "Margin (USD)": float(l.margin) if l.margin is not None else None,
                "Margin %": round(l.margin_pct, 2) if l.margin_pct is not None else None,
                "Primary vendor": l.vendor.name if l.vendor else "",
                "Backup vendor": l.backup_vendor.name if l.backup_vendor else "",
                "Margin rule": l.margin_rule.name if l.margin_rule else "",
                "Notice applied": "Yes" if l.notice_applied else "",
            })
        records.append(rec)
    df = pd.DataFrame(records)
    c = sheet.customer
    subtitle = [
        f"Customer: {c.name}   |   Reference: {sheet.reference}",
        f"Issued: {timezone.localtime(sheet.created_at):%Y-%m-%d}   |   Effective: {sheet.effective_date}   |   "
        f"Currency: USD per minute   |   Billing: {c.billing_increment}",
        f"Changes: {sheet.new_count} new, {sheet.increase_count} increases, {sheet.decrease_count} decreases, "
        f"{sheet.removed_count} removed. Increases take effect after {c.notice_days} days notice.",
    ]
    if internal:
        subtitle.append("INTERNAL - contains cost and margin. Do not send to the customer.")
    name = f"{sheet.reference}{'_internal' if internal else ''}"
    ActivityLog.record(request.user, "ratesheet", f"Exported {sheet.reference} ({'internal' if internal else 'customer'} {fmt.upper()})")
    return export_response(df, fmt, name, sheet_title="Rate sheet",
                           title=f"Rate sheet - {c.name}" + (" (internal)" if internal else ""),
                           subtitle_lines=subtitle, change_column="Change")
