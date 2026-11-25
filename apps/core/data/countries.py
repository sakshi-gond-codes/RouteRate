"""
Reference list of countries and their international dial codes (ITU-T E.164).

Used to validate every prefix in an uploaded rate deck: a prefix must start with
one of these codes. Matching uses the longest code, so "1876" (Jamaica) wins over
"1" (USA & Canada) for the prefix 18765.

Columns: name, ISO code, dial code, region, aliases (other names seen in vendor decks)
"""

COUNTRIES = [
    # North America & Caribbean (NANP shares code 1; islands use 4-digit codes)
    ("USA & Canada", "US", "1", "North America", "United States, USA, US, Canada, NANP, America"),
    ("Bahamas", "BS", "1242", "Caribbean", ""),
    ("Barbados", "BB", "1246", "Caribbean", ""),
    ("Trinidad and Tobago", "TT", "1868", "Caribbean", "Trinidad"),
    ("Jamaica", "JM", "1876", "Caribbean", ""),
    ("Dominican Republic", "DO", "1809", "Caribbean", "Dominican Rep"),
    ("Mexico", "MX", "52", "Latin America", ""),
    # Latin America
    ("Brazil", "BR", "55", "Latin America", "Brasil"),
    ("Argentina", "AR", "54", "Latin America", ""),
    ("Colombia", "CO", "57", "Latin America", ""),
    ("Chile", "CL", "56", "Latin America", ""),
    ("Peru", "PE", "51", "Latin America", ""),
    ("Venezuela", "VE", "58", "Latin America", ""),
    ("Ecuador", "EC", "593", "Latin America", ""),
    # Europe
    ("United Kingdom", "GB", "44", "Europe", "UK, Great Britain, England, Britain"),
    ("Ireland", "IE", "353", "Europe", "Eire"),
    ("Germany", "DE", "49", "Europe", "Deutschland"),
    ("France", "FR", "33", "Europe", ""),
    ("Spain", "ES", "34", "Europe", "Espana"),
    ("Italy", "IT", "39", "Europe", "Italia"),
    ("Portugal", "PT", "351", "Europe", ""),
    ("Netherlands", "NL", "31", "Europe", "Holland"),
    ("Belgium", "BE", "32", "Europe", ""),
    ("Switzerland", "CH", "41", "Europe", ""),
    ("Austria", "AT", "43", "Europe", ""),
    ("Sweden", "SE", "46", "Europe", ""),
    ("Norway", "NO", "47", "Europe", ""),
    ("Denmark", "DK", "45", "Europe", ""),
    ("Finland", "FI", "358", "Europe", ""),
    ("Poland", "PL", "48", "Europe", ""),
    ("Czech Republic", "CZ", "420", "Europe", "Czechia"),
    ("Romania", "RO", "40", "Europe", ""),
    ("Greece", "GR", "30", "Europe", ""),
    ("Hungary", "HU", "36", "Europe", ""),
    ("Ukraine", "UA", "380", "Europe", ""),
    ("Russia", "RU", "7", "Europe", "Russian Federation"),
    ("Turkey", "TR", "90", "Europe", "Turkiye"),
    # Middle East
    ("United Arab Emirates", "AE", "971", "Middle East", "UAE, Emirates"),
    ("Saudi Arabia", "SA", "966", "Middle East", "KSA"),
    ("Qatar", "QA", "974", "Middle East", ""),
    ("Kuwait", "KW", "965", "Middle East", ""),
    ("Oman", "OM", "968", "Middle East", ""),
    ("Bahrain", "BH", "973", "Middle East", ""),
    ("Jordan", "JO", "962", "Middle East", ""),
    ("Israel", "IL", "972", "Middle East", ""),
    # South Asia
    ("India", "IN", "91", "South Asia", ""),
    ("Pakistan", "PK", "92", "South Asia", ""),
    ("Bangladesh", "BD", "880", "South Asia", ""),
    ("Sri Lanka", "LK", "94", "South Asia", ""),
    ("Nepal", "NP", "977", "South Asia", ""),
    ("Afghanistan", "AF", "93", "South Asia", ""),
    # East & South-East Asia, Oceania
    ("China", "CN", "86", "Asia Pacific", "PRC"),
    ("Hong Kong", "HK", "852", "Asia Pacific", ""),
    ("Japan", "JP", "81", "Asia Pacific", ""),
    ("South Korea", "KR", "82", "Asia Pacific", "Korea"),
    ("Singapore", "SG", "65", "Asia Pacific", ""),
    ("Malaysia", "MY", "60", "Asia Pacific", ""),
    ("Thailand", "TH", "66", "Asia Pacific", ""),
    ("Vietnam", "VN", "84", "Asia Pacific", "Viet Nam"),
    ("Philippines", "PH", "63", "Asia Pacific", ""),
    ("Indonesia", "ID", "62", "Asia Pacific", ""),
    ("Australia", "AU", "61", "Asia Pacific", ""),
    ("New Zealand", "NZ", "64", "Asia Pacific", ""),
    # Africa
    ("Nigeria", "NG", "234", "Africa", ""),
    ("Kenya", "KE", "254", "Africa", ""),
    ("South Africa", "ZA", "27", "Africa", "RSA"),
    ("Egypt", "EG", "20", "Africa", ""),
    ("Ghana", "GH", "233", "Africa", ""),
    ("Morocco", "MA", "212", "Africa", ""),
    ("Ethiopia", "ET", "251", "Africa", ""),
    ("Tanzania", "TZ", "255", "Africa", ""),
    ("Uganda", "UG", "256", "Africa", ""),
    # Global / non-geographic services
    ("Satellite - Inmarsat", "XS", "870", "Global Services", "Inmarsat"),
    ("Satellite - Iridium", "XI", "8816", "Global Services", "Iridium"),
    ("International Networks", "XN", "882", "Global Services", "Intl Networks"),
]
