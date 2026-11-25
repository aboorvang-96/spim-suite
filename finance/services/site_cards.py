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


# ─────────────────────────────────────────────────────────────────────────
# Shared site list / "(No Site)" bucket / site-card figures.
#
# ONE place that defines:
#   * how a raw location_site value maps to a card key (site_key) — NULL,
#     '', whitespace, the literal "(No Site)" and the selector sentinel
#     NO_SITE_VALUE all collapse to the same '' key, so a null site and a
#     "No Site" value can never render as two cards;
#   * the selector list every module offers (site_choices), which always
#     ends with the virtual "(No Site)" option — no DB row is created;
#   * the single create path for a site typed in Income or Expense
#     (ensure_site), which registers it in projects.Site (what the cards,
#     Attendance and Projects read) AND branches.LocationSite (what the
#     legacy Salary / Employee dropdowns read);
#   * the per-site Credit / Debit figures for a 26→25 cycle that BOTH the
#     Income and Expense site cards render (build_site_cards).
# ─────────────────────────────────────────────────────────────────────────

NO_SITE_LABEL = '(No Site)'
NO_SITE_VALUE = '__NO_SITE__'
_NO_SITE_ALIASES = {'', '(no site)', NO_SITE_VALUE.lower()}
AUTO_SAL_PREFIX = '[AUTO-SAL:'
DEFAULT_SITE_CLIENT = 'GENERAL'


def site_key(raw):
    """Card/grouping key for a raw site value. '' means "(No Site)"."""
    s = (raw or '').strip()
    return '' if s.lower() in _NO_SITE_ALIASES else s.lower()


def is_no_site(raw):
    return site_key(raw) == ''


def site_choices(admin_id, include_no_site=True):
    """Shared selector list for Income / Expense / Attendance / Salary /
    Projects: canonical site names (projects.Site active ∪ recent
    attendance sites, via sites_for_admin) ∪ branches.LocationSite names,
    then the virtual "(No Site)" option last.
    Returns list[{'value': str, 'label': str}]."""
    from projects.utils import sites_for_admin
    names = {}
    try:
        for n in sites_for_admin(admin_id):
            names.setdefault(n.strip().lower(), n.strip())
    except Exception:
        pass
    try:
        from branches.models import LocationSite
        for n in LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True):
            n = (n or '').strip()
            if n and not is_no_site(n):
                names.setdefault(n.lower(), n)
    except Exception:
        pass
    out = [{'value': n, 'label': n}
           for n in sorted(names.values(), key=lambda s: s.lower())]
    if include_no_site:
        out.append({'value': NO_SITE_VALUE, 'label': NO_SITE_LABEL})
    return out


def site_choice_names(admin_id, extra=()):
    """Flat name list for string-valued selectors (Salary filter, Projects
    datalist): shared site names ∪ `extra` (module-local values), with
    "(No Site)" last. Selecting "(No Site)" is understood by site_filter_q."""
    names = {}
    for c in site_choices(admin_id, include_no_site=False):
        names.setdefault(c['value'].lower(), c['value'])
    for n in extra or ():
        n = (n or '').strip()
        if n and not is_no_site(n):
            names.setdefault(n.lower(), n)
    return sorted(names.values(), key=lambda s: s.lower()) + [NO_SITE_LABEL]


def site_filter_q(field, value, contains=False):
    """Q for filtering a site CharField by a selector value. "(No Site)" /
    NO_SITE_VALUE match NULL or blank — the same rows the shared
    "(No Site)" card holds. Returns None when value is empty (no filter)."""
    from django.db.models import Q
    raw = (value or '').strip()
    if not raw:
        return None
    if is_no_site(raw):
        return (Q(**{f'{field}__isnull': True}) | Q(**{field: ''})
                | Q(**{f'{field}__iexact': NO_SITE_LABEL}))
    lookup = 'icontains' if contains else 'exact'
    return Q(**{f'{field}__{lookup}': raw})


def ensure_site(admin_id, raw, user=None):
    """THE create path for a site typed in Income or Expense.

    Returns the value to store in location_site:
      * '' for blank / "(No Site)" / NO_SITE_VALUE (the No Site bucket —
        no record is created);
      * otherwise the canonical projects.Site name, creating the Site
        (under the tenant's GENERAL client) and the LocationSite registry
        row if missing. Idempotent and case-insensitive.
    Never raises: on any failure the trimmed name is returned unchanged
    so the money row still saves.
    """
    if is_no_site(raw):
        return ''
    name = (raw or '').strip()[:150]
    if not admin_id:
        return name
    from django.db import transaction
    try:
        with transaction.atomic():
            from projects.models import ProjectClient, Site
            site = Site.objects.filter(admin_id=admin_id, name__iexact=name).first()
            if site is None:
                client, _ = ProjectClient.objects.get_or_create(
                    admin_id=admin_id, name=DEFAULT_SITE_CLIENT,
                    defaults={'is_active': True},
                )
                site = Site.objects.create(
                    admin_id=admin_id, name=name, client=client, is_active=True,
                )
            name = site.name
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "ensure_site: projects.Site create failed admin=%s name=%r", admin_id, name)
    try:
        with transaction.atomic():
            from branches.models import LocationSite
            if not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
                LocationSite.objects.create(admin_id=admin_id, name=name, created_by=user)
    except Exception:
        pass
    return name


def _cycle_options(cycle_keys):
    """[{'key': 'YYYY-MM', 'label': '26 Oct → 25 Nov 2026'}] most recent first."""
    import datetime as _dt
    from accounts.cycle_utils import get_salary_cycle
    from finance.views import _cycle_label
    opts = []
    for m in sorted(cycle_keys, reverse=True):
        try:
            y, mo = m.split('-')
            c = get_salary_cycle(_dt.date(int(y), int(mo), 25))
            label = _cycle_label(c['start'], c['end'])
        except Exception:
            label = m
        opts.append({'key': m, 'label': label})
    return opts


def build_site_ledger(admin_id, cycle_start, cycle_end):
    """Per-site Credit / Debit for the Income + Expense site cards.

    Active cycle [cycle_start, cycle_end] (the figures shown on the card):
      credit = every Income row dated in the cycle (same rows the Income
               "Total Credits" KPI sums);
      debit  = non-salary expense Transactions in the cycle
               + attendance-based salary per working site
                 (employees.views.compute_cycle_salary_by_site, which
                 sum-matches compute_cycle_salary_total).
    So Σ card debits == the "Total Debits" / "Total Expenses" KPI.

    Other cycles (card dropdown history): Income rows + every expense
    Transaction including [AUTO-SAL:*] salary rows, bucketed by 26→25
    cycle.

    Returns {'credit', 'debit', 'display', 'latest', 'by_cycle',
    'active_key'} — all keyed by site_key().
    """
    from collections import defaultdict
    from decimal import Decimal as D
    from accounts.cycle_utils import get_salary_cycle

    credit = defaultdict(lambda: D('0'))
    debit = defaultdict(lambda: D('0'))
    display, latest = {}, {}
    by_cycle = defaultdict(lambda: defaultdict(lambda: {'credit': D('0'), 'debit': D('0')}))
    _ck_cache = {}

    def _ck(d):
        k = _ck_cache.get(d)
        if k is None:
            k = _ck_cache[d] = get_salary_cycle(d)['month_key']
        return k

    def _seen(k, raw, d):
        if k and k not in display:
            display[k] = (raw or '').strip()
        if d and (latest.get(k) is None or d > latest[k]):
            latest[k] = d

    active_key = _ck(cycle_end)

    try:
        from income.models import Income
        for i in Income.objects.filter(admin_id=admin_id).only('amount', 'location_site', 'date'):
            k = site_key(i.location_site)
            amt = i.amount or D('0')
            _seen(k, i.location_site, i.date)
            if i.date:
                by_cycle[k][_ck(i.date)]['credit'] += amt
                if cycle_start <= i.date <= cycle_end:
                    credit[k] += amt
    except Exception:
        pass

    for t in (Transaction.objects.filter(admin_id=admin_id, type='expense')
              .only('amount', 'location_site', 'date', 'reference')):
        k = site_key(t.location_site)
        amt = t.amount or D('0')
        _seen(k, t.location_site, t.date)
        if t.date:
            by_cycle[k][_ck(t.date)]['debit'] += amt
            is_sal = (t.reference or '').startswith(AUTO_SAL_PREFIX)
            if not is_sal and cycle_start <= t.date <= cycle_end:
                debit[k] += amt

    try:
        from employees.views import compute_cycle_salary_by_site
        for raw, rows in compute_cycle_salary_by_site(admin_id, cycle_start, cycle_end).items():
            k = site_key(raw)
            amt = sum((r['amount'] or D('0')) for r in rows)
            if amt:
                debit[k] += amt
                _seen(k, raw, max((r['date'] for r in rows if r.get('date')), default=None))
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "build_site_ledger: salary-by-site failed admin=%s", admin_id)

    # The active cycle always shows the KPI-consistent figures.
    for k in set(by_cycle) | set(credit) | set(debit):
        by_cycle[k][active_key] = {'credit': credit.get(k, D('0')),
                                   'debit': debit.get(k, D('0'))}

    return {
        'credit': dict(credit), 'debit': dict(debit),
        'display': display, 'latest': latest,
        'by_cycle': {k: dict(v) for k, v in by_cycle.items()},
        'active_key': active_key,
    }


def _accent_index(name, palette_len=8):
    n = (name or '').strip().lower()
    return (sum(ord(c) for c in n) % palette_len) if n else 0


def build_site_cards(admin_id, cycle_start, cycle_end, seed_names=None,
                     row_groups=None, restrict_keys=None, show_no_site=False):
    """Site cards for /income/ AND /expenses/ — one card set, one figure rule.

    * Card set = seed sites ∪ every site with non-zero Credit/Debit in the
      cycle. A non-zero site is never dropped, so Σ card figures always
      equals the KPI totals.
    * Blank / "(No Site)" rows form exactly one "(No Site)" card
      (key ''), shown when it has money or rows, or when show_no_site.
    * `row_groups` — the page's own grouped row dicts (each with a
      'site_key' computed via site_key()); their row lists are kept and
      their figures are overwritten with the ledger's.
    * `restrict_keys` — optional set of site_key()s (site filter).
    Returns list[dict] sorted by latest activity (desc).
    """
    import datetime as _dt
    import json as _json
    from decimal import Decimal as D

    ledger = build_site_ledger(admin_id, cycle_start, cycle_end)
    groups = {g['site_key']: g for g in (row_groups or [])}

    seed_disp = {}
    for n in seed_names or []:
        k = site_key(n)
        if k:
            seed_disp.setdefault(k, n.strip())

    # Card set depends ONLY on (seed, cycle figures) — never on which rows a
    # page happened to load — so /income/ and /expenses/ always render the
    # identical card set for the same cycle.
    keys = set(seed_disp)
    keys |= {k for k, v in ledger['credit'].items() if v}
    keys |= {k for k, v in ledger['debit'].items() if v}
    if show_no_site:
        keys.add('')
    if restrict_keys is not None:
        keys &= set(restrict_keys)

    try:
        from projects.utils import client_site_label
    except Exception:
        client_site_label = None

    cards = []
    for k in keys:
        g = groups.get(k) or {
            'count': 0, 'transactions': [], 'income_rows': [], 'card_rows': [],
        }
        if k:
            disp = seed_disp.get(k) or ledger['display'].get(k) or g.get('site') or k
        else:
            disp = NO_SITE_LABEL
        c = ledger['credit'].get(k, D('0'))
        d = ledger['debit'].get(k, D('0'))
        g['site'] = disp
        g['site_key'] = k
        g['credit'] = c
        g['debit'] = d
        g['balance'] = c - d
        g['latest_date'] = ledger['latest'].get(k) or g.get('latest_date')
        label = disp
        if k and client_site_label:
            try:
                label = client_site_label(admin_id, disp) or disp
            except Exception:
                label = disp
        g['label'] = label
        bc = dict(ledger['by_cycle'].get(k, {}))
        bc.setdefault(ledger['active_key'], {'credit': c, 'debit': d})
        g['monthly_json'] = _json.dumps({
            m: {'credit': float(v['credit']), 'debit': float(v['debit']),
                'balance': float(v['credit'] - v['debit'])}
            for m, v in bc.items()
        })
        # "All Cycles" option = sum over every cycle in the dropdown.
        tc = sum((v['credit'] for v in bc.values()), D('0'))
        td = sum((v['debit'] for v in bc.values()), D('0'))
        g['totals_json'] = _json.dumps({
            'credit': float(tc), 'debit': float(td), 'balance': float(tc - td),
        })
        g['month_options'] = _cycle_options(bc.keys())
        g['active_cycle_key'] = ledger['active_key']
        g['color_index'] = _accent_index(disp)
        cards.append(g)

    cards.sort(key=lambda g: (g['latest_date'] or _dt.date.min), reverse=True)
    return cards


def has_unassigned_transactions(admin_id, txn_type=None):
    """True if any Transaction row for this tenant has a null/empty
    location_site. Used to decide whether to render the "(No Site)" bucket
    — we don't want an empty Unassigned card cluttering the UI."""
    from django.db.models import Q
    qs = Transaction.objects.filter(admin_id=admin_id)
    if txn_type:
        qs = qs.filter(type=txn_type)
    return qs.filter(Q(location_site__isnull=True) | Q(location_site='')).exists()
