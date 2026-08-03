"""
Per-day salary math — the extracted helper called by BOTH the monthly rollup
in employees.views._compute_attendance_breakdown AND the attendance→expense
signal in attendance/signals.py.

Extracted verbatim from the existing base_salary / daily_basis weight table
in _compute_attendance_breakdown so the numbers stay byte-identical to the
Salary Manager. Do not tweak weights here — change them in one place and
both consumers stay in sync.

Cut-over date lives here too so the signal, the payslip guard, and the
backfill migration all read the same constant.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from accounts.cycle_utils import get_cycle_ending_in_month


# Attendance-driven expense rows are the source of truth for cycles whose
# dates fall on or after this day. Cycles ending before this stay on the
# legacy monthly SAL-{pk}-YYYY-MM payslip flow.
ATTENDANCE_EXPENSE_CUTOVER = datetime.date(2026, 7, 26)


# Status → pay-day weight. Two tables, one per salary_type.
# Mirrors _compute_attendance_breakdown in employees/views.py exactly.
_WEIGHT_BASE_SALARY = {
    'present':     Decimal('1.0'),
    'week_off':    Decimal('1.0'),
    'holiday':     Decimal('1.0'),
    'half_day':    Decimal('0.5'),
    # Explicit zeros — enumerated so unexpected new status strings map to 0
    # rather than silently earning.
    'leave':       Decimal('0'),
    'absent':      Decimal('0'),
    'no_week_off': Decimal('0'),
}
_WEIGHT_DAILY_BASIS = {
    'present':     Decimal('1.0'),
    'week_off':    Decimal('1.0'),
    'holiday':     Decimal('0'),
    'half_day':    Decimal('0'),
    'leave':       Decimal('0'),
    'absent':      Decimal('0'),
    'no_week_off': Decimal('0'),
}


def _weight(salary_type: str, status: str) -> Decimal:
    table = _WEIGHT_DAILY_BASIS if salary_type == 'daily_basis' else _WEIGHT_BASE_SALARY
    return table.get(status or '', Decimal('0'))


def compute_daily_salary(employee, attendance_record) -> Decimal:
    """One-day salary amount for a single AttendanceRecord.

    Returns Decimal('0') for any status whose weight is 0 under the
    employee's salary_type — callers can use `amount <= 0` as a signal to
    delete any linked expense row (status flipped to absent, etc.).

    Also returns 0 for future dates (defensive: cycle_days math is fine, but
    we never pay for a day that hasn't happened).
    """
    if attendance_record is None or getattr(attendance_record, 'date', None) is None:
        return Decimal('0')

    # Defensive Sunday rule kept from the monthly formula: an auto-marked
    # Sunday holiday in the future is excluded from monthly earnings, so
    # exclude it here too for symmetry.
    today = datetime.date.today()
    if attendance_record.date > today:
        return Decimal('0')

    status      = attendance_record.status or ''
    salary_type = getattr(employee, 'salary_type', 'base_salary')
    weight      = _weight(salary_type, status)
    if weight <= 0:
        return Decimal('0')

    basic_salary = Decimal(str(getattr(employee, 'base_salary', 0) or 0))
    if basic_salary <= 0:
        return Decimal('0')

    if salary_type == 'daily_basis':
        # Daily-wage: base_salary is already a per-day rate.
        return (basic_salary * weight).quantize(Decimal('0.01'))

    # Base-salary: prorate by the cycle window this attendance falls in.
    cycle = get_cycle_ending_in_month(attendance_record.date)
    cycle_days = (cycle['end'] - cycle['start']).days + 1
    if cycle_days <= 0:
        return Decimal('0')
    daily_rate = basic_salary / Decimal(str(cycle_days))
    return (daily_rate * weight).quantize(Decimal('0.01'))


def build_expense_defaults(attendance_record, amount):
    """Field dict shared by the signal and the backfill migration.

    Kept here so both writers set the same fields the same way. Only the
    caller-supplied `amount` differs (backfill computes once; signal
    recomputes on each save)."""
    emp = attendance_record.employee
    loc  = (getattr(emp, 'location', '') or '').strip()
    site_name = ''
    if attendance_record.site_ref_id:
        site_name = attendance_record.site_ref.name if attendance_record.site_ref else ''
    if not site_name:
        site_name = (getattr(emp, 'site', '') or '').strip()
    location_site = f"{loc} / {site_name}" if loc and site_name else (loc or site_name or '')
    label = f"Salary — {emp.name} — {attendance_record.date} {attendance_record.status}"
    return {
        'type':            'expense',
        'source':          'salary_attendance',
        'employee':        emp,
        'site':            attendance_record.site_ref,
        'location_site':   location_site,
        'amount':          amount,
        'date':            attendance_record.date,
        'description':     label,
        'breakdown_note':  label,
        'expense_category':'other',
        'reference':       f'SAL-DAY-{attendance_record.pk}',
        'admin_id':        attendance_record.admin_id,
    }
