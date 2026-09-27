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


def get_expense_card_seed(admin_id, selected_sites=None, restrict_today=False,
                          today=None, cycle_start=None, cycle_end=None,
                          include_salary_sites=False):
    """Single source of truth for the site-card seed list rendered on
    /expenses/ AND /income/.

    Both pages must render the identical card set for the same tenant —
    same names, same order — so this helper encapsulates the full rule:

      * If `selected_sites` is provided (user picked cards / filter),
        return the intersection with the canonical universe (case-
        insensitive), falling back to the raw picked names when the
        picks aren't in the universe.
      * Otherwise, return the cycle-scoped Client/Site universe.
        When `include_salary_sites=True` (Expense Manager path), the
        shared `finance.services.cycle_sites.sites_for_cycle` union is
        used — it also surfaces salary-only sites so the cards match
        the Salary Expenses panel 1:1. Income keeps the legacy union
        (default False) to avoid inheriting salary-only rows.

    Returns list[str] of site_name for backward compatibility.
    """
    from finance.models import Transaction

    if selected_sites:
        universe = get_active_site_names(admin_id, restrict_today=False, module='expense')
        wanted = {s.lower() for s in selected_sites}
        seed = [n for n in universe if n.lower() in wanted]
        return seed if seed else list(selected_sites)

    if include_salary_sites and cycle_start and cycle_end:
        from finance.services.cycle_sites import sites_for_cycle
        return [
            d['site_name']
            for d in sites_for_cycle(
                admin_id, cycle_start, cycle_end,
                restrict_today=restrict_today,
                today=today,
                module='expense',
            )
        ]

    seed = get_active_site_names(
        admin_id,
        restrict_today=restrict_today,
        today=today,
        module='expense',
    )
    if cycle_start and cycle_end:
        cycle_txn_sites = (
            Transaction.objects
            .filter(admin_id=admin_id, type='expense',
                    date__gte=cycle_start, date__lte=cycle_end)
            .exclude(location_site__isnull=True).exclude(location_site='')
            .values_list('location_site', flat=True).distinct()
        )
        seen = {(n or '').strip().lower() for n in seed if n}
        for n in cycle_txn_sites:
            k = (n or '').strip().lower()
            if k and k not in seen:
                seed.append(n.strip())
                seen.add(k)
    return seed


def has_unassigned_transactions(admin_id, txn_type=None):
    """True if any Transaction row for this tenant has a null/empty
    location_site. Used to decide whether to render the "(No Site)" bucket
    — we don't want an empty Unassigned card cluttering the UI."""
    from django.db.models import Q
    qs = Transaction.objects.filter(admin_id=admin_id)
    if txn_type:
        qs = qs.filter(type=txn_type)
    return qs.filter(Q(location_site__isnull=True) | Q(location_site='')).exists()
