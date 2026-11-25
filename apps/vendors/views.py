from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.permissions import admin_required, rate_manager_required
from apps.core.models import ActivityLog
from apps.ratedecks.models import VendorRate
from apps.routing.models import LcrEntry, LcrRun

from .forms import VendorForm
from .models import Vendor


@login_required
def vendor_list(request):
    today = timezone.localdate()
    live = dict(
        VendorRate.objects.active_on(today).values("vendor_id").annotate(n=Count("id")).values_list("vendor_id", "n")
    )
    latest_run = LcrRun.objects.first()
    wins = {}
    if latest_run:
        wins = dict(latest_run.entries.values("primary_vendor_id").annotate(n=Count("id"))
                    .values_list("primary_vendor_id", "n"))
    vendors = Vendor.objects.annotate(
        deck_count=Count("decks", distinct=True),
        pending=Count("decks", filter=Q(decks__status="validated"), distinct=True),
    )
    rows = [{"vendor": v, "live": live.get(v.id, 0), "wins": wins.get(v.id, 0)} for v in vendors]
    return render(request, "vendors/list.html", {"rows": rows, "latest_run": latest_run})


@login_required
def vendor_detail(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    today = timezone.localdate()
    rates = vendor.rates.active_on(today).select_related("country").order_by("prefix")
    q = request.GET.get("q", "").strip()
    if q:
        rates = rates.filter(Q(prefix__startswith=q) | Q(destination__icontains=q))
    scheduled = vendor.rates.scheduled_after(today).order_by("effective_from", "prefix")
    latest_run = LcrRun.objects.first()
    lcr_stats = None
    if latest_run:
        entries = latest_run.entries
        lcr_stats = {
            "primary": entries.filter(primary_vendor=vendor).count(),
            "backup": entries.filter(backup_vendor=vendor).count(),
            "run": latest_run,
        }
    return render(request, "vendors/detail.html", {
        "vendor": vendor,
        "page": Paginator(rates, 50).get_page(request.GET.get("page")),
        "live_count": vendor.rates.active_on(today).count(),
        "scheduled": scheduled[:50],
        "scheduled_count": scheduled.count(),
        "decks": vendor.decks.select_related("uploaded_by")[:10],
        "mapping": getattr(vendor, "column_mapping", None),
        "lcr_stats": lcr_stats,
        "today": today,
    })


@rate_manager_required
def vendor_create(request):
    form = VendorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vendor = form.save()
        ActivityLog.record(request.user, "vendor", f"Added vendor {vendor.name}")
        messages.success(request, f"Vendor {vendor.name} added. Upload its first rate deck next.")
        return redirect("vendors:detail", pk=vendor.pk)
    return render(request, "core/form_page.html", {
        "form": form, "title": "Add vendor", "submit_label": "Create vendor", "cancel_url": "vendors:list",
        "intro": "A vendor is a carrier you buy termination from. Their rate decks feed the LCR.",
    })


@rate_manager_required
def vendor_edit(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    form = VendorForm(request.POST or None, instance=vendor)
    if request.method == "POST" and form.is_valid():
        form.save()
        ActivityLog.record(request.user, "vendor", f"Updated vendor {vendor.name}")
        messages.success(request, "Vendor updated.")
        return redirect("vendors:detail", pk=vendor.pk)
    return render(request, "core/form_page.html", {
        "form": form, "title": f"Edit vendor: {vendor.name}", "submit_label": "Save changes",
        "cancel_url": "vendors:list",
    })


@admin_required
def vendor_delete(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method == "POST":
        name = vendor.name
        vendor.delete()
        ActivityLog.record(request.user, "vendor", f"Deleted vendor {name} and its rates")
        messages.success(request, f"Vendor {name} deleted.")
        return redirect("vendors:list")
    return render(request, "core/confirm_delete.html", {
        "object_name": vendor.name, "cancel_url": "vendors:list",
        "warning": (f"This permanently deletes {vendor.decks.count()} rate decks and "
                    f"{vendor.rates.count():,} rate records. To stop using the vendor, mark it inactive instead."),
    })
