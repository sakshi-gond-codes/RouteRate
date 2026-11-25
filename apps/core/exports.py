"""
CSV and Excel export helpers used across the app.

Every export goes through a Pandas DataFrame. Excel files are written with OpenPyXL
and get a styled header row, frozen panes, an auto filter, number formats and
sensible column widths so they are ready to send.
"""
import io
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1E2A4A")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1E2A4A")
THIN = Side(style="thin", color="D9DEE8")

CHANGE_FILLS = {
    "Increase": PatternFill("solid", fgColor="FDE2E1"),
    "Decrease": PatternFill("solid", fgColor="DCF5E7"),
    "New": PatternFill("solid", fgColor="DDEBFF"),
    "Removed": PatternFill("solid", fgColor="EEEEEE"),
}

RATE_FORMAT = "0.0000"
RATE_COLUMNS_HINT = ("rate", "cost", "price", "sell", "margin (usd)", "spread")


def _clean(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def dataframe_to_csv_response(df, filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.write("﻿")  # BOM so Excel opens UTF-8 correctly
    df.to_csv(response, index=False)
    return response


def style_table(ws, header_row, n_rows, columns, rate_decimals=4):
    """Style a table that starts at header_row on worksheet ws."""
    for idx, name in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        cell.border = Border(bottom=THIN)

        lname = str(name).lower()
        letter = get_column_letter(idx)
        is_rate = any(h in lname for h in RATE_COLUMNS_HINT) and "%" not in lname
        is_pct = "%" in lname
        width = max(len(str(name)) + 2, 10)
        for row in range(header_row + 1, header_row + n_rows + 1):
            c = ws.cell(row=row, column=idx)
            if is_rate and isinstance(c.value, (int, float)):
                c.number_format = "0." + "0" * rate_decimals
            elif is_pct and isinstance(c.value, (int, float)):
                c.number_format = "0.0"
            elif isinstance(c.value, (date, datetime)):
                c.number_format = "yyyy-mm-dd"
            if row - header_row <= 200:
                width = max(width, min(len(str(c.value or "")) + 2, 48))
        ws.column_dimensions[letter].width = width

    if n_rows:
        last = get_column_letter(len(columns))
        ws.auto_filter.ref = f"A{header_row}:{last}{header_row + n_rows}"
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)


def write_sheet(ws, df, title=None, subtitle_lines=(), change_column=None):
    """Write a DataFrame to a worksheet with an optional title block."""
    row = 1
    if title:
        ws.cell(row=1, column=1, value=title).font = TITLE_FONT
        row = 2
        for line in subtitle_lines:
            ws.cell(row=row, column=1, value=line).font = Font(color="5B6478")
            row += 1
        row += 1  # blank line before table

    header_row = row
    for col_idx, name in enumerate(df.columns, start=1):
        ws.cell(row=header_row, column=col_idx, value=str(name))

    change_idx = list(df.columns).index(change_column) + 1 if change_column in df.columns else None
    for r_offset, values in enumerate(df.itertuples(index=False), start=1):
        for col_idx, value in enumerate(values, start=1):
            if value is not None and not isinstance(value, str) and pd.isna(value):
                value = None
            ws.cell(row=header_row + r_offset, column=col_idx, value=_clean(value))
        if change_idx:
            fill = CHANGE_FILLS.get(values[change_idx - 1])
            if fill:
                for col_idx in range(1, len(df.columns) + 1):
                    ws.cell(row=header_row + r_offset, column=col_idx).fill = fill

    style_table(ws, header_row, len(df), list(df.columns))
    return header_row


def dataframe_to_xlsx_response(df, filename, sheet_title="Data", title=None, subtitle_lines=(), change_column=None,
                               extra_sheets=None):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    write_sheet(ws, df, title=title, subtitle_lines=subtitle_lines, change_column=change_column)
    for name, extra_df in (extra_sheets or {}).items():
        write_sheet(wb.create_sheet(name[:31]), extra_df)

    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return response


def export_response(df, fmt, filename, **xlsx_options):
    """Return a CSV or XLSX download for the DataFrame. fmt is 'csv' or 'xlsx'."""
    stamp = timezone.localdate().isoformat()
    name = f"{filename}_{stamp}"
    if fmt == "xlsx":
        return dataframe_to_xlsx_response(df, name, **xlsx_options)
    return dataframe_to_csv_response(df, name)
