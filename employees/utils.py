import re


_EMP_ID_STRIP_RE = re.compile(r'[\s\-\.]+')


def normalize_employee_id(raw):
    """Canonicalize an Employee ID for storage and duplicate detection.

    Trims outer whitespace, removes all internal whitespace, strips hyphens
    and dots, and uppercases the remainder. Blank/None inputs return ''.

    Examples:
        >>> normalize_employee_id('SPIM020')
        'SPIM020'
        >>> normalize_employee_id('  spim020\\n')
        'SPIM020'
        >>> normalize_employee_id('SPIM 020')
        'SPIM020'
        >>> normalize_employee_id('SPIM-020')
        'SPIM020'
    """
    if raw is None:
        return ''
    return _EMP_ID_STRIP_RE.sub('', str(raw)).upper()


def compute_net_pay(attendance_earnings, ot=0, advance=0, deduction=0,
                    food_allowance=0, food_usage=0):
    """Single source of truth for net pay.

    SINGLE SOURCE OF TRUTH. Do not inline this formula elsewhere.
    Mobile API, web list, report rows, report totals, and cycle totals all call this.

    net = attendance_earnings + ot - advance - deduction
          + (food_allowance - food_usage)

    Applies whether or not a custom salary override is active. None is
    treated as 0. Returns an unrounded Decimal (round only for display).
    """
    from decimal import Decimal

    def _d(v):
        return Decimal(str(v)) if v not in (None, '') else Decimal('0')

    return (
        _d(attendance_earnings) + _d(ot) - _d(advance) - _d(deduction)
        + (_d(food_allowance) - _d(food_usage))
    )


def compute_net_pay_for_record(attendance_earnings, salary_record):
    """compute_net_pay() fed from a SalaryUpdate row (or None => zeros)."""
    r = salary_record
    return compute_net_pay(
        attendance_earnings,
        ot=r.ot_allowance if r else 0,
        advance=r.advance_pay if r else 0,
        deduction=r.total_deduction if r else 0,
        food_allowance=r.food_allowance if r else 0,
        food_usage=r.food_usage if r else 0,
    )
