"""
Shared source-of-truth for the site names that render as site cards on both
the Expense Manager and Income Manager pages. The rule: a site card appears
if the site exists in Projects, in Attendance, in WorkLog, or in a legacy
Transaction/Income row — not only when someone has already entered money
against it. That way any site an admin adds in Attendance or Projects shows
up immediately as an editable zero-row card in Expense + Income.
"""

from finance.models import Transaction


def get_active_site_names(admin_id, restrict_today=False, today=None, module=None):
    """
    Canonical site-name strings for site cards. Delegates to
    projects.utils.sites_for_admin which unions:
      * projects.Site.name              (source of truth — casing wins)
      * attendance.AttendanceRecord.site   (CharField back-compat)
      * attendance.AttendanceRecord.site_ref__name (FK)

    Does NOT include legacy Transaction.location_site or Income.location_site
    distincts — those are considered orphans.

    `restrict_today=True` scopes the attendance contribution to `today`
    (a date). Projects.Site is always included.

    `module` ('expense' | 'income') applies the per-admin hide list from
    finance.ModuleHiddenSite: any name hidden for that (admin_id, module)
    is dropped from the result (case-insensitive). Pass None (default) to
    return the full union.
    """
    from projects.utils import sites_for_admin

    restrict_date = today if restrict_today and today is not None else None
    names = sites_for_admin(admin_id, restrict_attendance_to=restrict_date)

    if module in ('expense', 'income'):
        try:
            from finance.models import ModuleHiddenSite
            hidden_lower = {
                (n or '').strip().lower()
                for n in ModuleHiddenSite.objects
                    .filter(admin_id=admin_id, module=module)
                    .values_list('site_name', flat=True)
            }
            if hidden_lower:
                names = [n for n in names if n.strip().lower() not in hidden_lower]
        except Exception:
            pass

    return names


def has_unassigned_transactions(admin_id, txn_type=None):
    """True if any Transaction row for this tenant has a null/empty
    location_site. Used to decide whether to render the "(No Site)" bucket
    — we don't want an empty Unassigned card cluttering the UI."""
    from django.db.models import Q
    qs = Transaction.objects.filter(admin_id=admin_id)
    if txn_type:
        qs = qs.filter(type=txn_type)
    return qs.filter(Q(location_site__isnull=True) | Q(location_site='')).exists()
