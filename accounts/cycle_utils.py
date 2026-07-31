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
    """The most recent COMPLETED cycle (default payslip generation target).

    If we are still inside the current cycle (ref <= cycle_end), return the
    cycle that ended immediately before it.
    """
    ref = reference_date or today_ist()
    current = get_salary_cycle(ref)
    if ref <= current['end']:
        prev_end = current['start'] - timedelta(days=1)
        return get_salary_cycle(prev_end)
    return current


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


def get_force_active_until(reference_date=None):
    """Default force-active window end for the "Reactivate" toggle:
    15th of the month AFTER `reference_date`."""
    ref = reference_date or today_ist()
    return (ref.replace(day=1) + relativedelta(months=1)).replace(day=15)
