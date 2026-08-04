"""
Shared source-of-truth for the site names that render as site cards on both
the Expense Manager and Income Manager pages. The rule: a site card appears
if the site exists in Projects, in Attendance, in WorkLog, or in a legacy
Transaction/Income row — not only when someone has already entered money
against it. That way any site an admin adds in Attendance or Projects shows
up immediately as an editable zero-row card in Expense + Income.
"""

from finance.models import Transaction


def get_active_site_names(admin_id, restrict_today=False, today=None):
    """
    Canonical site-name strings for site cards. Union of:
      * projects.Site.name              (source of truth — casing wins)
      * attendance.AttendanceRecord.site   (CharField back-compat)
      * attendance.AttendanceRecord.site_ref__name (FK)
      * projects.WorkLog.site__name
      * finance.Transaction.location_site distinct (legacy fallback)

    Deduped case-insensitively. Sorted A→Z.

    `restrict_today=True` scopes the attendance/worklog contribution to
    `today` (a date). Projects.Site and Transaction distincts are always
    included — those are the "master" registries that shouldn't shrink to
    zero on a quiet day.
    """
    canonical = {}   # lower_key -> display

    def _add(name):
        if not name:
            return
        n = name.strip()
        if not n:
            return
        k = n.lower()
        if k not in canonical:
            canonical[k] = n

    # Projects.Site FIRST — canonical casing wins for any later match.
    try:
        from projects.models import Site as ProjSite
        for n in (
            ProjSite.objects
            .filter(admin_id=admin_id)
            .values_list('name', flat=True)
        ):
            _add(n)
    except Exception:
        pass

    # Attendance — respects today-restriction when caller asked for it.
    try:
        from attendance.models import AttendanceRecord
        att = AttendanceRecord.objects.filter(admin_id=admin_id)
        if restrict_today and today is not None:
            att = att.filter(date=today)
        for n in (
            att.exclude(site__isnull=True).exclude(site='')
               .values_list('site', flat=True).distinct()
        ):
            _add(n)
        for n in (
            att.filter(site_ref__isnull=False)
               .values_list('site_ref__name', flat=True).distinct()
        ):
            _add(n)
    except Exception:
        pass

    # WorkLog — same today-restriction rule.
    try:
        from projects.models import WorkLog
        wl = WorkLog.objects.filter(admin_id=admin_id, site__isnull=False)
        if restrict_today and today is not None:
            wl = wl.filter(date=today)
        for n in wl.values_list('site__name', flat=True).distinct():
            _add(n)
    except Exception:
        pass

    # Legacy transactions — always included so manual-entry sites don't
    # disappear when Projects/Attendance haven't been populated yet.
    try:
        for n in (
            Transaction.objects
            .filter(admin_id=admin_id)
            .exclude(location_site__isnull=True).exclude(location_site='')
            .values_list('location_site', flat=True).distinct()
        ):
            _add(n)
    except Exception:
        pass

    try:
        from income.models import Income
        for n in (
            Income.objects
            .filter(admin_id=admin_id)
            .exclude(location_site__isnull=True).exclude(location_site='')
            .values_list('location_site', flat=True).distinct()
        ):
            _add(n)
    except Exception:
        pass

    return sorted(canonical.values(), key=lambda s: s.lower())


def has_unassigned_transactions(admin_id, txn_type=None):
    """True if any Transaction row for this tenant has a null/empty
    location_site. Used to decide whether to render the "(No Site)" bucket
    — we don't want an empty Unassigned card cluttering the UI."""
    from django.db.models import Q
    qs = Transaction.objects.filter(admin_id=admin_id)
    if txn_type:
        qs = qs.filter(type=txn_type)
    return qs.filter(Q(location_site__isnull=True) | Q(location_site='')).exists()
