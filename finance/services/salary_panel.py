"""
Salary Expenses panel data builder.

Feeds the togglable side panel on the Expense Manager. Sources per-site
salary directly from AttendanceRecord (via
employees.views.compute_cycle_salary_by_site) so the panel's per-site
totals sum to the same figure the KPI tile / Salary Report PDF show —
including pre-CUTOVER attendance that never emitted [AUTO-SAL:*]
Transaction rows.

Site casing is normalised to Projects.Site's canonical spelling where
possible via projects.utils.sites_for_admin — the same rule Expense
site cards use so both surfaces agree.
"""
from decimal import Decimal


def build_salary_panel(admin_id, cycle_start, cycle_end, seed_site_names=None):
    """Return list[dict] — one entry per site in the shared cycle-sites union.

    Single code path: driver is `finance.services.cycle_sites.sites_for_cycle`,
    the same helper that seeds the expense cards. Cards and panel therefore
    render the identical site set for the same cycle. When the caller passes
    `seed_site_names` (a pre-narrowed list, e.g. after selected_sites
    filtering), the panel restricts to that intersection so filtered card
    views stay 1:1 with the panel.

    Sites without any salary in the cycle appear with total = ₹0, rows = [].
    Ordering: alphabetical by label.

    Shape:
        [
          {
            'label':  'UNIT 1 & 2 SPECTRO / KKNPP',
            'site':   'KKNPP',
            'total':  Decimal('39000.00'),
            'rows':   [{'date': date(2026, 8, 4),
                        'amount': Decimal('12000')}, ...],
          },
          ...
        ]
    """
    from employees.views import compute_cycle_salary_by_site
    from finance.services.cycle_sites import sites_for_cycle

    # Per-site salary totals (Attendance-derived — includes pre-CUTOVER data).
    by_site = compute_cycle_salary_by_site(admin_id, cycle_start, cycle_end)

    totals_by_key = {}
    for raw_site, entries in by_site.items():
        raw = (raw_site or '').strip()
        if not raw:
            continue
        key = raw.lower()
        bucket = totals_by_key.setdefault(
            key,
            {'total': Decimal('0'), 'rows_by_date': {}},
        )
        for entry in entries:
            amount = entry['amount'] or Decimal('0')
            bucket['total'] += amount
            d = entry['date']
            bucket['rows_by_date'][d] = bucket['rows_by_date'].get(d, Decimal('0')) + amount

    def _finalize_rows(rows_by_date):
        rows = [{'date': d, 'amount': amt} for d, amt in rows_by_date.items()]
        rows.sort(key=lambda r: (r['date'] or cycle_start), reverse=True)
        return rows

    # Shared driver — same union the expense cards render.
    driver = sites_for_cycle(admin_id, cycle_start, cycle_end, module='expense')

    # Optional intersection with the caller's pre-narrowed seed (e.g. when
    # the user has applied a site filter). Keeps panel and cards 1:1.
    if seed_site_names is not None:
        allowed = {(n or '').strip().lower() for n in seed_site_names if n}
        driver = [d for d in driver if d['site_name'].lower() in allowed]

    out = []
    for entry in driver:
        site_name = entry['site_name']
        label     = entry['label']
        bucket    = totals_by_key.get(site_name.lower())
        if bucket is not None:
            total = bucket['total']
            rows  = _finalize_rows(bucket['rows_by_date'])
        else:
            total = Decimal('0')
            rows  = []
        out.append({
            'label': label,
            'site':  site_name,
            'total': total,
            'rows':  rows,
        })

    out.sort(key=lambda b: b['label'].lower())
    return out
