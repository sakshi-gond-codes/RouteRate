"""
Generates the fictional sample rate decks in sample_data/.

Every vendor uses a different file layout on purpose, so the flexible column
mapping and normalization can be demonstrated:

  Kestrel Voice      clean CSV, ISO dates, full breakouts
  Orchid Telecom     Excel with title rows, grouped "44, 447" dial-code lists, Excel dates
  Tidewater Carrier  semicolon CSV, decimal commas, no dates, country-level codes only
  Quillon Wholesale  Excel, numeric prefixes, dd/mm/yyyy text dates, a few duplicates
  Zephyr Route       CSV with +44 / 0049 prefixes, ranges like 9170-9179, $ prices

All vendor names, rates and files are fictional. Country dial codes are real ITU codes.
Run:  python scripts/generate_sample_data.py
"""
import csv
import random
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from apps.core.data.countries import COUNTRIES  # noqa: E402

OUT = ROOT / "sample_data"
DECKS = OUT / "rate_decks"
TRY = OUT / "try_it_yourself"

# (prefix, destination, base cost USD/min, tier) tier: country | main | sub
BREAKOUTS = []


def add(prefix, name, rate, tier="main"):
    BREAKOUTS.append((prefix, name, rate, tier))


def add_subs(parent, name, rate, digits):
    for d in digits:
        add(f"{parent}{d}", name, rate, "sub")


# North America & Caribbean
add("1", "USA & Canada", 0.0040, "country"); add("1907", "USA - Alaska", 0.0150); add("1808", "USA - Hawaii", 0.0060)
add("1242", "Bahamas", 0.1100, "country"); add("1246", "Barbados", 0.1300, "country")
add("1868", "Trinidad and Tobago", 0.0900, "country"); add("1876", "Jamaica", 0.1400, "country")
add("1809", "Dominican Republic", 0.0450, "country")
# Latin America
add("52", "Mexico - Fixed", 0.0070, "country"); add("5255", "Mexico - Mexico City", 0.0040); add("521", "Mexico - Mobile", 0.0110)
add("55", "Brazil - Fixed", 0.0070, "country"); add("5511", "Brazil - Sao Paulo", 0.0050); add("55119", "Brazil - Sao Paulo Mobile", 0.0280)
add("54", "Argentina - Fixed", 0.0120, "country"); add("549", "Argentina - Mobile", 0.0350)
add("57", "Colombia - Fixed", 0.0060, "country"); add("573", "Colombia - Mobile", 0.0085)
add("56", "Chile - Fixed", 0.0140, "country"); add("569", "Chile - Mobile", 0.0200)
add("51", "Peru - Fixed", 0.0100, "country"); add("519", "Peru - Mobile", 0.0300)
# Europe
add("44", "United Kingdom - Fixed", 0.0042, "country"); add("447", "United Kingdom - Mobile", 0.0105)
add_subs("447", "United Kingdom - Mobile", 0.0105, "45789")
add("353", "Ireland - Fixed", 0.0090, "country"); add("3538", "Ireland - Mobile", 0.0200)
add("49", "Germany - Fixed", 0.0048, "country"); add("4915", "Germany - Mobile", 0.0210)
add("4916", "Germany - Mobile", 0.0230); add("4917", "Germany - Mobile", 0.0220)
add("33", "France - Fixed", 0.0052, "country"); add("336", "France - Mobile", 0.0190); add("337", "France - Mobile", 0.0195)
add("34", "Spain - Fixed", 0.0050, "country"); add("346", "Spain - Mobile", 0.0120); add("347", "Spain - Mobile", 0.0125)
add("39", "Italy - Fixed", 0.0060, "country"); add("393", "Italy - Mobile", 0.0170)
add("351", "Portugal - Fixed", 0.0080, "country"); add("3519", "Portugal - Mobile", 0.0150)
add("31", "Netherlands - Fixed", 0.0070, "country"); add("316", "Netherlands - Mobile", 0.0350)
add("32", "Belgium - Fixed", 0.0090, "country"); add("324", "Belgium - Mobile", 0.0400)
add("41", "Switzerland - Fixed", 0.0110, "country"); add("417", "Switzerland - Mobile", 0.0450)
add("46", "Sweden - Fixed", 0.0060, "country"); add("467", "Sweden - Mobile", 0.0090)
add("48", "Poland - Fixed", 0.0080, "country")
for d in "567":
    add(f"48{d}", "Poland - Mobile", 0.0110)
add("30", "Greece - Fixed", 0.0070, "country"); add("306", "Greece - Mobile", 0.0180)
add("90", "Turkey - Fixed", 0.0300, "country"); add("905", "Turkey - Mobile", 0.0600)
add("7", "Russia - Fixed", 0.0450, "country"); add("79", "Russia - Mobile", 0.0550)
# Middle East
add("971", "United Arab Emirates - Fixed", 0.0800, "country"); add("9715", "United Arab Emirates - Mobile", 0.1200)
add("966", "Saudi Arabia - Fixed", 0.0450, "country"); add("9665", "Saudi Arabia - Mobile", 0.0600)
add("974", "Qatar", 0.0900, "country"); add("965", "Kuwait", 0.0700, "country"); add("968", "Oman", 0.1300, "country")
# South Asia
add("91", "India - Fixed", 0.0080, "country")
for d in "789":
    add(f"91{d}", "India - Mobile", 0.0085)
add_subs("917", "India - Mobile", 0.0085, "0123456789")
add("92", "Pakistan - Fixed", 0.0200, "country"); add("923", "Pakistan - Mobile", 0.0250)
add_subs("923", "Pakistan - Mobile", 0.0250, "01234")
add("880", "Bangladesh - Fixed", 0.0110, "country"); add("8801", "Bangladesh - Mobile", 0.0115)
add_subs("8801", "Bangladesh - Mobile", 0.0115, "3456789")
add("94", "Sri Lanka - Fixed", 0.0600, "country"); add("947", "Sri Lanka - Mobile", 0.0750)
add("977", "Nepal", 0.0900, "country")
# Asia Pacific
add("63", "Philippines - Fixed", 0.0900, "country"); add("639", "Philippines - Mobile", 0.1100)
add("62", "Indonesia - Fixed", 0.0350, "country"); add("628", "Indonesia - Mobile", 0.0400)
add("60", "Malaysia - Fixed", 0.0120, "country"); add("601", "Malaysia - Mobile", 0.0140)
add("65", "Singapore - Fixed", 0.0060, "country"); add("658", "Singapore - Mobile", 0.0070); add("659", "Singapore - Mobile", 0.0070)
add("66", "Thailand - Fixed", 0.0100, "country"); add("668", "Thailand - Mobile", 0.0110); add("669", "Thailand - Mobile", 0.0110)
add("84", "Vietnam - Fixed", 0.0450, "country"); add("849", "Vietnam - Mobile", 0.0480)
add("86", "China - Fixed", 0.0090, "country"); add("861", "China - Mobile", 0.0090)
add("852", "Hong Kong - Fixed", 0.0050, "country")
for d in "569":
    add(f"852{d}", "Hong Kong - Mobile", 0.0060)
add("81", "Japan - Fixed", 0.0180, "country")
for d in "789":
    add(f"81{d}0", "Japan - Mobile", 0.0700)
add("82", "South Korea - Fixed", 0.0150, "country"); add("8210", "South Korea - Mobile", 0.0200)
add("61", "Australia - Fixed", 0.0120, "country"); add("614", "Australia - Mobile", 0.0220)
add("64", "New Zealand - Fixed", 0.0200, "country"); add("642", "New Zealand - Mobile", 0.0400)
# Africa
add("234", "Nigeria - Fixed", 0.0900, "country"); add("2347", "Nigeria - Mobile", 0.1050); add("2348", "Nigeria - Mobile", 0.1000)
add("254", "Kenya - Fixed", 0.1100, "country"); add("2547", "Kenya - Mobile", 0.1200)
add("27", "South Africa - Fixed", 0.0250, "country")
for d in "678":
    add(f"27{d}", "South Africa - Mobile", 0.0700)
add("20", "Egypt - Fixed", 0.0800, "country"); add("201", "Egypt - Mobile", 0.0900)
add("233", "Ghana - Fixed", 0.1700, "country"); add("2332", "Ghana - Mobile", 0.1800); add("2335", "Ghana - Mobile", 0.1800)
add("212", "Morocco - Fixed", 0.0900, "country"); add("2126", "Morocco - Mobile", 0.3000); add("2127", "Morocco - Mobile", 0.3000)
# Satellite (very expensive, only some vendors)
add("8816", "Satellite - Iridium", 4.2000, "satellite"); add("870", "Satellite - Inmarsat", 3.5000, "satellite")

DIAL = {code: region for _, _, code, region, _ in COUNTRIES}


def region_of(prefix):
    for n in range(min(4, len(prefix)), 0, -1):
        if prefix[:n] in DIAL:
            return DIAL[prefix[:n]]
    return ""


VENDORS = {
    "KST": {"seed": 11, "default": 1.00, "regions": {"Europe": 0.97}, "coverage": 0.93, "satellite": True},
    "ORC": {"seed": 22, "default": 1.04, "regions": {"Asia Pacific": 0.91, "South Asia": 0.94}, "coverage": 0.90, "satellite": False},
    "TDW": {"seed": 33, "default": 1.06, "regions": {"Africa": 0.85, "Middle East": 0.92}, "coverage": 0.95, "satellite": False},
    "QLN": {"seed": 44, "default": 1.07, "regions": {"South Asia": 0.87, "Latin America": 0.94}, "coverage": 0.90, "satellite": True},
    "ZPH": {"seed": 55, "default": 1.08, "regions": {"Europe": 0.90, "North America": 0.94}, "coverage": 0.88, "satellite": False},
}


def vendor_rates(code):
    """Return [(prefix, destination, rate)] for a vendor: base cost x regional strength x noise."""
    cfg = VENDORS[code]
    rng = random.Random(cfg["seed"])
    group_noise = {}
    rows = []
    # A vendor either serves a whole country (fixed + mobile breakouts) or not at all.
    country_prefixes = sorted((p for p, _, _, t in BREAKOUTS if t == "country"), key=len, reverse=True)
    excluded = {p for p in country_prefixes if p != "1" and rng.random() > cfg["coverage"]}

    def country_of(prefix):
        return next((c for c in country_prefixes if prefix.startswith(c)), None)

    for prefix, name, base, tier in BREAKOUTS:
        if tier == "satellite" and not cfg["satellite"]:
            continue
        if country_of(prefix) in excluded:
            continue
        if tier == "sub" and (code == "TDW" or rng.random() > 0.85):
            continue  # Tidewater only quotes country and main breakouts; others skip a few ranges
        factor = cfg["regions"].get(region_of(prefix), cfg["default"])
        if code == "ORC":  # Orchid prices a whole destination at one rate -> grouped dial codes
            noise = group_noise.setdefault(name, rng.uniform(0.94, 1.06))
        else:
            noise = rng.uniform(0.93, 1.07)
        rows.append((prefix, name, round(base * factor * noise, 4)))
    return rows


# ---------------------------------------------------------------- writers
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="2F3B59")


def write_csv(path, rows, delimiter=","):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh, delimiter=delimiter).writerows(rows)


def style_header(ws, row, n):
    for c in range(1, n + 1):
        cell = ws.cell(row=row, column=c)
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        ws.column_dimensions[cell.column_letter].width = 22


def kestrel():
    rows = [["Destination", "Prefix", "Rate", "Effective Date", "Billing Increment"]]
    for prefix, name, rate in vendor_rates("KST"):
        inc = "6/6" if prefix == "1" else "60/60"
        rows.append([name, prefix, f"{rate:.4f}", "2026-08-01", inc])
    write_csv(DECKS / "01_kestrel_voice_full_az.csv", rows)
    return rows


def orchid():
    grouped = {}
    for prefix, name, rate in vendor_rates("ORC"):
        grouped.setdefault((name, rate), []).append(prefix)
    wb = Workbook()
    ws = wb.active
    ws.title = "Rates"
    ws["A1"] = "Orchid Telecom - Wholesale Rate Notification"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Currency: USD per minute. All rates are fictional sample data."
    ws["A3"] = "Account: SAMPLE-0042"
    headers = ["Country", "Description", "Dial Codes", "Price USD/min", "Valid From", "Interval"]
    ws.append([])
    ws.append(headers)
    style_header(ws, 5, len(headers))
    for (name, rate), prefixes in grouped.items():
        country, _, desc = name.partition(" - ")
        ws.append([country, desc or "All", ", ".join(prefixes), rate, date(2026, 8, 15), "1/1"])
        ws.cell(row=ws.max_row, column=5).number_format = "dd-mmm-yyyy"
    ws.column_dimensions["C"].width = 48
    notes = wb.create_sheet("Notes")
    notes["A1"] = "Rates valid until further notice. Increases need 7 days notice."
    wb.save(DECKS / "02_orchid_telecom_rates.xlsx")


def tidewater():
    rows = [["Tidewater Carrier - Price list"], ["Generated for sample customer"], [],
            ["Code", "Description", "Cost", "Billing"]]
    for prefix, name, rate in vendor_rates("TDW"):
        rows.append([prefix, name.upper(), f"{rate:.4f}".replace(".", ","), "60-60"])
    write_csv(DECKS / "03_tidewater_carrier_deck.csv", rows, delimiter=";")


def quillon():
    wb = Workbook()
    ws = wb.active
    ws.title = "Quillon A-Z"
    headers = ["Destination", "Prefix", "Rate", "Effective Date", "Increment"]
    ws.append(headers)
    style_header(ws, 1, len(headers))
    rates = vendor_rates("QLN")
    for prefix, name, rate in rates:
        ws.append([name, int(prefix), rate, "01/09/2026", "60/60"])
    # Vendor mistakes: the same prefix twice with different prices
    for prefix, name, rate in [r for r in rates if r[0] in ("447", "9179", "2348")]:
        ws.append([name, int(prefix), round(rate * 1.08, 4), "01/09/2026", "60/60"])
    wb.save(DECKS / "04_quillon_wholesale_az.xlsx")


def zephyr():
    rates = vendor_rates("ZPH")
    india_sub = [r for r in rates if r[0].startswith("917") and len(r[0]) == 4]
    rows = [["Breakout", "Dial Codes", "Rate (USD)", "Billing"]]
    for i, (prefix, name, rate) in enumerate(rates):
        if prefix.startswith("917") and len(prefix) == 4:
            continue  # written below as a single range row
        shown = f"+{prefix}" if i % 3 == 0 else (f"00{prefix}" if i % 3 == 1 else prefix)
        rows.append([name, shown, f"${rate:.4f}", "60/60"])
    if india_sub:
        avg = round(sum(r[2] for r in india_sub) / len(india_sub), 4)
        rows.append(["India - Mobile", "9170-9179", f"${avg:.4f}", "60/60"])
    write_csv(DECKS / "05_zephyr_route_full.csv", rows)


def kestrel_update(base_rows):
    rng = random.Random(99)
    current = {r[1]: (r[0], float(r[2])) for r in base_rows[1:]}
    picks = rng.sample(sorted(p for p in current if p not in ("8816",)), 26)
    rows = [["Destination", "Prefix", "Rate", "Effective Date", "Billing Increment"]]
    for i, prefix in enumerate(picks):
        name, rate = current[prefix]
        if i < 10:
            new, eff = rate * rng.uniform(1.05, 1.18), "2026-10-01"     # increases, 7 days notice
        elif i < 20:
            new, eff = rate * rng.uniform(0.82, 0.96), "2026-10-01"     # decreases
        elif i < 23:
            new, eff = rate * rng.uniform(1.10, 1.20), "2026-11-20"     # scheduled future increases
        else:
            new, eff = rate * rng.uniform(1.04, 1.08), "2026-09-26"     # short-notice increases
        rows.append([name, prefix, f"{new:.4f}", eff, "60/60"])
    for prefix, name, rate in [("4473", "United Kingdom - Mobile", 0.0112), ("49176", "Germany - Mobile", 0.0236),
                               ("33644", "France - Mobile", 0.0201)]:
        rows.append([name, prefix, f"{rate:.4f}", "2026-10-01", "60/60"])
    write_csv(DECKS / "06_kestrel_voice_update_partial.csv", rows)


def orchid_update():
    wb = Workbook()
    ws = wb.active
    ws.title = "Price changes"
    headers = ["Country", "Description", "Dial Codes", "Price USD/min", "Interval"]
    ws.append(headers)
    style_header(ws, 1, len(headers))
    orc = {p: (n, r) for p, n, r in vendor_rates("ORC")}
    rng = random.Random(7)
    changes = sorted(orc)[5:60:4]
    for i, prefix in enumerate(changes):
        name, rate = orc[prefix]
        country, _, desc = name.partition(" - ")
        factor = rng.uniform(1.06, 1.15) if i % 2 == 0 else rng.uniform(0.85, 0.95)
        ws.append([country, desc or "All", prefix, round(rate * factor, 4), "1/1"])
    ws.append(["Philippines", "Mobile", "63917", 0.1050, "1/1"])           # new prefix
    ws.append(["Thailand", "Mobile", "669", 0.0101, "1/1"])                # duplicate with different prices
    ws.append(["Thailand", "Mobile", "669", 0.0108, "1/1"])
    wb.save(TRY / "orchid_price_update.xlsx")


def messy():
    rows = [
        ["Messy Vendor Ltd - rates (sample with deliberate mistakes)"],
        [],
        ["Destination", "Code", "Price", "Start", "Billing"],
        ["United Kingdom - Fixed", "44", "0.0045", "15/10/2026", "60/60"],
        ["United Kingdom - Mobile", "+44 7", "0.0108", "15/10/2026", "60/60"],
        ["United Kingdom - Mobile", "4470-4472", "0.0110", "15/10/2026", "60/60"],
        ["Germany - Mobile", "0049 151, 0049 152", "0,0215", "15.10.2026", "60/60"],
        ["France - Mobile", "4916", "0.0220", "15/10/2026", "60/60"],
        ["India - Mobile", "9198", "$0.0089", "Immediate", "1/1"],
        ["Unknown", "ABC12", "0.0100", "15/10/2026", "60/60"],
        ["Nowhere", "999123", "0.0200", "15/10/2026", "60/60"],
        ["Spain - Fixed", "34", "-0.0050", "15/10/2026", "60/60"],
        ["Spain - Mobile", "346", "", "15/10/2026", "60/60"],
        ["Italy - Fixed", "39", "0", "15/10/2026", "60/60"],
        ["Italy - Mobile", "393", "free", "15/10/2026", "60/60"],
        ["Portugal - Mobile", "3519", "0.0160", "31/02/2026", "60/60"],
        ["Greece - Mobile", "306", "0.0190", "15/10/2026", "sixty"],
        ["Japan - Mobile", "8190", "12.5", "15/10/2026", "60/60"],
        ["Satellite - Iridium", "8816", "4.3500", "15/10/2026", "60/60"],
        ["United Kingdom - Mobile", "4479-4470", "0.0110", "15/10/2026", "60/60"],
        ["Singapore - Mobile", "658", "0.0072", "15/10/2026", "60/60"],
        ["Singapore - Mobile", "658", "0.0068", "15/10/2026", "60/60"],
        ["Hong Kong - Fixed", "852", "0.0051", "15/10/2026", "60/60"],
        ["Hong Kong - Fixed", "852", "0.0051", "15/10/2026", "60/60"],
        ["Mexico - Fixed", "052", "0.0071", "15/10/2026", "60/60"],
        ["Brazil - Fixed", "55", "0.0072", "2027-12-31", "60/60"],
        [],
        ["Australia - Mobile", "614", "0.0230", "15/10/2026", "60/60"],
    ]
    write_csv(TRY / "messy_vendor_deck.csv", rows)


if __name__ == "__main__":
    DECKS.mkdir(parents=True, exist_ok=True)
    TRY.mkdir(parents=True, exist_ok=True)
    k = kestrel()
    orchid()
    tidewater()
    quillon()
    zephyr()
    kestrel_update(k)
    orchid_update()
    messy()
    print(f"Breakouts: {len(BREAKOUTS)}")
    for f in sorted(OUT.rglob("*.*")):
        print(f.relative_to(ROOT))
