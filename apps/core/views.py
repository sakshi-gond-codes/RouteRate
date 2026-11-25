from datetime import timedelta

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.ratedecks.models import RateDeck, VendorRate
from apps.routing.models import Customer, LcrEntry, LcrRun, RateSheet
from apps.routing.services.lcr import build_matrix
from apps.vendors.models import Vendor

from .exports import export_response
from .models import ActivityLog

# Categorical palette (validated for colour-blind separation, fixed order, follows the vendor not its rank)
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
STATUS_COLORS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}


def vendor_colors():
    """Each vendor keeps the same colour on every chart (assigned by id order, never by rank)."""
    return {v_id: SERIES_COLORS[i % len(SERIES_COLORS)]
            for i, v_id in enumerate(Vendor.objects.order_by("id").values_list("id", flat=True))}


# ---------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    today = timezone.localdate()
    since = timezone.now() - timedelta(days=30)
    active_vendors = Vendor.objects.filter(is_active=True)
    live = VendorRate.objects.active_on(today).filter(vendor__in=active_vendors)
    latest_run = LcrRun.objects.select_related("created_by").first()

    kpis = {
        "vendors": active_vendors.count(),
        "prefixes": live.values("prefix").distinct().count(),
        "countries": live.values("country_id").distinct().count(),
        "decks_30d": RateDeck.objects.filter(uploaded_at__gte=since).count(),
        "pending": RateDeck.objects.filter(status=RateDeck.Status.VALIDATED).count(),
        "sheets_30d": RateSheet.objects.filter(created_at__gte=since).count(),
        "customers": Customer.objects.filter(is_active=True).count(),
        "scheduled": VendorRate.objects.scheduled_after(today).count(),
    }

    colors = vendor_colors()
    vendor_chart = None
    no_backup = []
    if latest_run:
        quoted = dict(live.values("vendor_id").annotate(n=Count("prefix", distinct=True)).values_list("vendor_id", "n"))
        wins = dict(latest_run.entries.exclude(primary_vendor=None).values("primary_vendor_id")
                    .annotate(n=Count("id")).values_list("primary_vendor_id", "n"))
        vendors = list(active_vendors.order_by("name"))
        vendor_chart = {
            "labels": [v.name for v in vendors],
            "quoted": [quoted.get(v.id, 0) for v in vendors],
            "wins": [wins.get(v.id, 0) for v in vendors],
        }
        no_backup = (latest_run.entries.filter(status__in=[LcrEntry.Status.SINGLE, LcrEntry.Status.NO_ROUTE])
                     .select_related("primary_vendor")[:6])

    recent_decks = list(RateDeck.objects.exclude(status=RateDeck.Status.UPLOADED)
                        .select_related("vendor").order_by("-uploaded_at")[:8])[::-1]
    deck_chart = {
        "labels": [f"{d.vendor.code} #{d.pk}" for d in recent_decks],
        "accepted": [d.valid_rows for d in recent_decks],
        "duplicates": [d.duplicate_count for d in recent_decks],
        "rejected": [d.error_rows for d in recent_decks],
    }

    return render(request, "core/dashboard.html", {
        "kpis": kpis, "latest_run": latest_run, "vendor_chart": vendor_chart, "deck_chart": deck_chart,
        "status_colors": STATUS_COLORS, "series_colors": SERIES_COLORS[:2],
        "pending_decks": RateDeck.objects.filter(status=RateDeck.Status.VALIDATED).select_related("vendor")[:5],
        "no_backup": no_backup,
        "upcoming": VendorRate.objects.scheduled_after(today).select_related("vendor").order_by("effective_from")[:6],
        "recent_sheets": RateSheet.objects.select_related("customer")[:5],
        "activity": ActivityLog.objects.select_related("user")[:8],
        "today": today,
        "colors": colors,
    })


# ---------------------------------------------------------------- reports
def vendor_competitiveness(today, run):
    """Per vendor: coverage, LCR wins and how far above the cheapest price it usually is (Pandas)."""
    vendors, rows = build_matrix(today)
    records = []
    for row in rows:
        if not row.ranked:
            continue
        best = row.ranked[0].rate
        for rank, q in enumerate(row.ranked, start=1):
            records.append({"vendor": q.vendor.name, "vendor_id": q.vendor.id, "rank": rank,
                            "above_pct": float((q.rate - best) / best * 100) if best else 0.0})
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    summary = df.groupby(["vendor_id", "vendor"]).agg(
        prefixes=("rank", "size"),
        primary=("rank", lambda r: int((r == 1).sum())),
        backup=("rank", lambda r: int((r == 2).sum())),
        avg_above=("above_pct", "mean"),
    ).reset_index()
    summary["win_rate"] = (summary["primary"] / summary["prefixes"] * 100).round(1)
    summary["avg_above"] = summary["avg_above"].round(1)
    return summary.sort_values("primary", ascending=False)


def country_costs(run):
    entries = run.entries.exclude(primary_rate=None).values(
        "country__name", "country__region", "prefix", "primary_rate", "primary_vendor__name", "status")
    df = pd.DataFrame(list(entries))
    if df.empty:
        return df, df
    df["primary_rate"] = df["primary_rate"].astype(float)
    by_country = df.groupby(["country__name", "country__region"]).agg(
        prefixes=("prefix", "size"),
        min_cost=("primary_rate", "min"),
        avg_cost=("primary_rate", "mean"),
        max_cost=("primary_rate", "max"),
        top_vendor=("primary_vendor__name", lambda s: s.value_counts().index[0]),
        no_backup=("status", lambda s: int((s == "single").sum())),
    ).reset_index().rename(columns={"country__name": "country", "country__region": "region"})
    by_region = (df[df["primary_rate"] < 1]  # exclude satellite outliers from the regional average
                 .groupby("country__region")["primary_rate"].mean().sort_values().reset_index()
                 .rename(columns={"country__region": "region", "primary_rate": "avg_cost"}))
    return by_country.sort_values("country"), by_region


def margin_summary():
    rows = []
    for c in Customer.objects.order_by("name"):
        s = c.rate_sheets.order_by("-version").first()
        if s:
            rows.append({"customer": c.name, "reference": s.reference, "sheet_id": s.pk, "lines": s.line_count,
                         "avg_cost": float(s.avg_cost or 0), "avg_sell": float(s.avg_sell or 0),
                         "margin_pct": float(s.avg_margin_pct or 0), "increases": s.increase_count,
                         "decreases": s.decrease_count, "issued": s.created_at})
    return pd.DataFrame(rows)


def change_activity(days=90):
    since = timezone.now() - timedelta(days=days)
    qs = (RateDeck.objects.filter(status=RateDeck.Status.ACTIVE, activated_at__gte=since)
          .values("vendor__name").annotate(new=Sum("new_count"), increases=Sum("increase_count"),
                                            decreases=Sum("decrease_count"), removed=Sum("removed_count"),
                                            decks=Count("id")).order_by("vendor__name"))
    return pd.DataFrame(list(qs)).rename(columns={"vendor__name": "vendor"})


@login_required
def reports(request):
    today = timezone.localdate()
    run = LcrRun.objects.first()
    competitiveness = vendor_competitiveness(today, run)
    by_country, by_region = country_costs(run) if run else (pd.DataFrame(), pd.DataFrame())
    margins = margin_summary()
    changes = change_activity()

    export = request.GET.get("export")
    fmt = request.GET.get("fmt", "xlsx")
    if export == "vendors" and not competitiveness.empty:
        df = competitiveness.drop(columns=["vendor_id"]).rename(columns={
            "vendor": "Vendor", "prefixes": "Prefixes priced", "primary": "Primary routes", "backup": "Backup routes",
            "win_rate": "Win rate %", "avg_above": "Avg above cheapest %"})
        return export_response(df, fmt, "vendor_competitiveness", sheet_title="Vendors",
                               title=f"Vendor competitiveness - rates as of {today}")
    if export == "countries" and not by_country.empty:
        df = by_country.rename(columns={"country": "Country", "region": "Region", "prefixes": "Prefixes",
                                        "min_cost": "Min cost", "avg_cost": "Avg cost", "max_cost": "Max cost",
                                        "top_vendor": "Most used primary vendor", "no_backup": "Without backup"})
        return export_response(df, fmt, "country_costs", sheet_title="Countries",
                               title=f"LCR cost by country - run #{run.pk} ({run.as_of_date})")
    if export == "margins" and not margins.empty:
        df = margins.drop(columns=["sheet_id"]).rename(columns={
            "customer": "Customer", "reference": "Latest sheet", "lines": "Lines", "avg_cost": "Avg cost",
            "avg_sell": "Avg sell rate", "margin_pct": "Margin %", "increases": "Increases",
            "decreases": "Decreases", "issued": "Issued"})
        df["Issued"] = df["Issued"].dt.tz_localize(None)
        return export_response(df, fmt, "customer_margins", sheet_title="Margins", title="Customer margin summary")

    ctx = {
        "run": run, "today": today,
        "competitiveness": competitiveness.to_dict("records") if not competitiveness.empty else [],
        "by_country": by_country.to_dict("records") if not by_country.empty else [],
        "by_region": by_region.to_dict("records") if not by_region.empty else [],
        "margins": margins.to_dict("records") if not margins.empty else [],
        "changes": changes.to_dict("records") if not changes.empty else [],
        "colors": vendor_colors(),
    }
    ctx["chart_data"] = {
        "vendors": {
            "labels": [r["vendor"] for r in ctx["competitiveness"]],
            "above": [r["avg_above"] for r in ctx["competitiveness"]],
            "colors": [ctx["colors"].get(r["vendor_id"], SERIES_COLORS[0]) for r in ctx["competitiveness"]],
        },
        "regions": {"labels": [r["region"] for r in ctx["by_region"]],
                    "values": [round(r["avg_cost"], 4) for r in ctx["by_region"]]},
        "margins": {"labels": [r["customer"] for r in ctx["margins"]],
                    "values": [r["margin_pct"] for r in ctx["margins"]]},
        "changes": {"labels": [r["vendor"] for r in ctx["changes"]],
                    "increases": [int(r["increases"] or 0) for r in ctx["changes"]],
                    "decreases": [int(r["decreases"] or 0) for r in ctx["changes"]],
                    "new": [int(r["new"] or 0) for r in ctx["changes"]]},
    }
    return render(request, "core/reports.html", ctx)


# ---------------------------------------------------------------- activity history
@login_required
def activity(request):
    logs = ActivityLog.objects.select_related("user")
    action = request.GET.get("action")
    user = request.GET.get("user")
    if action:
        logs = logs.filter(action=action)
    if user:
        logs = logs.filter(user_id=user)
    actions = ActivityLog.objects.order_by("action").values_list("action", flat=True).distinct()
    return render(request, "core/activity.html", {
        "page": Paginator(logs, 40).get_page(request.GET.get("page")),
        "actions": actions, "users": User.objects.order_by("first_name"),
    })


# ---------------------------------------------------------------- error pages
def permission_denied(request, exception=None):
    return render(request, "403.html", {"message": str(exception or "")}, status=403)


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)
