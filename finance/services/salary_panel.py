"""
Salary Expenses panel data builder.

Feeds the togglable side panel on the Expense Manager. Reads the
AUTO-SAL Transaction rows for a tenant in the given cycle window,
groups them per site, and returns rows suitable for direct template
iteration.

Site casing is normalised to Projects.Site's canonical spelling where
possible via projects.utils.sites_for_admin — the same rule Expense
site cards use so both surfaces agree.
"""
from collections import OrderedDict
from decimal import Decimal

from finance.models import Transaction


def build_salary_panel(admin_id, cycle_start, cycle_end):
    """Return list[dict] — one entry per site with salary rows this cycle.

    Shape:
        [
          {
            'site':   'RAGURAM',
            'total':  Decimal('39000.00'),
            'rows':   [
              {'date': date(2026, 8, 4), 'amount': Decimal('12000')},
              ...
            ],
          },
          ...
        ]

    Sites with zero salary rows in the cycle are omitted. Sites are
    sorted alphabetically (case-insensitive). Rows inside each site are
    sorted date-descending.
    """
    salary_qs = (
        Transaction.objects
        .filter(
            admin_id=admin_id,
            type='expense',
            reference__startswith='[AUTO-SAL:',
            date__gte=cycle_start,
            date__lte=cycle_end,
        )
        .values('location_site', 'date', 'amount')
    )

    # Canonical display casing per site — Projects.Site casing wins.
    canonical = {}   # lower → display
    try:
        from projects.utils import sites_for_admin
        for name in sites_for_admin(admin_id):
            canonical.setdefault(name.strip().lower(), name.strip())
    except Exception:
        pass

    # Bucket: lower_key → {'site': display, 'total': Decimal, 'rows': list}
    buckets = {}
    for row in salary_qs:
        raw = (row['location_site'] or '').strip()
        if not raw:
            # Unattributable salary rows shouldn't clutter the panel —
            # the resync command / admin needs to fix Attendance for
            # them, not stare at an untitled bucket here.
            continue
        key = raw.lower()
        display = canonical.get(key, raw)
        b = buckets.get(key)
        if b is None:
            b = {'site': display, 'total': Decimal('0'), 'rows': []}
            buckets[key] = b
        amount = row['amount'] or Decimal('0')
        b['total'] += amount
        b['rows'].append({'date': row['date'], 'amount': amount})

    for b in buckets.values():
        b['rows'].sort(key=lambda r: (r['date'] or cycle_start), reverse=True)

    return sorted(buckets.values(), key=lambda b: b['site'].lower())
