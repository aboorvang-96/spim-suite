from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Avg, Count
import json
from .models import Income
from .forms import IncomeForm
import csv
from accounts.views import is_admin_user, get_admin_id
from branches.models import LocationSite
from finance.models import Source, Transaction as FinanceTransaction


# Fixed 8-slot accent palette — same colours / ordering as
# finance.views.SITE_ACCENT_PALETTE so the same site renders with the same
# border accent in both the Expense Manager and Income module cards.
SITE_ACCENT_PALETTE = [
    '#2563eb', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16',
]


def _site_color_index(name):
    """Stable 0..7 slot from a site name for the card border accent."""
    n = (name or '').strip().lower()
    if not n:
        return 0
    total = 0
    for ch in n:
        total += ord(ch)
    return total % len(SITE_ACCENT_PALETTE)


def _location_sites_json(user):
    admin_id = get_admin_id(user)
    names = list(LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True))
    return json.dumps(names)


def _shared_sources_json(user):
    admin_id = get_admin_id(user)
    names = list(Source.objects.filter(admin_id=admin_id, type='income').values_list('name', flat=True))
    return json.dumps(names)


def _shared_accounts_json(user):
    admin_id = get_admin_id(user)
    names = list(Source.objects.filter(admin_id=admin_id, type='account').values_list('name', flat=True))
    return json.dumps(names)


def _balance_by_combo(user, is_admin):
    """Return balance per (Income Source, Account) across income and expense records.
    Keys are normalised to lower-case so matching is case-insensitive; the display
    values ('source', 'account') keep the original casing from the income record."""
    admin_id = get_admin_id(user)
    if is_admin:
        income_qs  = Income.objects.filter(admin_id=admin_id)
        expense_qs = FinanceTransaction.objects.filter(admin_id=admin_id, type='expense')
    else:
        income_qs  = Income.objects.filter(user=user)
        expense_qs = FinanceTransaction.objects.filter(user=user, type='expense')

    combo_map = {}
    for i in income_qs:
        source  = (i.payment_by or '').strip()
        account = (i.payment_mode or '').strip()
        if source and account:
            k = f"{source.lower()}|||{account.lower()}"
            if k not in combo_map:
                combo_map[k] = {'source': source, 'account': account, 'income': 0, 'expense': 0}
            combo_map[k]['income'] += float(i.amount)

    for e in expense_qs:
        source  = (e.income_source or '').strip()
        account = (e.payment_mode or '').strip()
        if source and account:
            k = f"{source.lower()}|||{account.lower()}"
            if k not in combo_map:
                combo_map[k] = {'source': source, 'account': account, 'income': 0, 'expense': 0}
            combo_map[k]['expense'] += float(e.amount)

    result = []
    for v in combo_map.values():
        v['balance'] = v['income'] - v['expense']
        result.append(v)
    return sorted(result, key=lambda x: (-abs(x['balance']), x['source']))


@login_required
def shared_sources_api(request):
    """GET/POST income sources for the centralized shared registry."""
    admin_id = get_admin_id(request.user)

    if request.method == 'GET':
        names = list(Source.objects.filter(admin_id=admin_id, type='income').values_list('name', flat=True))
        return JsonResponse({'sources': names})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = (data.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            if not Source.objects.filter(admin_id=admin_id, name__iexact=name, type='income').exists():
                Source.objects.create(admin_id=admin_id, name=name, type='income', created_by=request.user)
            names = list(Source.objects.filter(admin_id=admin_id, type='income').values_list('name', flat=True))
            return JsonResponse({'success': True, 'sources': names})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def shared_accounts_api(request):
    """GET/POST shared accounts for the centralized shared registry."""
    admin_id = get_admin_id(request.user)

    if request.method == 'GET':
        names = list(Source.objects.filter(admin_id=admin_id, type='account').values_list('name', flat=True))
        return JsonResponse({'accounts': names})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = (data.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            if not Source.objects.filter(admin_id=admin_id, name__iexact=name, type='account').exists():
                Source.objects.create(admin_id=admin_id, name=name, type='account', created_by=request.user)
            names = list(Source.objects.filter(admin_id=admin_id, type='account').values_list('name', flat=True))
            return JsonResponse({'success': True, 'accounts': names})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def income_list(request):
    admin_id = get_admin_id(request.user)
    if is_admin_user(request.user):
        incomes = Income.objects.filter(admin_id=admin_id).select_related('category', 'user')
    else:
        incomes = Income.objects.filter(user=request.user).select_related('category')
    # Regular income view NEVER shows salary-income rows. Those are
    # segregated into the Salary Income side panel further down.
    try:
        incomes = incomes.filter(is_salary=False)
    except Exception:
        # Migration 0006 not yet applied — defer to the defensive fetch
        # branch below, which will still filter after load.
        pass
        
    # Filters — parity with Expense Manager. Multi-value site/category/
    # account/income_source read via getlist so ?site=A&site=B applies
    # OR-within-field. from_date / to_date range takes precedence over
    # month (mutually exclusive) and over date_from/date_to (legacy names
    # kept for back-compat).
    from finance.views import _clean_multi, _parse_iso_date
    cat_ids        = _clean_multi(request, 'category')
    accounts       = _clean_multi(request, 'account')
    income_sources = _clean_multi(request, 'income_source')
    sites          = _clean_multi(request, 'site')

    month      = (request.GET.get('month') or '').strip()
    search     = (request.GET.get('search') or '').strip()
    amount_min = (request.GET.get('amount_min') or '').strip()
    amount_max = (request.GET.get('amount_max') or '').strip()
    from_date  = _parse_iso_date(request.GET.get('from_date') or request.GET.get('date_from'))
    to_date    = _parse_iso_date(request.GET.get('to_date')   or request.GET.get('date_to'))

    if from_date or to_date:
        month = ''

    date_range_error = ''
    if from_date and to_date and to_date < from_date:
        date_range_error = 'To date is before From date — date range ignored.'
        from_date = None
        to_date = None

    if cat_ids:
        incomes = incomes.filter(category_id__in=cat_ids)

    if from_date or to_date:
        if from_date: incomes = incomes.filter(date__gte=from_date)
        if to_date:   incomes = incomes.filter(date__lte=to_date)
    elif month:
        incomes = incomes.filter(date__startswith=month)

    if search:     incomes = incomes.filter(
        Q(title__icontains=search) | Q(source__icontains=search) | Q(description__icontains=search)
    )
    if amount_min: incomes = incomes.filter(amount__gte=amount_min)
    if amount_max: incomes = incomes.filter(amount__lte=amount_max)

    if accounts:
        aq = Q()
        for a in accounts:
            aq |= Q(payment_mode__iexact=a)
        incomes = incomes.filter(aq)

    if income_sources:
        sq = Q()
        for s in income_sources:
            sq |= Q(payment_by__iexact=s)
        incomes = incomes.filter(sq)

    if sites:
        sq = Q()
        for s in sites:
            if s == 'UNASSIGNED':
                sq |= Q(location_site__isnull=True) | Q(location_site='')
            else:
                sq |= Q(location_site__iexact=s)
        incomes = incomes.filter(sq)

    from categories.models import IncomeCategory
    categories = IncomeCategory.objects.filter(created_by__admin_id=get_admin_id(request.user))

    # Defensive fetch: if migration 0005 (from_account / to_account /
    # remarks) hasn't been applied on this DB yet, the default `list(incomes)`
    # would 500 because the SELECT includes columns that don't exist.
    # Falling back to a deferred fetch + stubbed values in __dict__ prevents
    # the template from triggering lazy loads that would also fail.
    _NEW_INCOME_FIELDS = ('from_account', 'to_account', 'remarks')
    try:
        incomes_list = list(incomes)
    except Exception:
        incomes_list = list(incomes.defer(*_NEW_INCOME_FIELDS))
        for _i in incomes_list:
            for _f in _NEW_INCOME_FIELDS:
                _i.__dict__[_f] = ''
    total = sum(i.amount for i in incomes_list)
    count = len(incomes_list)
    average = total / count if count else 0

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = [{
            'id': i.id,
            'title': i.title,
            'amount': str(i.amount),
            'category': i.category.name if i.category else 'Uncategorized',
            'user': i.user.username if is_admin_user(request.user) else None,
            'date': str(i.date),
            'source': i.source,
            'payment_mode': i.get_payment_mode_display(),
        } for i in incomes_list]
        return JsonResponse({'incomes': data, 'total': str(total)})

    is_admin = is_admin_user(request.user)
    balance_combos = _balance_by_combo(request.user, is_admin)
    # Keyed by lower-case (source, account) so lookup is case-insensitive.
    combo_map = {(c['source'].lower(), c['account'].lower()): c for c in balance_combos}

    for i in incomes_list:
        src = (i.payment_by or '').strip().lower()
        acc = (i.payment_mode or '').strip().lower()
        i.combo_data = combo_map.get((src, acc)) if (src and acc) else None

    # Group the filtered incomes by Account for the legacy view (kept so
    # existing template code paths keep working). The NEW site-based card
    # view (Income/Expense restructure) is `sites_grouped` — one card per
    # location_site, with cross-module credit/debit/balance figures.
    # Shared site-name seed so Income cards match Expense: sites from
    # Projects/Attendance appear even with zero income rows. Site cards on
    # Income don't have a today-restriction — Income is a manual entry flow
    # and admins expect to see the full site universe.
    # Seed identical to /expenses/: single-source helper get_expense_card_seed.
    # Same admin, same cycle bounds → identical card set (names + order).
    # Any divergence between the two pages is a bug in the shared helper.
    from finance.services.site_cards import get_expense_card_seed, has_unassigned_transactions
    from accounts.cycle_utils import get_salary_cycle
    from accounts.date_utils import today_ist
    from django.utils import timezone as _tz_seed
    _cycle = get_salary_cycle(today_ist())
    seed_site_names = get_expense_card_seed(
        admin_id,
        selected_sites=[s for s in sites if s != 'UNASSIGNED'],
        restrict_today=False,
        today=_tz_seed.localdate(),
        cycle_start=_cycle['start'],
        cycle_end=_cycle['end'],
    )

    accounts_grouped = _group_incomes_by_account(incomes_list)
    sites_grouped    = _group_incomes_by_site(incomes_list, request.user, seed_names=seed_site_names)

    # Drop the (No Site) bucket unless a legacy row without location_site exists.
    if not (has_unassigned_transactions(admin_id) or any(
        not (getattr(i, 'location_site', None) or '').strip() for i in incomes_list
    )):
        sites_grouped = [g for g in sites_grouped if g['site_key']]

    # Salary Income side panel — mirrors the expense-side salary panel.
    # Rows are Income.objects with is_salary=True in the current salary
    # cycle. Each row shows the expense-side salary total for that site
    # in the same cycle (read-only Total Amount column).
    salary_panel_rows, salary_cycle = _build_salary_income_panel(
        request.user, admin_id, seed_site_names,
    )

    # Cycle-scoped KPI tiles (Total Credits / Total Debits / Net Balance).
    # Both queries are tenant-scoped by admin_id and windowed to the
    # current salary cycle. Credits sum EVERY Income row in the cycle
    # (is_salary True + False). Debits sum every expense Transaction in
    # the cycle regardless of reference shape (salary + standard).
    from decimal import Decimal as _KD
    from django.db.models import Sum as _KSum
    _cycle_credits = (
        Income.objects
        .filter(admin_id=admin_id, date__gte=salary_cycle['start'], date__lte=salary_cycle['end'])
        .aggregate(s=_KSum('amount'))['s'] or _KD('0')
    )
    _cycle_debits = (
        FinanceTransaction.objects
        .filter(admin_id=admin_id, type='expense',
                date__gte=salary_cycle['start'], date__lte=salary_cycle['end'])
        .aggregate(s=_KSum('amount'))['s'] or _KD('0')
    )
    _cycle_net = _cycle_credits - _cycle_debits
    _cycle_range_label = '{} - {} {}'.format(
        salary_cycle['start'].strftime('%d %b'),
        salary_cycle['end'].strftime('%d %b'),
        salary_cycle['end'].strftime('%Y'),
    )

    from django.utils import timezone as _tz
    return render(request, 'income/list.html', {
        'incomes':          incomes_list,
        'accounts_grouped': accounts_grouped,
        'sites_grouped':    sites_grouped,
        'categories':       categories,
        'current_month':    _tz.now().strftime('%Y-%m'),
        'total':            total,
        'count':            count,
        'average':          average,
        'total_balance':    sum(c['balance'] for c in balance_combos),
        'filters': {
            # Multi-value.
            'categories':     cat_ids,
            'accounts':       accounts,
            'income_sources': income_sources,
            'sites':          sites,
            # Scalars.
            'search':      search,
            'amount_min':  amount_min,
            'amount_max':  amount_max,
            'month':       month,
            'from_date':   from_date.isoformat() if from_date else '',
            'to_date':     to_date.isoformat() if to_date else '',
            'date_range_error': date_range_error,
            # Legacy scalar aliases — templates in the wild may still read
            # filters.category / filters.account / filters.income_source /
            # filters.date_from / filters.date_to. First selected value if any.
            'category':      cat_ids[0] if cat_ids else '',
            'account':       accounts[0] if accounts else '',
            'income_source': income_sources[0] if income_sources else '',
            'date_from':     from_date.isoformat() if from_date else '',
            'date_to':       to_date.isoformat() if to_date else '',
        },
        'is_admin':            is_admin,
        'location_sites_json': _location_sites_json(request.user),
        'income_sources_json': _shared_sources_json(request.user),
        'accounts_json':       _shared_accounts_json(request.user),
        'balance_data':        balance_combos,
        'salary_panel_rows':   salary_panel_rows,
        'salary_sites_json':   json.dumps(sorted(list(seed_site_names)) if seed_site_names else []),
        'salary_cycle_label':  salary_cycle['label'],
        'salary_cycle_start':  salary_cycle['start'],
        'salary_cycle_end':    salary_cycle['end'],
        'cycle_credits':       _cycle_credits,
        'cycle_debits':        _cycle_debits,
        'cycle_net':           _cycle_net,
        'cycle_range_label':   _cycle_range_label,
    })


def _salary_cycle_expense_totals(admin_id, cycle):
    """{site_lower: {'display': str, 'total': Decimal}} — expense-side
    salary sums per site for the given cycle. Same query pattern as
    finance.services.salary_panel.build_salary_panel; keeps this the
    single source of truth for the seed set."""
    from decimal import Decimal as _D
    from django.db.models import Sum
    out = {}
    try:
        rows = (
            FinanceTransaction.objects
            .filter(
                admin_id=admin_id,
                type='expense',
                reference__startswith='[AUTO-SAL:',
                date__gte=cycle['start'],
                date__lte=cycle['end'],
            )
            .values('location_site')
            .annotate(total=Sum('amount'))
        )
        for r in rows:
            raw = (r['location_site'] or '').strip()
            if not raw:
                continue
            k = raw.lower()
            b = out.get(k)
            if b is None:
                out[k] = {'display': raw, 'total': (r['total'] or _D('0'))}
            else:
                b['total'] += (r['total'] or _D('0'))
    except Exception:
        pass
    # Fold display names to canonical Projects.Site casing when available.
    try:
        from projects.utils import sites_for_admin
        for name in sites_for_admin(admin_id):
            k = (name or '').strip().lower()
            if k in out:
                out[k]['display'] = (name or '').strip()
    except Exception:
        pass
    return out


def _build_salary_income_panel(user, admin_id, seed_site_names):
    """Return (rows, cycle_dict) for the Salary Income side panel.

    NEW SHAPE: one row per site that has ANY expense-side salary this
    cycle. Sites with zero salary expense are omitted. The Income row
    for that site is upserted 1:1 with the seeded panel row — either it
    exists (edit-mode) or it doesn't (blank credit fields, id=None).
    """
    from decimal import Decimal as _D
    from accounts.cycle_utils import get_salary_cycle
    from accounts.date_utils import today_ist
    cycle = get_salary_cycle(today_ist())

    exp_totals = _salary_cycle_expense_totals(admin_id, cycle)

    # Existing Income salary rows for this cycle, keyed by site (lower).
    # Should be at most one per site under the upsert rule; if legacy
    # duplicates exist, we pick the most recent and ignore the rest so
    # the panel still renders one row per site.
    existing = {}
    try:
        if is_admin_user(user):
            qs = Income.objects.filter(
                admin_id=admin_id, is_salary=True,
                date__gte=cycle['start'], date__lte=cycle['end'],
            )
        else:
            qs = Income.objects.filter(
                user=user, is_salary=True,
                date__gte=cycle['start'], date__lte=cycle['end'],
            )
        for i in qs.order_by('-date', '-created_at'):
            k = (i.location_site or '').strip().lower()
            if k and k not in existing:
                existing[k] = i
    except Exception:
        existing = {}

    rows_out = []
    for key, bucket in exp_totals.items():
        salary = bucket['total'] or _D('0')
        inc = existing.get(key)
        credit = (inc.amount if inc else _D('0')) or _D('0')
        rows_out.append({
            'id':           inc.pk if inc else None,
            'site':         bucket['display'],
            'from_account': (inc.from_account or '') if inc else '',
            'credit':       credit,
            'salary':       salary,
            'balance':      credit - salary,
            'remarks':      (inc.remarks or '') if inc else '',
        })
    rows_out.sort(key=lambda r: (r['site'] or '').lower())
    return rows_out, cycle


@login_required
def income_export_csv(request):
    """Export income entries to CSV — mirrors reference file's exportIncomeExcel()"""
    if is_admin_user(request.user):
        incomes = Income.objects.filter(admin_id=get_admin_id(request.user)).select_related('category', 'user')
    else:
        incomes = Income.objects.filter(user=request.user).select_related('category')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="income-export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Title', 'Source', 'Category', 'Amount', 'Payment Mode', 'Description'])
    for i in incomes:
        writer.writerow([
            i.date, i.title, i.source or '',
            i.category.name if i.category else 'Uncategorized',
            i.amount, i.get_payment_mode_display(),
            i.description or '',
        ])
    return response


def _is_ajax(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def _normalize_site_or_office(admin_id, raw, user=None):
    """Reject orphan sites on the write path.

    Inline row writes always POST location_site from the card they were
    added under, but a crafted request could try to smuggle in an
    arbitrary site name. If the value isn't in the canonical set
    (sites_for_admin), fold it to "OFFICE" — matching the presentation-
    layer OFFICE fold in _group_incomes_by_site and the rewrite_income_sites
    backfill. Guarantees no new orphan Income rows leak past the API.
    """
    from projects.utils import sites_for_admin
    from attendance.site_utils import get_or_create_office_site, OFFICE_SITE_NAME
    value = (raw or '').strip()
    if not value:
        try:
            get_or_create_office_site(admin_id, user)
        except Exception:
            pass
        return OFFICE_SITE_NAME
    canonical = {s.lower(): s for s in sites_for_admin(admin_id)}
    hit = canonical.get(value.lower())
    if hit is not None:
        return hit
    try:
        get_or_create_office_site(admin_id, user)
    except Exception:
        pass
    return OFFICE_SITE_NAME


@login_required
def income_autocomplete_api(request):
    """Autocomplete for the inline row's From / To Account inputs.

    GET /income/api/autocomplete/?field=from_account|to_account&q=<prefix>
    Returns {'suggestions': [{'value': str, 'count': int}, ...]} ordered
    by usage count desc. Admin-scoped, case-insensitive dedup. No new
    model — just DISTINCT + COUNT over Income.
    """
    field = (request.GET.get('field') or '').strip()
    if field not in ('from_account', 'to_account'):
        return JsonResponse({'error': 'field must be from_account or to_account'}, status=400)
    q = (request.GET.get('q') or '').strip()
    admin_id = get_admin_id(request.user)

    qs = Income.objects.filter(admin_id=admin_id).exclude(**{f'{field}__exact': ''})
    if q:
        qs = qs.filter(**{f'{field}__icontains': q})

    # DISTINCT + COUNT via values+annotate. Values case-fold client-side
    # so "Bank A" and "bank a" collapse — keep the first-seen casing.
    counts = {}
    order = []
    for row in qs.values(field).annotate(n=Count('id')).order_by('-n')[:100]:
        raw = (row[field] or '').strip()
        if not raw:
            continue
        k = raw.lower()
        if k in counts:
            counts[k]['count'] += row['n']
        else:
            counts[k] = {'value': raw, 'count': row['n']}
            order.append(k)
    result = [counts[k] for k in order][:20]
    return JsonResponse({'suggestions': result})


def _group_incomes_by_account(qs):
    """
    Group an already-filtered Income queryset by `payment_mode` (the
    column that holds the Account name). Mirrors the expense-side helper
    in finance.views — see that docstring for full semantics.
    """
    import datetime as _dt
    from decimal import Decimal as _D
    groups = {}
    for i in qs:
        acc = (getattr(i, 'payment_mode', None) or '').strip()
        key = acc.lower()
        g = groups.get(key)
        if g is None:
            g = {
                'account':      acc or '(No Account)',
                'account_key':  key,
                'total':        _D('0'),
                'count':        0,
                'latest_date':  i.date,
                'transactions': [],
            }
            groups[key] = g
        g['total'] += i.amount
        g['count'] += 1
        g['transactions'].append(i)
        if i.date and (g['latest_date'] is None or i.date > g['latest_date']):
            g['latest_date'] = i.date
            g['account'] = acc or '(No Account)'
    for g in groups.values():
        g['transactions'].sort(
            key=lambda x: (x.date or _dt.date.min),
            reverse=True,
        )
    return sorted(
        groups.values(),
        key=lambda g: (g['latest_date'] or _dt.date.min),
        reverse=True,
    )


def _group_incomes_by_site(incomes, user, seed_names=None):
    """
    Site-based card view (Income/Expense restructure).

    Groups incomes by `location_site` (case-insensitive). For each site
    returns a dict with credit (sum of Income amounts for that site),
    debit (sum of expense Transaction amounts for the SAME site), and
    balance = credit - debit. The expense lookup is scoped to the same
    admin_id (tenant) so cross-tenant data never bleeds in.

    Sort order: most recent activity first (latest income date).

    Also builds the per-site monthly breakdown (credit/debit/balance keyed
    by 'YYYY-MM') and a `month_options` list for the card-level month
    dropdown (Issue 5 — replace the static latest_date span).
    """
    import datetime as _dt
    from decimal import Decimal as _D
    from accounts.views import get_admin_id, is_admin_user
    admin_id = get_admin_id(user)

    # Build the site → debit map (overall + per-month) in a single sweep
    # over expense Transactions for this tenant. Empty/None location_site
    # rows are folded into the "(No Site)" bucket so admins can still see
    # them.
    #
    # Defensive: the cross-module expense query is wrapped in try/except so
    # a transient Transaction-side failure (e.g. mid-deploy when one
    # migration has run and the other hasn't) degrades to an empty debit
    # map instead of 500-ing the Income page. `.only(...)` skips the new
    # `expense_category` column entirely so the SELECT works even if the
    # column hasn't been added yet on the Transaction table.
    debit_map = {}
    debit_by_month = {}
    expense_qs = None
    try:
        if is_admin_user(user):
            expense_qs = FinanceTransaction.objects.filter(admin_id=admin_id, type='expense')
        else:
            expense_qs = FinanceTransaction.objects.filter(user=user, type='expense')
        expense_qs = expense_qs.only('amount', 'location_site', 'date')
        for e in expense_qs:
            site = (e.location_site or '').strip()
            key  = site.lower()
            debit_map[key] = debit_map.get(key, _D('0')) + (e.amount or _D('0'))
            if e.date:
                mkey = e.date.strftime('%Y-%m')
                dm = debit_by_month.setdefault(key, {})
                dm[mkey] = dm.get(mkey, _D('0')) + (e.amount or _D('0'))
    except Exception:
        debit_map = {}
        debit_by_month = {}
        expense_qs = None

    groups = {}
    credit_by_month = {}

    # Seed with the canonical site list from Projects/Attendance so sites
    # with zero incomes still render as editable zero-row cards. Projects.Site
    # casing wins for display.
    seeded_keys = set()
    if seed_names:
        for n in seed_names:
            key = (n or '').strip().lower()
            if not key or key in groups:
                continue
            seeded_keys.add(key)
            groups[key] = {
                'site':         n,
                'site_key':     key,
                'credit':       _D('0'),
                'debit':        debit_map.get(key, _D('0')),
                'balance':      _D('0'),
                'count':        0,
                'latest_date':  None,
                'transactions': [],
            }

    # OFFICE is the roll-up bucket for any Income/Expense row whose
    # location_site isn't in the canonical seed set (orphan sites created
    # via the free-form form, or by legacy imports). The rewrite_income_sites
    # backfill actually mutates these rows to location_site="OFFICE"; this
    # presentation-layer fold makes the page correct even before the
    # backfill runs.
    OFFICE_KEY = 'office'

    def _office_group():
        g = groups.get(OFFICE_KEY)
        if g is None:
            g = {
                'site':         'OFFICE',
                'site_key':     OFFICE_KEY,
                'credit':       _D('0'),
                'debit':        debit_map.get(OFFICE_KEY, _D('0')),
                'balance':      _D('0'),
                'count':        0,
                'latest_date':  None,
                'transactions': [],
            }
            groups[OFFICE_KEY] = g
            seeded_keys.add(OFFICE_KEY)
        return g

    for i in incomes:
        site = (getattr(i, 'location_site', None) or '').strip()
        key  = site.lower()
        g = groups.get(key)
        if g is None:
            # Orphan (or blank): fold into OFFICE instead of minting a
            # standalone card. Preserves totals; hides orphan site names.
            g = _office_group()
            key = OFFICE_KEY
        g['credit'] += (i.amount or _D('0'))
        g['count']  += 1
        g['transactions'].append(i)
        if i.date:
            mkey = i.date.strftime('%Y-%m')
            cm = credit_by_month.setdefault(key, {})
            cm[mkey] = cm.get(mkey, _D('0')) + (i.amount or _D('0'))
        if i.date and (g['latest_date'] is None or i.date > g['latest_date']):
            g['latest_date'] = i.date

    # Also surface sites that have expenses but zero income — admin still
    # needs to see those in the site card list. Orphan expense sites (not
    # in the seed set) roll up under OFFICE too so the Income card grid
    # matches the canonical set.
    for key, debit in debit_map.items():
        if key in groups:
            continue
        if key not in seeded_keys:
            og = _office_group()
            og['debit'] = og.get('debit', _D('0')) + debit
            dm = debit_by_month.get(key, {})
            if dm:
                merged = debit_by_month.setdefault(OFFICE_KEY, {})
                for mk, mv in dm.items():
                    merged[mk] = merged.get(mk, _D('0')) + mv
            continue
        # Re-derive a display name from the most recent expense row of this site
        site_disp = ''
        latest = None
        if expense_qs is not None:
            try:
                latest = expense_qs.filter(location_site__iexact=key).order_by('-date').first()
            except Exception:
                latest = None
        if latest:
            site_disp = (latest.location_site or '').strip() or '(No Site)'
        groups[key] = {
            'site':         site_disp or '(No Site)',
            'site_key':     key,
            'credit':       _D('0'),
            'debit':        debit,
            'balance':      _D('0'),
            'count':        0,
            'latest_date':  latest.date if latest else None,
            'transactions': [],
        }

    today = _dt.date.today()
    current_month = today.strftime('%Y-%m')
    month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    for g in groups.values():
        g['balance'] = g['credit'] - g['debit']
        g['transactions'].sort(
            key=lambda x: (x.date or _dt.date.min),
            reverse=True,
        )
        # Per-site monthly breakdown — fed to the card via data-monthly so
        # the card's month dropdown can repaint the Credit/Debit/Balance
        # tiles without a round-trip.
        ck = g['site_key']
        cm = credit_by_month.get(ck, {})
        dm = debit_by_month.get(ck, {})
        all_months = set(cm.keys()) | set(dm.keys())
        all_months.add(current_month)
        monthly = {}
        for m in all_months:
            c = cm.get(m, _D('0'))
            d = dm.get(m, _D('0'))
            monthly[m] = {
                'credit':  float(c),
                'debit':   float(d),
                'balance': float(c - d),
            }
        g['monthly_json'] = json.dumps(monthly)
        g['totals_json']  = json.dumps({
            'credit':  float(g['credit']),
            'debit':   float(g['debit']),
            'balance': float(g['balance']),
        })
        opts = []
        for m in sorted(all_months, reverse=True):
            try:
                y, mo = m.split('-')
                label = '{} {}'.format(month_names[int(mo) - 1], y)
            except Exception:
                label = m
            opts.append({'key': m, 'label': label})
        g['month_options'] = opts
        # Per-site accent for the card border (Issue 4 — color palette).
        g['color_index'] = _site_color_index(g['site'])

    return sorted(
        groups.values(),
        key=lambda g: (g['latest_date'] or _dt.date.min),
        reverse=True,
    )


def _ensure_location_site(admin_id, name, created_by):
    """
    Idempotently register a location_site under the given tenant. Called
    whenever an Income row is saved with a non-blank location_site so
    the SPIM Suite LocationSite registry stays in sync — mirrors the
    behavior originally inlined in income_add / income_edit, and is
    reused by the SPIM Lite HR mobile endpoints so both paths behave
    identically. No return value; failure is silent by design (matches
    the original inline behavior).
    """
    if not admin_id:
        return
    name = (name or '').strip()
    if not name:
        return
    if LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
        return
    LocationSite.objects.create(admin_id=admin_id, name=name, created_by=created_by)


def _income_to_dict(i):
    return {
        'id': i.pk,
        'date': i.date.isoformat() if i.date else '',
        'date_display': i.date.strftime('%d %b, %Y') if i.date else '',
        'amount': str(i.amount),
        'amount_display': '{:,.2f}'.format(float(i.amount)),
        'income_type': i.income_type or '',
        'location': i.location_site or '',
        'payment_by': i.payment_by or '',
        'payment_mode': i.payment_mode or '',
        'description': i.description or '',
        # New site-detail fields (Income/Expense restructure).
        'from_account': getattr(i, 'from_account', '') or '',
        'to_account':   getattr(i, 'to_account',   '') or '',
        'remarks':      getattr(i, 'remarks',      '') or '',
        'is_salary':    bool(getattr(i, 'is_salary', False)),
        'edit_url': f'/income/{i.pk}/edit/',
        'delete_url': f'/income/{i.pk}/delete/',
    }


def _income_combo_data(income, user, is_admin):
    """Return the combo balance dict for this income's (source, account) pair.
    Comparison is case-insensitive to match the normalised _balance_by_combo keys."""
    src = (income.payment_by or '').strip().lower()
    acc = (income.payment_mode or '').strip().lower()
    if not (src and acc):
        return None
    for c in _balance_by_combo(user, is_admin):
        if c['source'].lower() == src and c['account'].lower() == acc:
            return c
    return None


@login_required
def income_add(request):
    # Modal-only flow: any GET hit on /income/add/ bounces to the list.
    if request.method != 'POST':
        return redirect('income:list')

    ajax = _is_ajax(request)
    admin_id = get_admin_id(request.user)

    # Salary Income upsert path — the panel POSTs is_salary=1 with a site
    # that MUST be in this cycle's expense-side salary set. If an existing
    # Income row for (admin_id, site, is_salary=True, date in cycle) is
    # found, we UPDATE it instead of creating a new row.
    if _parse_is_salary(request.POST):
        return _salary_income_upsert(request, admin_id, ajax)

    form = IncomeForm(request.user, request.POST)

    if form.is_valid():
        income = form.save(commit=False)
        income.user     = request.user
        income.admin_id = admin_id
        income.is_salary = False
        income.location_site = _normalize_site_or_office(
            income.admin_id, income.location_site, request.user,
        )
        income.save()
        _ensure_location_site(
            get_admin_id(request.user),
            income.location_site,
            request.user,
        )
        if ajax:
            d = _income_to_dict(income)
            d['combo'] = _income_combo_data(income, request.user, is_admin_user(request.user))
            return JsonResponse({'success': True, 'income': d})
        messages.success(request, f'Income "{income.title}" added successfully.')
        return redirect('income:list')

    if ajax:
        errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
        first_error = next(iter(errors.values()), ['Invalid data.'])[0]
        return JsonResponse({'success': False, 'errors': errors, 'message': first_error}, status=400)

    messages.error(request, 'Could not save income. Please try again.')
    return redirect('income:list')


def _parse_is_salary(post):
    v = (post.get('is_salary') or '').strip().lower()
    return v in ('1', 'true', 'on', 'yes')


def _salary_income_upsert(request, admin_id, ajax):
    """One-row-per-site upsert for Salary Income panel writes.

    Site MUST be in this cycle's expense-side salary set (server-side
    re-validation of the seed set). Date defaults to cycle start.
    If a matching (admin_id, site, is_salary=True, date in cycle) row
    exists it is UPDATED; otherwise a new row is created.
    """
    from decimal import Decimal, InvalidOperation
    from accounts.cycle_utils import get_salary_cycle
    from accounts.date_utils import today_ist, validate_not_future
    from django.core.exceptions import ValidationError

    cycle = get_salary_cycle(today_ist())
    exp_totals = _salary_cycle_expense_totals(admin_id, cycle)

    raw_site = (request.POST.get('location_site') or '').strip()
    site_key = raw_site.lower()
    bucket = exp_totals.get(site_key)
    if bucket is None:
        msg = 'Site is not in this cycle’s salary expense set.'
        if ajax:
            return JsonResponse({'success': False, 'message': msg,
                                 'errors': {'location_site': [msg]}}, status=400)
        messages.error(request, msg)
        return redirect('income:list')
    site_display = bucket['display']

    amount_raw = (request.POST.get('amount') or '').strip()
    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError):
        amount = None
    if amount is None or amount <= 0:
        msg = 'Credit Amount must be greater than zero.'
        if ajax:
            return JsonResponse({'success': False, 'message': msg,
                                 'errors': {'amount': [msg]}}, status=400)
        messages.error(request, msg)
        return redirect('income:list')

    from_account = (request.POST.get('from_account') or '').strip()[:200]
    remarks      = (request.POST.get('remarks') or '').strip()[:500]

    # Date: use POST value if provided and in-cycle, else cycle start.
    date_raw = (request.POST.get('date') or '').strip()
    row_date = cycle['start']
    if date_raw:
        try:
            import datetime as _dt
            parsed = _dt.datetime.strptime(date_raw, '%Y-%m-%d').date()
            if cycle['start'] <= parsed <= cycle['end']:
                row_date = parsed
        except ValueError:
            pass
    try:
        validate_not_future(row_date, 'Income date')
    except ValidationError as e:
        msg = str(e.message if hasattr(e, 'message') else e)
        if ajax:
            return JsonResponse({'success': False, 'message': msg,
                                 'errors': {'date': [msg]}}, status=400)
        messages.error(request, msg)
        return redirect('income:list')

    existing = (Income.objects
                .filter(admin_id=admin_id, is_salary=True,
                        location_site__iexact=site_display,
                        date__gte=cycle['start'], date__lte=cycle['end'])
                .order_by('-date', '-created_at')
                .first())
    if existing is None:
        income = Income(
            user=request.user,
            admin_id=admin_id,
            amount=amount,
            date=row_date,
            location_site=site_display,
            from_account=from_account,
            remarks=remarks,
            income_type='SALARY',
            is_salary=True,
        )
    else:
        income = existing
        income.amount        = amount
        income.date          = row_date
        income.location_site = site_display
        income.from_account  = from_account
        income.remarks       = remarks
        income.is_salary     = True
    income.save()
    _ensure_location_site(admin_id, income.location_site, request.user)

    if ajax:
        d = _income_to_dict(income)
        d['salary'] = str(bucket['total'])
        d['balance'] = str((amount or Decimal('0')) - (bucket['total'] or Decimal('0')))
        return JsonResponse({'success': True, 'income': d})
    messages.success(request, f'Salary income saved for {site_display}.')
    return redirect('income:list')


@login_required
def income_edit(request, pk):
    if is_admin_user(request.user):
        income = get_object_or_404(Income, pk=pk, admin_id=get_admin_id(request.user))
    else:
        income = get_object_or_404(Income, pk=pk, user=request.user)

    # Modal-only flow: GET bounces to the list.
    if request.method != 'POST':
        return redirect('income:list')

    ajax = _is_ajax(request)

    # Salary Income upsert path — reuse the create-side helper so both
    # entry points share validation and one-per-site enforcement. The pk
    # in the URL is honoured only when it matches the resolved upsert
    # target; the helper's own query decides which row to update.
    if _parse_is_salary(request.POST):
        return _salary_income_upsert(request, get_admin_id(request.user), ajax)

    form = IncomeForm(request.user, request.POST, instance=income)

    if form.is_valid():
        income = form.save(commit=False)
        income.admin_id = get_admin_id(request.user)
        # Preserve is_salary across edits: only overwrite if POST explicitly
        # supplied the flag. Prevents an inline edit from the standard site
        # panel from silently flipping a salary row into a regular row.
        if 'is_salary' in request.POST:
            income.is_salary = _parse_is_salary(request.POST)
        income.location_site = _normalize_site_or_office(
            income.admin_id, income.location_site, request.user,
        )
        income.save()
        _ensure_location_site(
            get_admin_id(request.user),
            income.location_site,
            request.user,
        )
        if ajax:
            d = _income_to_dict(income)
            d['combo'] = _income_combo_data(income, request.user, is_admin_user(request.user))
            return JsonResponse({'success': True, 'income': d})
        messages.success(request, f'Income "{income.title}" updated.')
        return redirect('income:list')

    if ajax:
        errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
        first_error = next(iter(errors.values()), ['Invalid data.'])[0]
        return JsonResponse({'success': False, 'errors': errors, 'message': first_error}, status=400)

    messages.error(request, 'Could not update income. Please try again.')
    return redirect('income:list')


@login_required
def income_delete(request, pk):
    if is_admin_user(request.user):
        income = get_object_or_404(Income, pk=pk, admin_id=get_admin_id(request.user))
    else:
        income = get_object_or_404(Income, pk=pk, user=request.user)
        
    if request.method == 'POST':
        title = income.title
        income.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, f'Income "{title}" deleted.')
        return redirect('income:list')
    return render(request, 'income/confirm_delete.html', {'income': income})


@login_required
def delete_incomes_by_sites(request):
    """Bulk-delete every Income row whose location_site matches one of the
    site names in `sites[]` (case-insensitive). Scope is strictly the
    current admin tenant — never touches projects.Site or
    attendance.AttendanceRecord. POST only, atomic, returns per-site counts."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    admin_id = get_admin_id(request.user)
    if not admin_id:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    site_names = request.POST.getlist('sites') or request.POST.getlist('sites[]')
    site_names = [s.strip() for s in site_names if (s or '').strip()]
    if not site_names:
        return JsonResponse({'success': False, 'error': 'No sites selected'}, status=400)

    from django.db import transaction as _db_tx
    import logging as _logging
    _log = _logging.getLogger(__name__)

    # TODO remove debug logging after delete flow verified
    _log.info(
        "DEBUG delete_incomes_by_sites: admin_id=%r raw_body=%r POST=%r parsed_sites=%r",
        admin_id, request.body[:500], dict(request.POST.lists()), site_names,
    )

    # FIX 2 (belt-and-suspenders): also match against the internal-whitespace
    # collapsed form so "Foo  Bar" from a card matches a "Foo Bar" row.
    import re as _re
    site_q = Q()
    for name in site_names:
        stripped = name.strip()
        collapsed = _re.sub(r'\s+', ' ', stripped)
        site_q |= Q(location_site__iexact=stripped)
        if collapsed != stripped:
            site_q |= Q(location_site__iexact=collapsed)

    base_qs = Income.objects.filter(admin_id=admin_id).filter(site_q)

    from finance.models import ModuleHiddenSite

    deleted_by_site = {}
    hidden_site_names = []
    with _db_tx.atomic():
        for name in site_names:
            deleted_by_site[name] = base_qs.filter(location_site__iexact=name).count()
        pre_delete_total = base_qs.count()  # TODO remove debug logging after delete flow verified
        deleted_count, _ = base_qs.delete()

        for name in site_names:
            stripped = name.strip()
            if not stripped:
                continue
            _, created = ModuleHiddenSite.objects.get_or_create(
                admin_id=admin_id,
                module='income',
                site_name=stripped,
                defaults={'hidden_by': request.user if request.user.is_authenticated else None},
            )
            hidden_site_names.append(stripped)

    _log.info(
        "Bulk income delete: admin_id=%s sites=%s pre_count=%s deleted=%s per_site=%s hidden=%s",
        admin_id, site_names, pre_delete_total, deleted_count, deleted_by_site, hidden_site_names,
    )

    return JsonResponse({
        'success': True,
        'deleted_row_count':  deleted_count,
        'hidden_site_count':  len(hidden_site_names),
        'hidden_site_names':  hidden_site_names,
        'deleted_by_site':    deleted_by_site,
        'deleted_count': deleted_count,
    })


@login_required
def debug_site_match_income(request):
    """Diagnostic-only endpoint. For each card-list site name reports how
    many Income rows this admin owns under that name. Gated by ?debug=1
    AND admin-scope. TODO remove after delete-flow verified."""
    if request.GET.get('debug') != '1':
        return JsonResponse({'error': 'not enabled'}, status=404)

    admin_id = get_admin_id(request.user)
    if not admin_id:
        return JsonResponse({'error': 'no admin scope'}, status=403)

    from finance.services.site_cards import get_active_site_names
    card_names = get_active_site_names(admin_id, restrict_today=False)

    raw_qs = Income.objects.filter(admin_id=admin_id)
    distinct_stored = sorted(
        set(
            (v or '') for v in raw_qs.values_list('location_site', flat=True).distinct()
        ),
        key=lambda s: s.lower(),
    )
    stored_lower_prefix = [(s, s.strip().lower()[:5]) for s in distinct_stored]

    per_card = []
    for name in card_names:
        stripped = (name or '').strip()
        prefix = stripped.lower()[:5]
        exact_ct    = raw_qs.filter(location_site=name).count()
        iexact_ct   = raw_qs.filter(location_site__iexact=stripped).count()
        icontain_ct = raw_qs.filter(location_site__icontains=stripped).count() if stripped else 0
        similar = [s for (s, p) in stored_lower_prefix if p and prefix and p == prefix][:3]
        per_card.append({
            'card_data_site_name': name,
            'stripped_for_match':  stripped,
            'exact_count':         exact_ct,
            'iexact_count':        iexact_ct,
            'icontains_count':     icontain_ct,
            'similar_stored_samples': similar,
        })

    top_rows = list(raw_qs.order_by('-created_at').values(
        'id', 'admin_id', 'location_site', 'amount', 'date',
    )[:3])

    return JsonResponse({
        'admin_id_in_scope':       admin_id,
        'total_income_rows':       raw_qs.count(),
        'distinct_location_sites_stored': distinct_stored,
        'card_names_from_union':   card_names,
        'per_card_match_counts':   per_card,
        'top_3_income_rows':       top_rows,
    }, json_dumps_params={'indent': 2})
