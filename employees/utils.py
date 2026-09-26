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
