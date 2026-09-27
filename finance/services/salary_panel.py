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


def build_salary_panel(admin_id, cycle_start, cycle_end):
    """Return list[dict] — one entry per Client/Site pair for the tenant.

    Parity rule: driver list is `projects.utils.client_sites_for_admin` so
    the panel shows the SAME set of rows as the Expense site cards. Sites
    with zero salary in the cycle still appear (total = ₹0, rows = []).
    Orphan sites (in AUTO-SAL/attendance data but not in the canonical
    list) are appended at the end with label '— / <site>'.

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

    Rows inside each site are ONE per date, summed across employees, sorted
    date-descending. Sort order of sites: alphabetical by label.
    """
    from employees.views import compute_cycle_salary_by_site
    from projects.utils import client_sites_for_admin, client_site_label

    by_site = compute_cycle_salary_by_site(admin_id, cycle_start, cycle_end)

    # totals_by_key[site_name_lower] = {'total': Decimal, 'rows_by_date': {date: Decimal}}
    totals_by_key = {}
    for raw_site, entries in by_site.items():
        raw = (raw_site or '').strip()
        if not raw:
            continue
        key = raw.lower()
        bucket = totals_by_key.setdefault(
            key,
            {'site': raw, 'total': Decimal('0'), 'rows_by_date': {}},
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

    out = []
    consumed = set()

    # Driver: canonical Client/Site list — same source expense cards use.
    for cs in client_sites_for_admin(admin_id):
        site_name = cs['site_name']
        key = site_name.lower()
        bucket = totals_by_key.get(key)
        consumed.add(key)
        if bucket is not None:
            total = bucket['total']
            rows = _finalize_rows(bucket['rows_by_date'])
        else:
            total = Decimal('0')
            rows = []
        out.append({
            'label': cs['label'],
            'site':  site_name,
            'total': total,
            'rows':  rows,
        })

    # Orphans: attendance/AUTO-SAL sites with no canonical match. Do not
    # drop silently — surface with '— / <site>' fallback label.
    for key, bucket in totals_by_key.items():
        if key in consumed:
            continue
        site_name = bucket['site']
        try:
            label = client_site_label(admin_id, site_name)
        except Exception:
            label = f"— / {site_name}"
        out.append({
            'label': label,
            'site':  site_name,
            'total': bucket['total'],
            'rows':  _finalize_rows(bucket['rows_by_date']),
        })

    out.sort(key=lambda b: b['label'].lower())
    return out
