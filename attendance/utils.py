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
    """
    Idempotently create AttendanceRecord(status='holiday', source='admin')
    rows for every Sunday in [date_from, date_to] × every employee.

    Parameters
    ----------
    admin_id : str
        Tenant scope. Required; no-op if falsy. New rows are stamped with
        this admin_id so multi-tenant filtering keeps working.
    date_from, date_to : date | str
        Inclusive window. Strings parsed as 'YYYY-MM-DD'. If either is
        missing or `date_from > date_to`, the call is a no-op.
    employees : iterable of Employee, optional
        Restrict the backfill to a specific set (e.g. the single employee
        hitting the mobile endpoint). When None, every Employee under
        `admin_id` is targeted.

    Returns
    -------
    int
        Number of rows the database actually inserted. Existing rows
        (admin overrides, prior auto-fills) are preserved via
        ignore_conflicts so this is safe to call on every page load.
    """
    if not admin_id:
        return 0

    df = _coerce_date(date_from)
    dt = _coerce_date(date_to)
    if df is None or dt is None or df > dt:
        return 0

    # Cap the backfill window at today — never pre-fill future Sundays as
    # Holiday. Existing rows for any date (admin overrides, prior auto-
    # fills) are preserved unconditionally by the bulk_create(..., ignore_
    # conflicts=True) call below, so this only prevents NEW rows from
    # being created for dates that haven't arrived yet.
    today = datetime.date.today()
    if dt > today:
        dt = today
    if df > dt:
        return 0

    sundays = _sundays_between(df, dt)
    if not sundays:
        return 0

    if employees is None:
        # Lazy import keeps attendance.utils free of an employees app dependency
        # at import time, which matters because attendance.models is imported
        # by employees.views during salary calculations.
        from employees.models import Employee
        emp_list = list(Employee.objects.filter(admin_id=admin_id))
    else:
        emp_list = [e for e in employees if e is not None]

    if not emp_list:
        return 0

    rows = [
        AttendanceRecord(
            admin_id=admin_id,
            employee=emp,
            date=sun,
            status='holiday',
            source='admin',
        )
        for emp in emp_list
        for sun in sundays
    ]

    # ignore_conflicts honours the (employee, date) unique-together — so
    # any pre-existing row (admin override, employee self-mark, prior
    # auto-fill) survives untouched. Return the actual insert count for
    # callers that want to log/telemetry.
    created = AttendanceRecord.objects.bulk_create(rows, ignore_conflicts=True)
    # On databases that don't return PKs from bulk_create+ignore_conflicts
    # (e.g. older MySQL), `created` is still the list passed in; counting
    # objects with non-None pk gives the actual insert count where the
    # backend supports it, otherwise it's a best-effort upper bound.
    return sum(1 for r in created if getattr(r, 'pk', None) is not None) or 0
