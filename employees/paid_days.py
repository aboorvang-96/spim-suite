"""
Paid Days / Attendance Earnings — the ONE place this math lives.

Every consumer (Salary page list + Edit modal, salary report downloads,
Save, payslip generation, SPIM Lite mobile API, attendance calendar drawer
footer + per-cell amounts + Excel export) routes through this module.

Rate source (authoritative, decided 2026-11-25): the cycle's monthly
snapshot `SalaryUpdate.basic_salary` when a row exists for the payroll
month, else `Employee.base_salary`. See `resolve_cycle_rate`.
"""

import datetime
from decimal import Decimal

DAILY_BASIS = 'daily_basis'

STATUSES = ('present', 'week_off', 'holiday', 'half_day', 'leave', 'no_week_off')

# DO NOT inline this formula elsewhere. Daily: Present + WeekOff only. Monthly: Present + WeekOff + Holiday + 0.5*HalfDay.
# Any status not listed (leave, no_week_off, unknown) pays 0.
PAY_WEIGHTS = {
    True: {  # daily_basis
        'present':  Decimal('1'),
        'week_off': Decimal('1'),
    },
    False: {  # monthly (base_salary)
        'present':  Decimal('1'),
        'week_off': Decimal('1'),
        'holiday':  Decimal('1'),
        'half_day': Decimal('0.5'),
    },
}


def is_daily_basis(employee):
    return getattr(employee, 'salary_type', 'base_salary') == DAILY_BASIS


def day_weight(status, is_daily):
    """Pay weight for one AttendanceRecord.status under the rules above."""
    return PAY_WEIGHTS[bool(is_daily)].get(status, Decimal('0'))


def resolve_cycle_rate(employee, cycle_end):
    """Authoritative rate for the payroll month that `cycle_end` falls in:
    the month's SalaryUpdate.basic_salary snapshot, else Employee.base_salary.
    Mirrors the Salary page's salary_record lookup exactly."""
    from .models import SalaryUpdate
    sal = SalaryUpdate.objects.filter(
        employee=employee,
        month__year=cycle_end.year,
        month__month=cycle_end.month,
    ).first()
    value = sal.basic_salary if sal else employee.base_salary
    return Decimal(str(value or 0))


def summarize_paid_days(counts, *, is_daily, rate, cycle_days, has_records=True):
    """Pure (no DB) core of calculate_paid_days — unit-tested directly.

    `rate` is the per-day rate for daily_basis, the monthly salary otherwise
    (monthly per-day = rate / cycle_days).
    """
    rate = Decimal(str(rate or 0))
    c = {s: int(counts.get(s, 0) or 0) for s in STATUSES}

    if is_daily:
        per_day = rate
    else:
        per_day = rate / Decimal(cycle_days) if cycle_days > 0 else Decimal('0')

    if not has_records:
        if is_daily:
            # Daily-basis: no attendance → no earnings.
            paid_days, earnings = Decimal('0'), Decimal('0.00')
        else:
            # Monthly safe fallback: unmarked cycle pays the full salary so
            # payroll is never silently zeroed.
            paid_days = Decimal(cycle_days)
            earnings = rate.quantize(Decimal('0.01'))
    else:
        paid_days = sum(
            (Decimal(c[s]) * day_weight(s, is_daily) for s in STATUSES),
            Decimal('0'),
        )
        earnings = (per_day * paid_days).quantize(Decimal('0.01'))

    return {
        **c,
        'paid_days': paid_days,
        'attendance_earnings': earnings,
        'per_day_rate': per_day,
        'rate': rate,
        'cycle_days': cycle_days,
        'is_daily': bool(is_daily),
    }


def calculate_paid_days(employee, cycle_start, cycle_end, rate=None, today=None):
    """Returns {present, week_off, holiday, half_day, leave, no_week_off,
    paid_days, attendance_earnings, per_day_rate, rate, cycle_days, is_daily}.

    Future-dated records (after `today`) are never paid. `rate` defaults to
    resolve_cycle_rate(employee, cycle_end).
    """
    from django.db.models import Count
    from attendance.models import AttendanceRecord

    today = today or datetime.date.today()
    if rate is None:
        rate = resolve_cycle_rate(employee, cycle_end)
    cycle_days = (cycle_end - cycle_start).days + 1

    rows = (
        AttendanceRecord.objects
        .filter(employee=employee, date__gte=cycle_start, date__lte=cycle_end)
        .filter(date__lte=today)
        .order_by()  # drop Meta.ordering so GROUP BY is status only
        .values('status')
        .annotate(n=Count('id'))
    )
    counts = {r['status']: r['n'] for r in rows}
    return summarize_paid_days(
        counts,
        is_daily=is_daily_basis(employee),
        rate=rate,
        cycle_days=cycle_days,
        has_records=sum(counts.values()) > 0,
    )
