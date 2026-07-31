"""Shared date helpers.

Anchors "today" to IST regardless of server timezone. Railway runs UTC;
users are in India (UTC+5:30). If we used server-local `date.today()`,
between 00:00 and 05:30 IST a mobile user could not mark attendance for
"today" because the server still thinks it is yesterday.

Every user-editable "event date" field routes its future-date check
through `validate_not_future` so the error text stays identical between
web and mobile.
"""
from datetime import date
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone

IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> date:
    """Return today's date in IST, regardless of server timezone."""
    return timezone.now().astimezone(IST).date()


def today_ist_context(request):
    """Template context processor.

    Exposes `today_ist` (a date object) and `today_ist_iso` (YYYY-MM-DD
    string) to every template so date `<input>` elements can render
    `max="{{ today_ist_iso }}"` without every view having to pass it in.
    """
    d = today_ist()
    return {'today_ist': d, 'today_ist_iso': d.isoformat()}


def validate_not_future(value, field_label: str = "Date") -> None:
    """Raise ValidationError if value (date, datetime, or ISO string) is
    after today IST.

    Accepts ISO "YYYY-MM-DD" strings because JSON payloads (attendance bulk
    save, etc.) hand dates to the ORM un-parsed; without this, comparing
    str > date raised TypeError and every bulk-created row failed.
    None values are ignored so this stays safe for nullable fields.
    """
    if value is None:
        return
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value.strip())
        except ValueError:
            raise ValidationError(
                f"{field_label} is not a valid date (expected YYYY-MM-DD)."
            )
    d = value.date() if hasattr(value, "date") and callable(value.date) else value
    if d > today_ist():
        raise ValidationError(
            f"{field_label} cannot be in the future. "
            f"Today is {today_ist().strftime('%d-%m-%Y')} (IST)."
        )
