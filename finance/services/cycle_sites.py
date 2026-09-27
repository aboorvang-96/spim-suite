"""
Single-source union of Client/Site pairs for the Expense Manager's cycle
view. Consumed by BOTH the expense site cards and the Salary Expenses
side panel — they must never drift.

Union sources:
  * projects.utils.sites_for_admin — cycle-scoped canonical list
    (Projects.Site is_active=True ∪ Attendance in the current+previous
    cycle window; optionally today-restricted for a fresh landing).
  * Transaction.location_site distincts for expense rows in
    [cycle_start, cycle_end] — surfaces legacy strings.
  * employees.views.compute_cycle_salary_by_site — surfaces
    pre-CUTOVER attendance-derived salary sites that have no
    [AUTO-SAL:*] Transaction row yet.

The ModuleHiddenSite hide-list (module='expense') is applied at the
end. Case-insensitive dedup; Projects.Site casing wins.

Returns list[dict] sorted alphabetically by label:
    [{'client_name': 'UNIT 1 & 2 SPECTRO', 'site_name': 'KKNPP',
      'label': 'UNIT 1 & 2 SPECTRO / KKNPP', 'site_id': 42}, ...]
"""

from datetime import date

from finance.models import Transaction


# Cutover for canonical-only Attendance+Projects site enumeration.
# Salary written from this cycle onward MUST resolve to a canonical site
# via attendance.signals._resolve_working_site (whose OFFICE fallback is
# itself a per-tenant Projects.Site). If a card is missing while its
# salary shows in the KPI tile after this date, that's a data-hygiene
# gap in _resolve_working_site — investigate the attendance write path,
# do NOT widen the enumerator to hide the orphan.
SITES_CYCLE_CANONICAL_ONLY_FROM = date(2026, 10, 26)


def sites_for_cycle(admin_id, cycle_start, cycle_end,
                    restrict_today=False, today=None, module='expense'):
    """Cycle-scoped Client/Site universe for the expense / income pages.

    Two behavior modes:
      * Legacy (cycle_start < SITES_CYCLE_CANONICAL_ONLY_FROM): union of
        canonical base ∪ Transaction.location_site distincts ∪ AUTO-SAL
        distincts ∪ attendance-derived salary sites. Widens preserve
        visibility of pre-cutover orphan salary sites.
      * Canonical (cycle_start >= SITES_CYCLE_CANONICAL_ONLY_FROM):
        canonical base ONLY, ModuleHiddenSite hide-list still applied.
        Every widen is skipped so orphans stay loud in Django admin.
    """
    from projects.utils import sites_for_admin, client_site_label

    # 1. Canonical base — cycle-scoped attendance ∪ active Projects.Site.
    #    sites_for_admin honours a today-restrict via `restrict_attendance_to`.
    restrict_date = today if restrict_today and today is not None else None
    base_names = sites_for_admin(admin_id, restrict_attendance_to=restrict_date)

    canonical = {}   # site_name_lower → site_name (canonical casing)
    for n in base_names:
        if not n:
            continue
        n2 = n.strip()
        if not n2:
            continue
        canonical.setdefault(n2.lower(), n2)

    # Canonical-only mode — apply hide-list and return early. All widens
    # are intentionally skipped from the cutover cycle onward.
    if cycle_start and cycle_start >= SITES_CYCLE_CANONICAL_ONLY_FROM:
        if module in ('expense', 'income'):
            try:
                from finance.models import ModuleHiddenSite
                hidden = {
                    (h or '').strip().lower()
                    for h in ModuleHiddenSite.objects
                        .filter(admin_id=admin_id, module=module)
                        .values_list('site_name', flat=True)
                }
                if hidden:
                    for k in list(canonical.keys()):
                        if k in hidden:
                            del canonical[k]
            except Exception:
                pass
        return _resolve_labels(admin_id, canonical, client_site_label)

    # 2. Widen with any non-salary Transaction.location_site distincts
    #    inside the cycle window (legacy expense rows).
    if cycle_start and cycle_end:
        non_salary_txn_sites = (
            Transaction.objects
            .filter(admin_id=admin_id, type='expense',
                    date__gte=cycle_start, date__lte=cycle_end)
            .exclude(reference__startswith='[AUTO-SAL:')
            .exclude(location_site__isnull=True).exclude(location_site='')
            .values_list('location_site', flat=True).distinct()
        )
        for n in non_salary_txn_sites:
            if not n:
                continue
            k = (n or '').strip().lower()
            if k and k not in canonical:
                canonical[k] = n.strip()

    # 3. Apply ModuleHiddenSite filter to the non-salary universe ONLY.
    #    A tenant may have bulk-deleted expenses for a site and hidden
    #    it from this module — respect that for legacy/non-salary data.
    #    Salary-active sites (steps 4 + 5) override the hide-list because
    #    real money paid in-cycle must always be visible in the UI.
    if module in ('expense', 'income'):
        try:
            from finance.models import ModuleHiddenSite
            hidden = {
                (h or '').strip().lower()
                for h in ModuleHiddenSite.objects
                    .filter(admin_id=admin_id, module=module)
                    .values_list('site_name', flat=True)
            }
            if hidden:
                for k in list(canonical.keys()):
                    if k in hidden:
                        del canonical[k]
        except Exception:
            pass

    # 4. Widen with distinct location_site values from [AUTO-SAL:*]
    #    Transaction rows in the cycle. Per-spec: this is the primary
    #    salary-site signal — any site with real payroll booked in-cycle
    #    must be visible in cards + panel, hide-list notwithstanding.
    if cycle_start and cycle_end:
        auto_sal_sites = (
            Transaction.objects
            .filter(admin_id=admin_id, type='expense',
                    reference__startswith='[AUTO-SAL:',
                    date__gte=cycle_start, date__lte=cycle_end)
            .exclude(location_site__isnull=True).exclude(location_site='')
            .values_list('location_site', flat=True).distinct()
        )
        for n in auto_sal_sites:
            if not n:
                continue
            k = (n or '').strip().lower()
            if k and k not in canonical:
                canonical[k] = n.strip()

    # 5. Widen with salary-active sites in the cycle (Attendance-derived —
    #    surfaces pre-CUTOVER salary sites that never emitted AUTO-SAL
    #    Transaction rows). Also overrides the hide-list.
    try:
        from employees.views import compute_cycle_salary_by_site
        by_site = compute_cycle_salary_by_site(admin_id, cycle_start, cycle_end)
        for raw_site in by_site.keys():
            n = (raw_site or '').strip()
            if not n:
                continue
            k = n.lower()
            if k not in canonical:
                canonical[k] = n
    except Exception:
        pass

    # 6. Resolve each site_name to a Client/Site label dict.
    return _resolve_labels(admin_id, canonical, client_site_label)


def _resolve_labels(admin_id, canonical, client_site_label):
    """Turn {lower_name: display_name} into the public list-of-dicts shape.
    Extracted so both the legacy union path and the canonical-only cutover
    path emit identical output."""
    out = []
    for site_name in canonical.values():
        try:
            label = client_site_label(admin_id, site_name) or site_name
        except Exception:
            label = site_name
        client_name = '—'
        site_id = None
        if label and ' / ' in label:
            head = label.split(' / ', 1)[0].strip()
            if head:
                client_name = head
        out.append({
            'client_name': client_name,
            'site_name':   site_name,
            'label':       label,
            'site_id':     site_id,
        })
    out.sort(key=lambda d: d['label'].lower())
    return out
