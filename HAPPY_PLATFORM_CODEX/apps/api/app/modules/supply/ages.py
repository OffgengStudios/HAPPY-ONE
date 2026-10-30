"""Calendar age projections. Missing event dates never become today's date."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


def programme_today() -> date:
    return datetime.now(ZoneInfo("Africa/Accra")).date()


def event_age(birth: date | None, reference: date | None) -> int | None:
    if birth is None or reference is None or reference < birth:
        return None
    # A leap-day birthday advances on March 1 in non-leap years.
    return (
        reference.year - birth.year - ((reference.month, reference.day) < (birth.month, birth.day))
    )
