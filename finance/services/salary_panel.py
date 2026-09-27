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
    """Return list[dict] — one entry per site in the expense-card seed.

    Parity rule: `seed_site_names` MUST be the identical list the caller
    passed to `_group_expenses_by_site` for the on-screen expense cards
    (i.e. the result of `get_expense_card_seed(...)`). The panel then
    shows 1:1 the same site set, in the same order, with the same labels.
    Sites without any salary in the cycle appear with total = ₹0 and
    rows = []. Orphan sites (AUTO-SAL data for a site NOT in the seed —
    rare, legacy only) are appended at the end with label '— / <site>'.

    Falls back to `client_sites_for_admin(admin_id)` when seed is None,
    purely as a safety net for legacy callers; new callers must pass the
    seed.

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
    from projects.utils import client_site_label

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

    # Driver list: prefer the seed the caller already computed for the
    # expense cards (guarantees 1:1 parity). Fall back to the all-time
    # canonical list only when no seed was passed.
    if seed_site_names is None:
        from projects.utils import client_sites_for_admin
        driver = [
            (cs['site_name'], cs['label'])
            for cs in client_sites_for_admin(admin_id)
        ]
    else:
        driver = []
        seen = set()
        for name in seed_site_names:
            n = (name or '').strip()
            if not n:
                continue
            k = n.lower()
            if k in seen:
                continue
            seen.add(k)
            try:
                label = client_site_label(admin_id, n) or n
            except Exception:
                label = n
            driver.append((n, label))

    out = []
    consumed = set()
    for site_name, label in driver:
        key = site_name.lower()
        consumed.add(key)
        bucket = totals_by_key.get(key)
        if bucket is not None:
            total = bucket['total']
            rows = _finalize_rows(bucket['rows_by_date'])
        else:
            total = Decimal('0')
            rows = []
        out.append({
            'label': label,
            'site':  site_name,
            'total': total,
            'rows':  rows,
        })

    # Orphan AUTO-SAL totals (site not in the expense-card seed). Keep
    # visible for audit, tagged with the '— / <site>' fallback.
    orphans = []
    for key, bucket in totals_by_key.items():
        if key in consumed:
            continue
        site_name = bucket['site']
        try:
            label = client_site_label(admin_id, site_name)
        except Exception:
            label = f"— / {site_name}"
        orphans.append({
            'label': label,
            'site':  site_name,
            'total': bucket['total'],
            'rows':  _finalize_rows(bucket['rows_by_date']),
        })
    orphans.sort(key=lambda b: b['label'].lower())

    # Sort main rows alphabetically by label so the panel reads consistently;
    # orphan rows tail after, also sorted.
    out.sort(key=lambda b: b['label'].lower())
    return out + orphans
