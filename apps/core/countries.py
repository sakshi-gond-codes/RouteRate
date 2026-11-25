"""Fast lookup from a phone prefix to its country (longest dial-code match)."""
from .models import Country


class CountryIndex:
    def __init__(self, countries=None):
        countries = list(countries if countries is not None else Country.objects.all())
        self.by_code = {c.dial_code: c for c in countries}
        self.by_id = {c.id: c for c in countries}
        self.max_len = max((len(code) for code in self.by_code), default=0)

    def resolve(self, prefix):
        """Return the Country whose dial code is the longest leading match of the prefix, or None."""
        for length in range(min(self.max_len, len(prefix)), 0, -1):
            country = self.by_code.get(prefix[:length])
            if country:
                return country
        return None

    @staticmethod
    def destination_matches(country, destination):
        """True when the vendor's destination text mentions the country (or one of its aliases)."""
        text = (destination or "").lower()
        return any(name and name in text for name in country.names)
