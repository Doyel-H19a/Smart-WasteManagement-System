"""Small helpers shared by list views (safe query-string parsing)."""
from django.utils.dateparse import parse_date


def int_param(raw, maximum=None):
    """A safe non-negative integer from a query-string value, or None."""
    if raw.isdecimal() and len(raw) < 10:
        number = int(raw)
        if maximum is None or number <= maximum:
            return number
    return None


def date_param(raw):
    """A date from a query-string value (YYYY-MM-DD), or None."""
    try:
        return parse_date(raw)
    except ValueError:
        return None