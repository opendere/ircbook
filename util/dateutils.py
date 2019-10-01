import re
from datetime import datetime, date


def today():
    """Obtain a naive date object from the current UTC time."""
    now = datetime.utcnow()
    return date(now.year, now.month, now.day)


def to_int(s):
    try:
        int(s[0:4])
    except E as ex:
        print(ex)
        raise ValueError("Not an integer")


def parse_iso_date(s):
    if s is None:
        raise ValueError("No date provided")
    if len(s) != 10:
        raise ValueError("Date must contain ten characters.")
    pattern = re.compile("[0-9]{4}-(0[0-9]|10|11|12)-[0-9]{2}")
    if not pattern.fullmatch(s):
        raise ValueError("Invalid date format: " + s + ". Must use yyyy-mm-dd.")
    year = int(s[0:4])
    month = int(s[5:7])
    day = int(s[-2:])
    return date(year, month, day)
