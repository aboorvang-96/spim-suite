"""
Attendance helpers shared by the Suite admin views and the Lite mobile API.

The headline helper here is `ensure_sunday_holidays`, which lazily backfills
the AttendanceRecord table with an admin-sourced 'holiday' row for every
Sunday × every employee in a given date range. Called from:

  * attendance.views.load_attendance — Suite admin attendance page
  * api.views.mobile_attendance      — Lite employee attendance fetch

so any cycle a user actually views ends up with Sundays populated. Existing
rows (including manual admin overrides) are never touched — bulk_create
with ignore_conflicts honours the AttendanceRecord (employee, date) unique-
together.

Salary impact: the Suite salary module already excludes Sundays from both
the numerator and denominator of _compute_attendance_earnings (see
`.exclude(date__week_day=1)`), so persisting Sundays as 'holiday' rows
does NOT inflate payslips — Sundays remain unpaid working days.
"""

from __future__ import annotations

import datetime
from typing import Iterable

from .models import AttendanceRecord


def _coerce_date(value):
    """Accept either a date object or a 'YYYY-MM-DD' string. Returns None
    if the value is empty or cannot be parsed — caller should bail out."""
    if not value:
        return None
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    try:
        return datetime.datetime.strptime(str(value), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _sundays_between(date_from: datetime.date, date_to: datetime.date) -> list[datetime.date]:
    """Return every Sunday-dated day in [date_from, date_to] inclusive.
    Uses Python's weekday() (Mon=0..Sun=6) so the rule is independent of
    locale / first-day-of-week settings."""
    if date_from > date_to:
        return []
    out: list[datetime.date] = []
    cur = date_from
    while cur <= date_to:
        if cur.weekday() == 6:
            out.append(cur)
        cur += datetime.timedelta(days=1)
    return out


def ensure_sunday_holidays(
    admin_id: str,
    date_from,
    date_to,
    *,
    employees: Iterable | None = None,
) -> int:
    """No-op. Sunday auto-generation has been removed — attendance rows
    (including Sundays) now exist only when entered manually. The signature
    is preserved so existing callers stay import-safe."""
    return 0


# ---------------------------------------------------------------------------
# Attendance display mapping — single source of truth
# ---------------------------------------------------------------------------
#
# Lifted verbatim from attendance.views.load_attendance's nested closure so
# both the Suite web view AND the SPIM Lite HR mobile endpoint call the SAME
# helper. Behavior is byte-for-byte identical to the original closure — only
# the function name changed (was `_display_status`, now `display_status`).
# ---------------------------------------------------------------------------

STATUS_DISPLAY = {
    'present':      'Present',
    'absent':       'Absent',
    'half_day':     'Half Day',
    'leave':        'Leave',
    'holiday':      'Holiday',
    # The attendance summary template (templates/attendance/index.html)
    # buckets by 'Weekly Off' (see byDate / kpiCounts / groups / slugMap).
    # Returning 'Week Off' here makes the bucket lookup fall through to
    # the else branch and the rendered cell always reads 0. Emit the
    # label the template expects so summaries/charts/KPIs aggregate.
    'week_off':     'Weekly Off',
    'no_week_off':  'No Week Off',
}


def display_status(r):
    # Sundays are treated exactly like any other day — no auto-remap.
    return STATUS_DISPLAY.get(r.status, 'Present')
