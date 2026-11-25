# Sample rate decks

All vendors, rates and files here are **fictional**. Country dial codes are the real ITU codes.
Each vendor uses a different layout on purpose, to show the column mapping and normalization.
`python manage.py seed_demo` loads the files in `rate_decks/` through the real processing pipeline.

| File | Vendor | What it demonstrates |
|---|---|---|
| `rate_decks/01_kestrel_voice_full_az.csv` | Kestrel Voice | Clean CSV, ISO dates, full A-Z deck |
| `rate_decks/02_orchid_telecom_rates.xlsx` | Orchid Telecom | Excel with 3 title rows, separate Country/Description columns, grouped dial codes like `447, 4474, 4475`, Excel date cells, second sheet with notes |
| `rate_decks/03_tidewater_carrier_deck.csv` | Tidewater Carrier | Semicolon delimiter, decimal commas `0,0123`, UPPERCASE names, increments written `60-60`, no date column, only country/main breakouts (shows "via" fallback in LCR) |
| `rate_decks/04_quillon_wholesale_az.xlsx` | Quillon Wholesale | Numeric prefix cells, `dd/mm/yyyy` text dates, duplicated prefixes with different prices |
| `rate_decks/05_zephyr_route_full.csv` | Zephyr Route | `+44` and `0049` prefixes, `$` prices, a range `9170-9179` |
| `rate_decks/06_kestrel_voice_update_partial.csv` | Kestrel Voice | Partial update: increases, decreases, new prefixes, short-notice increases and future-dated (scheduled) rates |

## Try it yourself

| File | Upload as | What you will see |
|---|---|---|
| `try_it_yourself/orchid_price_update.xlsx` | Orchid Telecom, **Partial update**, default effective date = today | New / Increase / Decrease detection, short-notice increase warnings, a duplicate prefix |
| `try_it_yourself/messy_vendor_deck.csv` | Any vendor, Partial update | Header on row 3, 12 rejected rows (letters in prefixes, unknown dial code, negative/empty/zero/too-high rates, impossible dates, bad increment, reversed range, leading 0), warnings and duplicates. Download the error report. |

Regenerate the files with `python scripts/generate_sample_data.py`.
