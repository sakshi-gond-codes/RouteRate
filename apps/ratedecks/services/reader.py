"""
Reads CSV and Excel rate decks into a Pandas DataFrame of raw text.

Vendor files are messy: title rows above the header, semicolon delimiters,
decimal commas, Excel dates, numbers stored as text. So the reader keeps every
cell as text, remembers the original file row number, and leaves all
interpretation to the normalization step.
"""
import csv
import io
from datetime import date, datetime, time

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from .mapping import header_score

SUPPORTED_TYPES = {"csv", "xlsx"}
CSV_DELIMITERS = [",", ";", "\t", "|"]
MAX_HEADER_SEARCH_ROWS = 25


class DeckReadError(Exception):
    pass


def file_type_from_name(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("csv", "txt"):
        return "csv"
    if ext in ("xlsx", "xlsm"):
        return "xlsx"
    if ext == "xls":
        raise DeckReadError("Old .xls files are not supported. Open the file in Excel and save it as .xlsx.")
    raise DeckReadError("Unsupported file type. Upload a .csv or .xlsx file.")


# ---------------------------------------------------------------- cell conversion
def cell_to_text(value):
    """Convert an Excel cell value to text without losing meaning (447.0 -> '447', dates -> ISO)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == time(0, 0) else value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value).strip()


# ---------------------------------------------------------------- CSV
def _decode(raw_bytes):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DeckReadError("Could not read the file encoding. Save it as UTF-8 CSV.")


def detect_delimiter(text):
    """Pick the delimiter that splits the most lines into the same number of columns."""
    sample_lines = [line for line in text.splitlines()[:60] if line.strip()]
    best, best_score = ",", -1
    for delimiter in CSV_DELIMITERS:
        counts = [len(row) for row in csv.reader(sample_lines, delimiter=delimiter)]
        multi = [c for c in counts if c > 1]
        if not multi:
            continue
        mode = max(set(multi), key=multi.count)
        score = multi.count(mode) * mode
        if score > best_score:
            best, best_score = delimiter, score
    return best


def read_csv_rows(path):
    with open(path, "rb") as fh:
        text = _decode(fh.read())
    delimiter = detect_delimiter(text)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return rows, delimiter


# ---------------------------------------------------------------- Excel
def excel_sheet_names(path):
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        return wb.sheetnames
    finally:
        wb.close()


def read_excel_rows(path, sheet_name=None):
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # corrupt or password-protected file
        raise DeckReadError(f"Could not open the Excel file: {exc}") from exc
    try:
        names = wb.sheetnames
        if sheet_name and sheet_name in names:
            ws = wb[sheet_name]
        else:
            # Default to the first sheet that actually contains data
            ws = next((wb[n] for n in names if (wb[n].max_row or 0) > 1), wb[names[0]])
        rows = [[cell_to_text(v) for v in row] for row in ws.iter_rows(values_only=True)]
        return rows, ws.title, names
    finally:
        wb.close()


# ---------------------------------------------------------------- public API
def read_raw(path, file_type, sheet_name=None):
    """
    Return (raw_df, info). raw_df has one row per file row (index = file row number, 1-based)
    and columns 0..n-1, every value as stripped text.
    """
    info = {"sheet_names": [], "sheet": "", "delimiter": ""}
    if file_type == "csv":
        rows, delimiter = read_csv_rows(path)
        info["delimiter"] = {"\t": "Tab"}.get(delimiter, delimiter)
    elif file_type == "xlsx":
        rows, sheet, names = read_excel_rows(path, sheet_name)
        info.update(sheet=sheet, sheet_names=names)
    else:
        raise DeckReadError("Unsupported file type.")

    if not rows:
        raise DeckReadError("The file is empty.")
    width = max(len(r) for r in rows)
    padded = [[(c or "").strip() for c in r] + [""] * (width - len(r)) for r in rows]
    df = pd.DataFrame(padded, dtype=str)
    df.index = range(1, len(df) + 1)  # real file row numbers
    # Drop columns that are empty in every row (common in Excel exports)
    df = df.loc[:, (df != "").any(axis=0)]
    df.columns = range(df.shape[1])
    if df.empty or (df == "").all(axis=None):
        raise DeckReadError("The file has no data.")
    return df, info


def detect_header_row(raw_df):
    """Return the 1-based file row that looks most like a header (e.g. has 'Prefix' and 'Rate')."""
    best_row, best_score = None, 0
    for row_number, values in raw_df.head(MAX_HEADER_SEARCH_ROWS).iterrows():
        score = header_score(values.tolist())
        if score > best_score:
            best_row, best_score = row_number, score
        if score >= 3:
            break
    if best_row is None:
        # No recognisable header: use the first non-empty row
        non_empty = raw_df[(raw_df != "").any(axis=1)]
        best_row = int(non_empty.index[0])
    return int(best_row)


def column_labels(raw_df, header_row):
    """Readable unique labels for each column, e.g. 'Dial Code' or 'Column C'."""
    labels, seen = [], {}
    header_values = raw_df.loc[header_row].tolist() if header_row in raw_df.index else []
    for idx in range(raw_df.shape[1]):
        name = header_values[idx].strip() if idx < len(header_values) else ""
        if not name:
            name = f"Column {get_column_letter(idx + 1)}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        labels.append(name)
    return labels


def data_frame(raw_df, header_row):
    """Rows below the header, labelled with column names, blank rows removed."""
    labels = column_labels(raw_df, header_row)
    body = raw_df.loc[raw_df.index > header_row].copy()
    body.columns = labels
    body = body[(body != "").any(axis=1)]
    return body
