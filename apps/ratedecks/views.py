from datetime import date

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import rate_manager_required
from apps.core.exports import export_response
from apps.core.models import ActivityLog, Country
from apps.vendors.models import Vendor

from .forms import DeckUploadForm, MappingForm
from .models import ChangeType, ColumnMapping, DeckIssue, RateDeck, VendorRate
from .services import reader
from .services.activation import ActivationError, activate_deck, discard_deck
from .services.mapping import FIELDS, suggest_mapping
from .services.processor import process_deck

PAGE_SIZE = 50


def parse_day(value, default=None):
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        return default


# ---------------------------------------------------------------- upload
@rate_manager_required
def upload(request):
    initial = {}
    if request.GET.get("vendor"):
        initial["vendor"] = request.GET["vendor"]
    form = DeckUploadForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        deck = form.save(commit=False)
        deck.original_filename = request.FILES["file"].name[:255]
        deck.file_type = form.file_type
        deck.uploaded_by = request.user
        deck.save()
        ActivityLog.record(request.user, "upload",
                           f"Uploaded {deck.original_filename} for {deck.vendor.name} ({deck.get_deck_type_display()[:12]})")
        return redirect("ratedecks:map", pk=deck.pk)
    recent = RateDeck.objects.select_related("vendor")[:5]
    return render(request, "ratedecks/upload.html", {"form": form, "recent": recent})


# ---------------------------------------------------------------- column mapping
@rate_manager_required
def map_columns(request, pk):
    deck = get_object_or_404(RateDeck.objects.select_related("vendor"), pk=pk)
    if not deck.can_remap:
        messages.info(request, "This deck has already been activated or discarded.")
        return redirect("ratedecks:detail", pk=deck.pk)

    saved = getattr(deck.vendor, "column_mapping", None)
    previous = deck.mapping or {}
    source = request.POST if request.method == "POST" else request.GET
    sheet = source.get("sheet") or previous.get("sheet") or (saved.sheet_name if saved else "")

    try:
        raw, info = reader.read_raw(deck.file.path, deck.file_type, sheet or None)
    except reader.DeckReadError as exc:
        deck.status = RateDeck.Status.FAILED
        deck.save(update_fields=["status"])
        messages.error(request, f"Could not read the file: {exc}")
        return redirect("ratedecks:detail", pk=deck.pk)

    detected = reader.detect_header_row(raw)
    try:
        header_row = int(source.get("header_row") or previous.get("header_row") or detected)
    except ValueError:
        header_row = detected
    if header_row not in raw.index:
        header_row = detected
    columns = reader.column_labels(raw, header_row)
    body = reader.data_frame(raw, header_row)

    saved_columns = previous.get("columns") or (saved.columns if saved else {})
    suggestion = suggest_mapping(columns, saved_columns)
    initial = {f"map_{k}": v for k, v in suggestion.items()}
    initial.update(header_row=header_row, sheet=info["sheet"],
                   date_order=previous.get("date_order") or (saved.date_order if saved else "DMY"),
                   save_mapping=True)

    form = MappingForm(request.POST if request.method == "POST" and "process" in request.POST else None,
                       initial=initial, columns=columns, sheets=info["sheet_names"])

    if request.method == "POST" and "process" in request.POST and form.is_valid():
        options = {
            "columns": form.columns(),
            "header_row": form.cleaned_data["header_row"],
            "sheet": info["sheet"],
            "date_order": form.cleaned_data["date_order"],
        }
        if form.cleaned_data.get("save_mapping"):
            ColumnMapping.objects.update_or_create(
                vendor=deck.vendor,
                defaults={"columns": options["columns"], "header_row": options["header_row"],
                          "sheet_name": info["sheet"], "date_order": options["date_order"]},
            )
        try:
            process_deck(deck, options)
        except (reader.DeckReadError, ValueError) as exc:
            messages.error(request, f"Processing failed: {exc}")
            return redirect("ratedecks:detail", pk=deck.pk)
        deck.refresh_from_db()
        ActivityLog.record(request.user, "process",
                           f"Processed {deck.vendor.code} deck #{deck.pk}: {deck.prefix_count:,} prefixes, "
                           f"{deck.error_rows} rejected rows")
        if deck.status == RateDeck.Status.FAILED:
            messages.error(request, "No valid rates were found. Check the mapping and the error report.")
        elif deck.error_rows:
            messages.warning(request, f"Processed with {deck.error_rows} rejected rows. Review the error report "
                                      f"before activating.")
        else:
            messages.success(request, "Deck processed successfully. Review the changes and activate it.")
        return redirect("ratedecks:detail", pk=deck.pk)

    preview_rows = body.head(10)
    preview = {
        "columns": columns,
        "rows": [(idx, list(r)) for idx, r in preview_rows.iterrows()],
    }
    raw_top = [(idx, list(r)) for idx, r in raw.head(min(header_row + 2, 15)).iterrows()]
    return render(request, "ratedecks/map.html", {
        "deck": deck, "form": form, "preview": preview, "raw_top": raw_top, "info": info,
        "detected_header": detected, "header_row": header_row, "data_rows": len(body),
        "field_meta": FIELDS, "used_saved": bool(saved_columns),
    })


# ---------------------------------------------------------------- review / detail
@login_required
def deck_detail(request, pk):
    deck = get_object_or_404(RateDeck.objects.select_related("vendor", "uploaded_by", "activated_by"), pk=pk)
    tab = request.GET.get("tab", "lines")
    ctx = {"deck": deck, "tab": tab, "change_choices": [c for c in ChangeType.choices if c[0] != "removed"]}

    if tab == "lines":
        lines = deck.lines.select_related("country")
        change = request.GET.get("change")
        if change in ChangeType.values:
            lines = lines.filter(change=change)
        q = request.GET.get("q", "").strip()
        if q:
            lines = lines.filter(Q(prefix__startswith=q) | Q(destination__icontains=q))
        ctx["page"] = Paginator(lines, PAGE_SIZE).get_page(request.GET.get("page"))
        ctx["change_filter"] = change
    elif tab in ("errors", "warnings", "duplicates"):
        level = {"errors": "error", "warnings": "warning", "duplicates": "duplicate"}[tab]
        ctx["page"] = Paginator(deck.issues.filter(level=level), PAGE_SIZE).get_page(request.GET.get("page"))
    else:
        ctx["logs"] = deck.logs.all()

    ctx["issue_counts"] = {
        "errors": deck.issues.filter(level="error").count(),
        "warnings": deck.warning_count,
        "duplicates": deck.duplicate_count,
    }
    if deck.status == RateDeck.Status.VALIDATED:
        ctx["live_count"] = VendorRate.objects.filter(vendor=deck.vendor).active_on(timezone.localdate()).count()
    return render(request, "ratedecks/detail.html", ctx)


@require_POST
@rate_manager_required
def deck_activate(request, pk):
    deck = get_object_or_404(RateDeck, pk=pk)
    try:
        deck = activate_deck(deck, request.user)
    except ActivationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Deck activated. {deck.prefix_count:,} rates are now live in the routing table"
                                  + (f" and {deck.removed_count} prefixes were closed." if deck.removed_count else "."))
    return redirect("ratedecks:detail", pk=pk)


@require_POST
@rate_manager_required
def deck_discard(request, pk):
    deck = get_object_or_404(RateDeck, pk=pk)
    try:
        discard_deck(deck, request.user)
        messages.info(request, "Deck discarded. Nothing was changed in the routing table.")
    except ActivationError as exc:
        messages.error(request, str(exc))
    return redirect("ratedecks:detail", pk=pk)


@login_required
def deck_download(request, pk):
    deck = get_object_or_404(RateDeck, pk=pk)
    try:
        return FileResponse(deck.file.open("rb"), as_attachment=True, filename=deck.original_filename)
    except FileNotFoundError:
        raise Http404("The original file is no longer on the server.") from None


@login_required
def deck_export(request, pk, kind):
    deck = get_object_or_404(RateDeck.objects.select_related("vendor"), pk=pk)
    fmt = request.GET.get("fmt", "xlsx")
    if kind == "lines":
        df = pd.DataFrame(list(deck.lines.values_list(
            "prefix", "country__name", "destination", "rate", "increment", "effective_date", "change",
            "previous_rate", "row_number")),
            columns=["Prefix", "Country", "Destination", "Rate", "Increment", "Effective date", "Change",
                     "Previous rate", "Source row"])
        df["Change"] = df["Change"].map(lambda c: ChangeType(c).label if c else "")
        return export_response(df, fmt, f"{deck.vendor.code}_deck{deck.pk}_normalized", sheet_title="Normalized rates",
                               title=f"{deck.vendor.name} - normalized deck #{deck.pk}",
                               subtitle_lines=[f"Source file: {deck.original_filename}",
                                               f"Status: {deck.get_status_display()}"],
                               change_column="Change")
    if kind == "errors":
        df = issues_frame(deck.issues.all())
        return export_response(df, fmt, f"{deck.vendor.code}_deck{deck.pk}_error_report", sheet_title="Issues",
                               title=f"Error report - {deck.vendor.name} deck #{deck.pk}",
                               subtitle_lines=[f"Source file: {deck.original_filename}",
                                               f"Rows: {deck.total_rows:,} | rejected: {deck.error_rows:,} | "
                                               f"warnings: {deck.warning_count:,} | duplicates: {deck.duplicate_count:,}"])
    raise Http404


def issues_frame(issues, with_deck=False):
    rows = []
    for i in issues.select_related("deck__vendor") if with_deck else issues:
        row = {}
        if with_deck:
            row.update({"Deck": i.deck_id, "Vendor": i.deck.vendor.name, "File": i.deck.original_filename})
        row.update({"Row": i.row_number, "Level": i.get_level_display(), "Field": i.field,
                    "Value": i.value, "Problem": i.message})
        rows.append(row)
    cols = (["Deck", "Vendor", "File"] if with_deck else []) + ["Row", "Level", "Field", "Value", "Problem"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------- processing history
@login_required
def history(request):
    decks = RateDeck.objects.select_related("vendor", "uploaded_by")
    vendor = request.GET.get("vendor")
    status = request.GET.get("status")
    if vendor:
        decks = decks.filter(vendor_id=vendor)
    if status in RateDeck.Status.values:
        decks = decks.filter(status=status)
    if request.GET.get("issues"):
        decks = decks.filter(Q(error_rows__gt=0) | Q(duplicate_count__gt=0))
    page = Paginator(decks, 25).get_page(request.GET.get("page"))
    return render(request, "ratedecks/history.html", {
        "page": page, "vendors": Vendor.objects.order_by("name"), "statuses": RateDeck.Status.choices,
    })


@login_required
def error_reports(request):
    issues = DeckIssue.objects.select_related("deck__vendor").order_by("-deck__uploaded_at", "row_number", "id")
    level = request.GET.get("level")
    vendor = request.GET.get("vendor")
    q = request.GET.get("q", "").strip()
    if level in DeckIssue.Level.values:
        issues = issues.filter(level=level)
    if vendor:
        issues = issues.filter(deck__vendor_id=vendor)
    if q:
        issues = issues.filter(Q(message__icontains=q) | Q(value__icontains=q))

    if request.GET.get("fmt") in ("csv", "xlsx"):
        df = issues_frame(issues[:20000], with_deck=True)
        return export_response(df, request.GET["fmt"], "error_report", sheet_title="Issues",
                               title="RouteRate - error report")

    summary = {
        "errors": DeckIssue.objects.filter(level="error").count(),
        "warnings": DeckIssue.objects.filter(level="warning").count(),
        "duplicates": DeckIssue.objects.filter(level="duplicate").count(),
        "decks": RateDeck.objects.filter(Q(error_rows__gt=0) | Q(duplicate_count__gt=0)).count(),
    }
    return render(request, "ratedecks/errors.html", {
        "page": Paginator(issues, PAGE_SIZE).get_page(request.GET.get("page")),
        "vendors": Vendor.objects.order_by("name"), "levels": DeckIssue.Level.choices, "summary": summary,
    })


# ---------------------------------------------------------------- live rate browser (effective dates)
@login_required
def rate_browser(request):
    today = timezone.localdate()
    as_of = parse_day(request.GET.get("as_of"), today)
    view = request.GET.get("view", "live")
    rates = VendorRate.objects.select_related("vendor", "country", "deck")
    vendor = request.GET.get("vendor")
    country = request.GET.get("country")
    q = request.GET.get("q", "").strip()
    if vendor:
        rates = rates.filter(vendor_id=vendor)
    if country:
        rates = rates.filter(country_id=country)
    if q:
        rates = rates.filter(Q(prefix__startswith=q) | Q(destination__icontains=q))

    if view == "scheduled":
        rates = rates.scheduled_after(today).order_by("effective_from", "prefix")
    elif view == "history":
        rates = rates.order_by("prefix", "vendor__name", "effective_from")
    else:
        view = "live"
        rates = rates.active_on(as_of).order_by("prefix", "vendor__name")

    if request.GET.get("fmt") in ("csv", "xlsx"):
        df = pd.DataFrame([{
            "Vendor": r.vendor.name, "Prefix": r.prefix, "Country": r.country.name if r.country else "",
            "Destination": r.destination, "Rate": r.rate, "Increment": r.increment,
            "Effective from": r.effective_from, "Effective to": r.effective_to,
            "Change": r.get_change_display(), "Previous rate": r.previous_rate, "Deck": r.deck_id,
        } for r in rates[:50000]])
        label = {"live": f"live_{as_of}", "scheduled": "scheduled", "history": "history"}[view]
        return export_response(df, request.GET["fmt"], f"vendor_rates_{label}", sheet_title="Vendor rates",
                               title=f"Vendor rates - {view} {'as of ' + str(as_of) if view == 'live' else ''}",
                               change_column="Change")

    return render(request, "ratedecks/rates.html", {
        "page": Paginator(rates, PAGE_SIZE).get_page(request.GET.get("page")),
        "as_of": as_of, "today": today, "view": view,
        "vendors": Vendor.objects.order_by("name"), "countries": Country.objects.order_by("name"),
        "scheduled_count": VendorRate.objects.scheduled_after(today).count(),
    })
