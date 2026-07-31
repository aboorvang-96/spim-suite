"""Salary cycle helpers.

SPIM salary cycle runs 26th of month N-1 → 25th of month N. All salary,
attendance-earnings and payslip flows use these helpers to pick cycle
boundaries so the boundary math lives in exactly one place.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from accounts.date_utils import today_ist


def get_salary_cycle(reference_date=None):
    """Return the salary cycle that CONTAINS `reference_date`.

    Cycle window: 26th of month N-1 → 25th of month N.

    Returns dict:
        start:     date (26th of prev month or same month)
        end:       date (25th of ref month or next month)
        label:     e.g. 'Jun-Jul 2026'
        month_key: e.g. '2026-07' (payroll month = the month the cycle
                   ends in — used as SalaryUpdate.month's first-of-month)
    """
    ref = reference_date or today_ist()
    if ref.day >= 26:
        start = ref.replace(day=26)
        end = (start + relativedelta(months=1)).replace(day=25)
    else:
        end = ref.replace(day=25)
        start = (end - relativedelta(months=1)).replace(day=26)
    label = f"{start.strftime('%b')}-{end.strftime('%b %Y')}"
    month_key = end.strftime('%Y-%m')
    return {'start': start, 'end': end, 'label': label, 'month_key': month_key}


def get_previous_cycle(reference_date=None):
    """The payroll cycle whose END date falls in `reference_date`'s
    calendar month — i.e. the cycle we are currently operating on for
    payslip generation and mobile salary display.

    Day-of-month is IGNORED — every day in July resolves to the Jun 26 →
    Jul 25 cycle; every day in August resolves to the Jul 26 → Aug 25
    cycle. In particular, on the 26th of a month we still return the
    prior cycle (that just ended on the 25th), not the freshly-started
    one — HR needs the full month's window to complete the payroll.

    Equivalent to `get_cycle_ending_in_month(reference_date)`; kept as a
    named alias because callers read better with this name at the site.
    """
    ref = reference_date or today_ist()
    return get_cycle_ending_in_month(ref)


def is_payslip_download_active(payslip_generated_at, force_active_until=None):
    """Green if today (IST) <= 15th of the calendar month AFTER generation.

    `force_active_until` is a date; when set and today <= it, the download
    stays green regardless of the 15th rule (used by the HR "Reactivate
    expired downloads" toggle).
    """
    if payslip_generated_at is None:
        return False
    gen_date = (
        payslip_generated_at.date()
        if hasattr(payslip_generated_at, 'date') and callable(payslip_generated_at.date)
        else payslip_generated_at
    )
    today = today_ist()
    if force_active_until and today <= force_active_until:
        return True
    threshold = (gen_date.replace(day=1) + relativedelta(months=1)).replace(day=15)
    return today <= threshold


def get_cycle_ending_in_month(month_date):
    """Return the salary cycle that ENDS in `month_date`'s calendar month.

    Deterministic — day-of-month is ignored. For any input in July, always
    returns 26 Jun → 25 Jul; for any input in August, always returns
    26 Jul → 25 Aug. This is the exact pre-refactor semantic used by
    `_compute_attendance_breakdown` and is the safe choice whenever the
    caller wants "the cycle for payroll month X" rather than "the cycle
    containing today". Use `get_salary_cycle` only when the day-sensitive
    'current cycle' rule is genuinely what you want.
    """
    end = month_date.replace(day=25)
    start = (end - relativedelta(months=1)).replace(day=26)
    label = f"{start.strftime('%b')}-{end.strftime('%b %Y')}"
    month_key = end.strftime('%Y-%m')
    return {'start': start, 'end': end, 'label': label, 'month_key': month_key}


def get_force_active_until(reference_date=None):
    """Default force-active window end for the "Reactivate" toggle:
    15th of the month AFTER `reference_date`."""
    ref = reference_date or today_ist()
    return (ref.replace(day=1) + relativedelta(months=1)).replace(day=15)
