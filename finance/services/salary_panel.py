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
    ONE per date with amounts summed across every employee/salary
    Transaction for that (site, date), sorted date-descending. A single
    day with 25 employees renders as a single row, not 25.
    """
    from django.db.models import Sum

    salary_qs = (
        Transaction.objects
        .filter(
            admin_id=admin_id,
            type='expense',
            reference__startswith='[AUTO-SAL:',
            date__gte=cycle_start,
            date__lte=cycle_end,
        )
        # Group by (site, date) in the DB so N employees on the same day
        # become one aggregated row. `location_site` is a CharField; the
        # canonical-casing pass below folds spelling variants down to
        # one bucket per site (case-insensitive).
        .values('location_site', 'date')
        .annotate(amount=Sum('amount'))
    )

    # Canonical display casing per site — Projects.Site casing wins.
    canonical = {}   # lower → display
    try:
        from projects.utils import sites_for_admin
        for name in sites_for_admin(admin_id):
            canonical.setdefault(name.strip().lower(), name.strip())
    except Exception:
        pass

    # Bucket: lower_key → {'site': display, 'total': Decimal,
    #                      'rows_by_date': {date: Decimal}}.
    # Row-per-date bucket is a dict here so two spellings of the same
    # site on the same day still collapse to a single row after the
    # case-insensitive fold.
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
            b = {'site': display, 'total': Decimal('0'), 'rows_by_date': {}}
            buckets[key] = b
        amount = row['amount'] or Decimal('0')
        b['total'] += amount
        d = row['date']
        b['rows_by_date'][d] = b['rows_by_date'].get(d, Decimal('0')) + amount

    for b in buckets.values():
        rows = [
            {'date': d, 'amount': amt}
            for d, amt in b['rows_by_date'].items()
        ]
        rows.sort(key=lambda r: (r['date'] or cycle_start), reverse=True)
        b['rows'] = rows
        del b['rows_by_date']

    return sorted(buckets.values(), key=lambda b: b['site'].lower())
