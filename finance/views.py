from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
import json
import datetime
from .models import Transaction, Category, Source
from .forms import TransactionForm, CategoryForm
from branches.models import LocationSite
from accounts.views import get_admin_id


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


def _balance_by_combo_expense(user):
    """Return balance per (Income Source, Account) for the expense page.
    Keys are normalised to lower-case so matching is case-insensitive; the display
    values ('source', 'account') keep the original casing from the income record.

    Defensive: each cross-module query is wrapped + uses `.only(...)` so a
    transient migration mismatch on either side doesn't 500 the page.
    """
    admin_id = get_admin_id(user)
    combo_map = {}

    try:
        from income.models import Income
        income_qs = Income.objects.filter(admin_id=admin_id).only(
            'amount', 'payment_by', 'payment_mode',
        )
        for i in income_qs:
            source  = (i.payment_by or '').strip()
            account = (i.payment_mode or '').strip()
            if source and account:
                k = f"{source.lower()}|||{account.lower()}"
                if k not in combo_map:
                    combo_map[k] = {'source': source, 'account': account, 'income': 0, 'expense': 0}
                combo_map[k]['income'] += float(i.amount)
    except Exception:
        pass

    try:
        expense_qs = Transaction.objects.filter(admin_id=admin_id, type='expense').only(
            'amount', 'income_source', 'payment_mode',
        )
        for e in expense_qs:
            source  = (e.income_source or '').strip()
            account = (e.payment_mode or '').strip()
            if source and account:
                k = f"{source.lower()}|||{account.lower()}"
                if k not in combo_map:
                    combo_map[k] = {'source': source, 'account': account, 'income': 0, 'expense': 0}
                combo_map[k]['expense'] += float(e.amount)
    except Exception:
        pass

    result = []
    for v in combo_map.values():
        v['balance'] = v['income'] - v['expense']
        result.append(v)
    return sorted(result, key=lambda x: (-abs(x['balance']), x['source']))


def _is_ajax(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


# Fixed 8-slot accent palette — assigned per site by hashing the site name so
# the same site always renders with the same border accent in both the Expense
# Manager and Income module cards. Kept readable on the light theme.
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


def _group_expenses_by_site(expenses, user):
    """
    Site-based card view for the Expense page (Income/Expense restructure).

    Groups expense Transactions by `location_site` (case-insensitive). For
    each site returns credit (sum of Income amounts for the SAME site —
    pulled live from income.Income, never duplicated), debit (sum of
    Transaction amounts), and balance = credit - debit. Sort order: most
    recent expense activity first.

    Sites that have income but zero expense are still surfaced so the
    admin can see the credit balance even before any expense is logged.

    Defensive: the cross-module Income query is wrapped in try/except so a
    transient Income-side failure (e.g. mid-deploy when one migration has
    run and the other hasn't) degrades to an empty credit map instead of
    blowing up the entire Expense page.
    """
    import datetime as _dt
    from decimal import Decimal as _D
    from accounts.views import get_admin_id
    admin_id = get_admin_id(user)

    # Normalise the (raw -> key, display) for a site value so the "(No Site)"
    # bucket collapses every shape an empty/no-site record can take: NULL,
    # empty string, whitespace, or the literal string "(No Site)" that
    # earlier site-detail Add-Row submissions wrote back into location_site.
    # This is what fixes the "two (No Site) cards" symptom — the grouping
    # key is now identical regardless of how the row was created.
    def _site_key_display(raw):
        s = (raw or '').strip()
        if not s or s.lower() == '(no site)':
            return '', '(No Site)'
        return s.lower(), s

    # Credit map: site → total income amount for that tenant. Built in a
    # single sweep so site_card render stays O(N) over expenses + incomes.
    # credit_by_month[site_key][YYYY-MM] = Decimal — feeds the card-level
    # month dropdown so each card can show monthly Credit/Debit/Balance.
    credit_map  = {}
    site_disp   = {}
    income_dates = {}
    credit_by_month = {}
    try:
        from income.models import Income
        income_qs = Income.objects.filter(admin_id=admin_id).only(
            'amount', 'location_site', 'date',
        )
        for i in income_qs:
            key, disp = _site_key_display(i.location_site)
            credit_map[key] = credit_map.get(key, _D('0')) + (i.amount or _D('0'))
            if key not in site_disp or not site_disp[key]:
                site_disp[key] = disp
            if i.date:
                mkey = i.date.strftime('%Y-%m')
                cb = credit_by_month.setdefault(key, {})
                cb[mkey] = cb.get(mkey, _D('0')) + (i.amount or _D('0'))
                prev = income_dates.get(key)
                if prev is None or i.date > prev:
                    income_dates[key] = i.date
    except Exception:
        # Income table unavailable (e.g. migration not yet applied). Render
        # the Expense page with zero credit rather than 500-ing.
        credit_map  = {}
        site_disp   = {}
        income_dates = {}
        credit_by_month = {}

    debit_by_month = {}
    groups = {}
    for e in expenses:
        key, disp = _site_key_display(getattr(e, 'location_site', None))
        g = groups.get(key)
        if g is None:
            g = {
                'site':         site_disp.get(key) or disp,
                'site_key':     key,
                'credit':       credit_map.get(key, _D('0')),
                'debit':        _D('0'),
                'balance':      _D('0'),
                'count':        0,
                'latest_date':  e.date,
                'transactions': [],
            }
            groups[key] = g
        g['debit'] += (e.amount or _D('0'))
        g['count'] += 1
        g['transactions'].append(e)
        if e.date:
            mkey = e.date.strftime('%Y-%m')
            db = debit_by_month.setdefault(key, {})
            db[mkey] = db.get(mkey, _D('0')) + (e.amount or _D('0'))
        if e.date and (g['latest_date'] is None or e.date > g['latest_date']):
            g['latest_date'] = e.date
            # Don't overwrite the canonical display with a blank — keep the
            # first non-empty real-site spelling, otherwise leave "(No Site)".
            if key:
                g['site'] = disp

    # Surface income-only sites (credit > 0, no expense yet) so the card
    # list reflects every site the tenant is tracking — admin still needs
    # to see the positive balance.
    for key, credit in credit_map.items():
        if key in groups:
            continue
        groups[key] = {
            'site':         site_disp.get(key) or '(No Site)',
            'site_key':     key,
            'credit':       credit,
            'debit':        _D('0'),
            'balance':      credit,
            'count':        0,
            'latest_date':  income_dates.get(key),
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
        # tiles without a round-trip. Includes every month with credit OR
        # debit activity, plus the current month (default selection).
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
        # Pretty month options for the dropdown — sorted most-recent first.
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


def _dynamic_site_options(admin_id, month_yyyy_mm=None, exact_date=None):
    """Site NAMES to surface in the Expense-page site filter dropdown.

    Scope is EITHER a single date (`exact_date`, higher priority) OR a
    month string 'YYYY-MM'. Union of names from:
      * attendance.AttendanceRecord.site (CharField, mobile back-compat)
      * attendance.AttendanceRecord.site_ref.name (FK on projects.Site)
      * projects.WorkLog.site.name (FK on projects.Site)
      * distinct non-empty Transaction.location_site strings (legacy)

    Returns [{'name': <display>}] deduped on lower(name), sorted by name.
    Returns [] when scope is empty (no date, no month).
    """
    if not exact_date and not month_yyyy_mm:
        return []

    def _scope_filter(qs, date_field):
        if exact_date is not None:
            return qs.filter(**{date_field: exact_date})
        return qs.filter(**{f"{date_field}__startswith": month_yyyy_mm})

    names = set()

    try:
        from attendance.models import AttendanceRecord
        att_qs = _scope_filter(
            AttendanceRecord.objects.filter(admin_id=admin_id),
            'date',
        )
        for n in att_qs.exclude(site__isnull=True).exclude(site='') \
                       .values_list('site', flat=True).distinct():
            if n:
                names.add(n.strip())
        for n in att_qs.filter(site_ref__isnull=False) \
                       .values_list('site_ref__name', flat=True).distinct():
            if n:
                names.add(n.strip())
    except Exception:  # noqa: BLE001
        pass

    try:
        from projects.models import WorkLog
        for n in _scope_filter(
            WorkLog.objects.filter(admin_id=admin_id, site__isnull=False),
            'date',
        ).values_list('site__name', flat=True).distinct():
            if n:
                names.add(n.strip())
    except Exception:  # noqa: BLE001
        pass

    for n in _scope_filter(
        Transaction.objects.filter(admin_id=admin_id), 'date',
    ).exclude(location_site__isnull=True).exclude(location_site='') \
     .values_list('location_site', flat=True).distinct():
        if n:
            names.add(n.strip())

    dedup = {}
    for n in names:
        key = n.lower()
        if key and key not in dedup:
            dedup[key] = n
    return sorted(
        ({'name': v} for v in dedup.values()),
        key=lambda o: o['name'].lower(),
    )


def _group_expenses_by_account(qs):
    """
    Group an already-filtered Transaction queryset by `payment_mode` (the
    column that holds the Account name, e.g. "MURUGAN NALLAKANNU").

    Returns a list of dicts, sorted by latest_date descending:
        {
            'account':      <display name, casing of the most recent row>,
            'account_key':  <lower-cased account, the dedup key>,
            'total':        Decimal — sum of all amounts in this group,
            'count':        int — number of transactions,
            'latest_date':  date — most recent transaction date,
            'transactions': [Transaction, ...] — sorted by date desc,
        }

    Records with a blank account fall under the "(No Account)" bucket so
    they are still visible to the admin (instead of silently disappearing).
    Lower-cased keys mirror the case-insensitive matching used by
    `_balance_by_combo_expense` above — two rows with "Cash" / "CASH"
    collapse into one card.
    """
    import datetime as _dt
    from decimal import Decimal as _D
    groups = {}
    for t in qs:
        acc = (getattr(t, 'payment_mode', None) or '').strip()
        key = acc.lower()
        g = groups.get(key)
        if g is None:
            g = {
                'account':      acc or '(No Account)',
                'account_key':  key,
                'total':        _D('0'),
                'count':        0,
                'latest_date':  t.date,
                'transactions': [],
            }
            groups[key] = g
        g['total'] += t.amount
        g['count'] += 1
        g['transactions'].append(t)
        if t.date and (g['latest_date'] is None or t.date > g['latest_date']):
            g['latest_date'] = t.date
            # Refresh display casing to the most recent row's spelling.
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


def _expense_combo_data(t, user):
    """Return the combo balance dict for this transaction's (income_source, account) pair.
    Comparison is case-insensitive to match the normalised _balance_by_combo_expense keys."""
    src = (t.income_source or '').strip().lower()
    acc = (t.payment_mode or '').strip().lower()
    if not (src and acc):
        return None
    for c in _balance_by_combo_expense(user):
        if c['source'].lower() == src and c['account'].lower() == acc:
            return c
    return None


def _expense_to_dict(t):
    return {
        'id': t.pk,
        'date': t.date.isoformat() if t.date else '',
        'date_display': t.date.strftime('%d %b, %Y') if t.date else '',
        'amount': str(t.amount),
        'amount_display': '{:,.2f}'.format(float(t.amount)),
        'category': t.category.name if t.category else 'General',
        'category_id': t.category_id,
        # Fixed-choice category for the site-detail panel (Income/Expense
        # restructure). Stored on the row as a code ('food', 'fuel', …);
        # the display label is resolved via Transaction.get_expense_category_display().
        'expense_category':         getattr(t, 'expense_category', '') or '',
        'expense_category_display': t.get_expense_category_display() if getattr(t, 'expense_category', '') else '',
        'expense_type': t.purpose or '',
        'location': t.location_site or '',
        'payment_by': t.payment_by or '',
        'payment_to': t.vendor or '',
        'payment_mode': t.payment_mode or '',
        'income_source': t.income_source or '',
        'description': t.description or '',
        'edit_url': f'/expenses/{t.pk}/edit/',
        'delete_url': f'/expenses/{t.pk}/delete/',
    }

FILTER_PARAM_KEYS = ('date', 'month', 'site', 'income_source', 'category', 'search', 'account')


def _apply_expense_filters(request, admin_id):
    """
    Parse the Expense page's querystring filters and apply them to a
    Transaction queryset. Returns (qs, filters, has_explicit_filter,
    exact_date, month, today_default_active).

    Rule: if the user has set ANY filter param, honour it verbatim. If not
    (fresh landing on /expenses/), narrow to today's active sites — a soft
    default the moment any filter is touched.
    """
    qs = (
        Transaction.objects
        .filter(admin_id=admin_id, type='expense')
        .select_related('category', 'branch')
    )

    cat_id        = request.GET.get('category', '')
    month         = request.GET.get('month', '')
    search        = request.GET.get('search', '')
    account       = request.GET.get('account', '')
    income_source = request.GET.get('income_source', '')
    site_filter   = request.GET.get('site', '')  # '' | site_name | 'UNASSIGNED'

    has_explicit_filter = any(
        (request.GET.get(k) or '').strip() for k in FILTER_PARAM_KEYS
    )

    _raw_date = request.GET.get('date', None)
    if _raw_date is None or _raw_date.strip() == '':
        exact_date = None
    else:
        try:
            exact_date = datetime.date.fromisoformat(_raw_date.strip())
        except (ValueError, TypeError):
            exact_date = None

    today_default_active = False
    if not has_explicit_filter:
        # Soft default — narrow the Expense landing view to sites that are
        # active in Attendance / WorkLog / Transaction today (IST). Anything
        # the user changes drops this restriction immediately.
        today = timezone.localdate()
        today_names = [
            s['name'] for s in _dynamic_site_options(admin_id, exact_date=today)
        ]
        if today_names:
            site_q = Q()
            for n in today_names:
                site_q |= Q(location_site__iexact=n)
            qs = qs.filter(site_q)
            today_default_active = True

    if cat_id:        qs = qs.filter(category_id=cat_id)
    if exact_date:
        qs = qs.filter(date=exact_date)
    elif month:
        qs = qs.filter(date__startswith=month)
    if search:        qs = qs.filter(
        Q(description__icontains=search) | Q(vendor__icontains=search) | Q(reference__icontains=search)
    )
    if account:       qs = qs.filter(payment_mode__icontains=account)
    if income_source: qs = qs.filter(income_source__icontains=income_source)
    if site_filter:
        if site_filter == 'UNASSIGNED':
            qs = qs.filter(Q(location_site__isnull=True) | Q(location_site=''))
        else:
            qs = qs.filter(location_site__iexact=site_filter)

    filters = {
        'category':      cat_id,
        'month':         month,
        'search':        search,
        'account':       account,
        'income_source': income_source,
        'site':          site_filter,
        'date':          exact_date.isoformat() if exact_date else '',
    }
    return qs, filters, has_explicit_filter, exact_date, month, today_default_active


def _all_site_options(admin_id):
    """Full universe of location_site names ever used by this tenant.

    Union of:
      * distinct Transaction.location_site (any type)
      * attendance.AttendanceRecord.site  and  .site_ref__name
      * projects.WorkLog.site__name
      * projects.Site.name  (master list)
    Returned as [{'name': <display>}] deduped case-insensitively, sorted A→Z.
    """
    names = set()

    for n in (
        Transaction.objects.filter(admin_id=admin_id)
        .exclude(location_site__isnull=True).exclude(location_site='')
        .values_list('location_site', flat=True).distinct()
    ):
        if n:
            names.add(n.strip())

    try:
        from attendance.models import AttendanceRecord
        att_qs = AttendanceRecord.objects.filter(admin_id=admin_id)
        for n in att_qs.exclude(site__isnull=True).exclude(site='') \
                       .values_list('site', flat=True).distinct():
            if n:
                names.add(n.strip())
        for n in att_qs.filter(site_ref__isnull=False) \
                       .values_list('site_ref__name', flat=True).distinct():
            if n:
                names.add(n.strip())
    except Exception:
        pass

    try:
        from projects.models import WorkLog
        for n in (
            WorkLog.objects.filter(admin_id=admin_id, site__isnull=False)
            .values_list('site__name', flat=True).distinct()
        ):
            if n:
                names.add(n.strip())
    except Exception:
        pass

    try:
        from projects.models import Site as _ProjSite
        for n in (
            _ProjSite.objects.filter(admin_id=admin_id)
            .values_list('name', flat=True)
        ):
            if n:
                names.add(n.strip())
    except Exception:
        pass

    dedup = {}
    for n in names:
        key = n.lower()
        if key and key not in dedup:
            dedup[key] = n
    return sorted(
        ({'name': v} for v in dedup.values()),
        key=lambda o: o['name'].lower(),
    )


@login_required
def transaction_list(request):
    admin_id = get_admin_id(request.user)
    qs, filters, has_explicit_filter, exact_date, month, today_default_active = \
        _apply_expense_filters(request, admin_id)

    total_expense = qs.aggregate(t=Sum('amount'))['t'] or 0

    # Total Income across the same tenant — feeds the Balance Summary box
    # so its numbers stay consistent with the Total Expenses card above.
    # Defensive: a transient Income-side schema mismatch falls back to 0.
    try:
        from income.models import Income as _Income
        total_income = _Income.objects.filter(admin_id=admin_id).aggregate(t=Sum('amount'))['t'] or 0
    except Exception:
        total_income = 0
    net_balance = (total_income or 0) - (total_expense or 0)

    now = timezone.now()
    this_month_qs = Transaction.objects.filter(
        admin_id=admin_id, type='expense',
        date__year=now.year, date__month=now.month
    )
    this_month_expense = this_month_qs.aggregate(t=Sum('amount'))['t'] or 0
    expense_count = qs.count()

    balance_combos = _balance_by_combo_expense(request.user)
    # Keyed by lower-case (source, account) so lookup is case-insensitive.
    combo_map = {(c['source'].lower(), c['account'].lower()): c for c in balance_combos}

    # Defensive fetch: if migration 0008 (expense_category) hasn't been
    # applied on this DB yet, the default `list(qs[:200])` would 500 because
    # the SELECT includes a column that doesn't exist. Falling back to a
    # deferred fetch + a stubbed value in __dict__ prevents the template
    # from triggering a lazy load that would also fail.
    try:
        transactions_list = list(qs[:200])
    except Exception:
        transactions_list = list(qs.defer('expense_category')[:200])
        for _t in transactions_list:
            _t.__dict__['expense_category'] = ''

    for t in transactions_list:
        src = (t.income_source or '').strip().lower()
        acc = (t.payment_mode or '').strip().lower()
        t.combo_data = combo_map.get((src, acc)) if (src and acc) else None

    # ── Serialize to JSON for client-side JS rendering ──
    _mode_display = dict(Transaction.PAYMENT_MODE)
    transactions_json = json.dumps([{
        'id':          t.pk,
        'date':        t.date.isoformat() if t.date else '',
        'type':        t.type,
        'desc':        t.description or '',
        'amount':      float(t.amount),
        'catId':       t.category_id,
        'catName':     t.category.name if t.category else 'General',
        'catColor':    t.category.color if t.category else '#94a3b8',
        'branchId':    t.branch_id,
        'branchName':  t.branch.name if t.branch else '',
        'mode':        _mode_display.get(t.payment_mode, t.payment_mode or ''),
        'account':     t.payment_mode or '',
        'vendor':      t.vendor or '',
        'ref':         t.reference or '',
        'incomeSource': t.income_source or '',
    } for t in transactions_list])

    # Group the filtered transactions by Account (legacy) and Site (new
    # site-based card view, Income/Expense restructure). The site card uses
    # live Income totals as Credit — never duplicated.
    accounts_grouped = _group_expenses_by_account(transactions_list)
    sites_grouped    = _group_expenses_by_site(transactions_list, request.user)

    # Site dropdown — full universe of sites the tenant has ever used, so
    # the filter never looks broken. Add an "Unassigned" bucket when any
    # Transaction row is missing location_site.
    site_options = _all_site_options(admin_id)
    has_unassigned = Transaction.objects.filter(admin_id=admin_id, type='expense') \
        .filter(Q(location_site__isnull=True) | Q(location_site='')).exists()

    # Unique Credit From / Credit To values across this tenant's expense
    # rows — feeds the inline-edit dropdowns (datalists) in the site detail
    # panel. No model fields added; we just surface what's already stored.
    payment_by_options = list(
        Transaction.objects.filter(admin_id=admin_id, type='expense')
        .exclude(payment_by__isnull=True).exclude(payment_by='')
        .values_list('payment_by', flat=True).distinct().order_by('payment_by')
    )
    vendor_options = list(
        Transaction.objects.filter(admin_id=admin_id, type='expense')
        .exclude(vendor__isnull=True).exclude(vendor='')
        .values_list('vendor', flat=True).distinct().order_by('vendor')
    )

    return render(request, 'finance/list.html', {
        'transactions':        transactions_list,
        'transactions_json':   transactions_json,
        'accounts_grouped':    accounts_grouped,
        'sites_grouped':       sites_grouped,
        'total_expense':       total_expense,
        'total_income':        total_income,
        'net_balance':         net_balance,
        'this_month_expense':  this_month_expense,
        'expense_count':       expense_count,
        'categories':          Category.objects.filter(admin_id=admin_id, type='expense'),
        'filters':               filters,
        'site_options':          site_options,
        'has_unassigned':        has_unassigned,
        'today_default_active':  today_default_active,
        'is_date_scoped':        bool(exact_date),
        'today_ist_iso':         timezone.localdate().isoformat(),
        'location_sites_json':  _location_sites_json(request.user),
        'income_sources_json':  _shared_sources_json(request.user),
        'accounts_json':        _shared_accounts_json(request.user),
        'balance_data':         balance_combos,
        # Default selection for the per-card month dropdown (Issue 4) —
        # the page renders with the current month pre-selected so each card
        # surfaces this month's Credit/Debit/Balance immediately.
        'current_month':        timezone.now().strftime('%Y-%m'),
        # Unique values for the inline-edit Credit From / Credit To dropdowns.
        'payment_by_options':   payment_by_options,
        'vendor_options':       vendor_options,
    })

@login_required
def add_transaction(request):
    # Default any GET hit on /expenses/add/ back to the list page (modal-only flow).
    if request.method != 'POST':
        return redirect('expenses:list')

    # Force the type to expense regardless of what the client sent.
    post_data = request.POST.copy()
    post_data['type'] = 'expense'

    form = TransactionForm(request.user, post_data)
    ajax = _is_ajax(request)

    if form.is_valid():
        t = form.save(commit=False)
        t.user     = request.user
        t.type     = 'expense'
        t.admin_id = get_admin_id(request.user)
        t.save()
        if t.location_site:
            admin_id = get_admin_id(request.user)
            name = t.location_site.strip()
            if name and not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
                LocationSite.objects.create(admin_id=admin_id, name=name, created_by=request.user)
        if ajax:
            d = _expense_to_dict(t)
            d['combo'] = _expense_combo_data(t, request.user)
            return JsonResponse({'success': True, 'expense': d})
        messages.success(request, "Expense recorded.")
        return redirect('expenses:list')

    if ajax:
        errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
        first_error = next(iter(errors.values()), ['Invalid data.'])[0]
        return JsonResponse({'success': False, 'errors': errors, 'message': first_error}, status=400)

    # Non-AJAX fallback: still keep user on the list page; surface the error in flash.
    messages.error(request, "Could not save expense. Please try again.")
    return redirect('expenses:list')

@login_required
def edit_transaction(request, pk):
    t = get_object_or_404(Transaction, pk=pk, admin_id=get_admin_id(request.user))

    # Modal-only flow: any GET hit on /expenses/<pk>/edit/ bounces to the list.
    if request.method != 'POST':
        return redirect('expenses:list')

    post_data = request.POST.copy()
    post_data['type'] = 'expense'

    form = TransactionForm(request.user, post_data, instance=t)
    ajax = _is_ajax(request)

    if form.is_valid():
        obj = form.save(commit=False)
        obj.user     = request.user
        obj.type     = 'expense'
        obj.admin_id = get_admin_id(request.user)
        obj.save()
        if obj.location_site:
            admin_id = get_admin_id(request.user)
            name = obj.location_site.strip()
            if name and not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
                LocationSite.objects.create(admin_id=admin_id, name=name, created_by=request.user)
        if ajax:
            d = _expense_to_dict(obj)
            d['combo'] = _expense_combo_data(obj, request.user)
            return JsonResponse({'success': True, 'expense': d})
        messages.success(request, "Expense updated.")
        return redirect('expenses:list')

    if ajax:
        errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
        first_error = next(iter(errors.values()), ['Invalid data.'])[0]
        return JsonResponse({'success': False, 'errors': errors, 'message': first_error}, status=400)

    messages.error(request, "Could not update expense. Please try again.")
    return redirect('expenses:list')

@login_required
def delete_transaction(request, pk):
    t = get_object_or_404(Transaction, pk=pk, admin_id=get_admin_id(request.user))
    if request.method == 'POST':
        t.delete()
        messages.success(request, "Deleted.")
    return redirect('expenses:list')

# ═══════════════════════════════════════════════════════════════════════
# Export — PDF + Excel. Both reuse `_apply_expense_filters` so the report
# reflects the exact filter state the user has on screen (querystring is
# forwarded from the Download links).
# ═══════════════════════════════════════════════════════════════════════
EXPORT_CATEGORIES = ['food', 'room', 'diesel', 'travel', 'ticket', 'other']
EXPORT_CATEGORY_LABELS = {
    'food':   'Food',
    'room':   'Room',
    'diesel': 'Diesel',
    'travel': 'Travel',
    'ticket': 'Ticket',
    'other':  'Misc/Others',
}


def _filter_summary(filters):
    parts = []
    if filters.get('month'):         parts.append(f"Month={filters['month']}")
    if filters.get('date'):          parts.append(f"Date={filters['date']}")
    if filters.get('site'):          parts.append(f"Site={filters['site']}")
    if filters.get('income_source'): parts.append(f"Source={filters['income_source']}")
    if filters.get('account'):       parts.append(f"Account={filters['account']}")
    if filters.get('category'):      parts.append(f"Category={filters['category']}")
    if filters.get('search'):        parts.append(f"Search={filters['search']}")
    return ' | '.join(parts) if parts else 'None'


def _row_category_amounts(t):
    """Return dict {food, room, diesel, travel, ticket, other} — amount in
    the row's expense_category slot, 0 elsewhere. Diesel absorbs 'fuel';
    an unset category falls into 'other' so nothing goes missing."""
    cat = (getattr(t, 'expense_category', '') or '').strip().lower()
    if cat == 'fuel':
        cat = 'diesel'
    if cat not in EXPORT_CATEGORIES:
        cat = 'other'
    amt = float(t.amount or 0)
    return {c: (amt if c == cat else 0.0) for c in EXPORT_CATEGORIES}


@login_required
def export_expenses_pdf(request):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )
    from django.http import HttpResponse
    from io import BytesIO
    from decimal import Decimal as _D

    admin_id = get_admin_id(request.user)
    qs, filters, _has, _ed, _mo, _td = _apply_expense_filters(request, admin_id)
    try:
        rows = list(qs.order_by('location_site', 'date'))
    except Exception:
        rows = list(qs.defer('expense_category').order_by('location_site', 'date'))
        for _t in rows:
            _t.__dict__.setdefault('expense_category', '')

    sites_grouped = _group_expenses_by_site(rows, request.user)

    try:
        from income.models import Income as _Income
        total_income = _Income.objects.filter(admin_id=admin_id).aggregate(t=Sum('amount'))['t'] or 0
    except Exception:
        total_income = 0
    total_expense = sum((float(t.amount or 0) for t in rows), 0.0)
    net_balance = float(total_income) - total_expense

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=14, spaceAfter=4)
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    label = ParagraphStyle('label', parent=styles['Normal'], fontSize=9)

    story = []
    ts = timezone.localtime().strftime('%d %b %Y, %H:%M IST')
    admin_name = (
        request.user.get_full_name() or request.user.username or request.user.email or 'Admin'
    )
    story.append(Paragraph('SPIM Suite — Expense Report', h1))
    story.append(Paragraph(f'Generated {ts} · {admin_name}', small))
    story.append(Paragraph(f'<b>Filters:</b> {_filter_summary(filters)}', label))
    story.append(Spacer(1, 6))

    header_cells = ['Date', 'Credit', 'From', 'To'] + \
        [EXPORT_CATEGORY_LABELS[c] for c in EXPORT_CATEGORIES] + ['Remarks']

    for g in sites_grouped:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<b>{g['site']}</b> &nbsp;·&nbsp; "
            f"Credit ₹{float(g['credit']):,.2f} &nbsp;·&nbsp; "
            f"Debit ₹{float(g['debit']):,.2f} &nbsp;·&nbsp; "
            f"Balance ₹{float(g['balance']):,.2f}",
            label,
        ))
        data = [header_cells]
        for t in g['transactions']:
            cats = _row_category_amounts(t)
            data.append([
                t.date.strftime('%d %b %Y') if t.date else '',
                f"{float(g['credit']):,.2f}" if g['credit'] else '',
                (t.payment_by or '')[:24],
                (t.vendor or '')[:24],
                *(f"{cats[c]:,.2f}" if cats[c] else '' for c in EXPORT_CATEGORIES),
                (t.description or '')[:60],
            ])
        tbl = Table(data, repeatRows=1, colWidths=[
            22 * mm, 20 * mm, 26 * mm, 26 * mm,
            18 * mm, 18 * mm, 18 * mm, 18 * mm, 18 * mm, 22 * mm,
            50 * mm,
        ])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 8),
            ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#cbd5e1')),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',      (4, 1), (9, -1), 'RIGHT'),
            ('ALIGN',      (1, 1), (1, -1), 'RIGHT'),
        ]))
        story.append(tbl)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<b>Grand Total</b> &nbsp;·&nbsp; Income ₹{float(total_income):,.2f} &nbsp;·&nbsp; "
        f"Expense ₹{total_expense:,.2f} &nbsp;·&nbsp; Net ₹{net_balance:,.2f}",
        label,
    ))
    if not sites_grouped:
        story.append(Paragraph('<i>No transactions match the current filter.</i>', label))

    doc.build(story)
    fname = 'spim_expenses_' + timezone.localtime().strftime('%Y-%m-%d_%H%M%S') + '.pdf'
    resp = HttpResponse(buf.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


@login_required
def export_expenses_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    from io import BytesIO

    admin_id = get_admin_id(request.user)
    qs, filters, _has, _ed, _mo, _td = _apply_expense_filters(request, admin_id)
    try:
        rows = list(qs.order_by('location_site', 'date'))
    except Exception:
        rows = list(qs.defer('expense_category').order_by('location_site', 'date'))
        for _t in rows:
            _t.__dict__.setdefault('expense_category', '')

    try:
        from income.models import Income as _Income
        total_income = float(_Income.objects.filter(admin_id=admin_id).aggregate(t=Sum('amount'))['t'] or 0)
    except Exception:
        total_income = 0.0
    total_expense = sum((float(t.amount or 0) for t in rows), 0.0)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Expenses'

    ts = timezone.localtime().strftime('%d %b %Y, %H:%M IST')
    ws.cell(row=1, column=1, value=f'SPIM Suite — Expense Report  (Generated {ts})').font = Font(bold=True, size=13)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=12)
    ws.cell(row=2, column=1, value=f'Filters: {_filter_summary(filters)}').font = Font(italic=True, color='64748B')
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=12)

    headers = ['Site', 'Date', 'Credit', 'From', 'To'] + \
        [EXPORT_CATEGORY_LABELS[c] for c in EXPORT_CATEGORIES] + ['Remarks']
    header_fill = PatternFill('solid', fgColor='F1F5F9')
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=4, column=i, value=h)
        c.font = Font(bold=True, color='334155')
        c.fill = header_fill
        c.alignment = Alignment(horizontal='center', vertical='center')

    r = 5
    rows_by_site = {}
    for t in rows:
        rows_by_site.setdefault((t.location_site or '(No Site)'), []).append(t)
    for site in sorted(rows_by_site.keys(), key=lambda s: s.lower()):
        for t in sorted(rows_by_site[site], key=lambda x: (x.date or datetime.date.min)):
            cats = _row_category_amounts(t)
            ws.cell(row=r, column=1,  value=site)
            ws.cell(row=r, column=2,  value=t.date.strftime('%Y-%m-%d') if t.date else '')
            ws.cell(row=r, column=3,  value='')
            ws.cell(row=r, column=4,  value=t.payment_by or '')
            ws.cell(row=r, column=5,  value=t.vendor or '')
            for i, k in enumerate(EXPORT_CATEGORIES):
                cell = ws.cell(row=r, column=6 + i, value=(cats[k] or None))
                if cats[k]:
                    cell.number_format = '#,##0.00'
            ws.cell(row=r, column=12, value=t.description or '')
            r += 1

    ws.freeze_panes = 'A5'
    for i in range(1, 13):
        col = get_column_letter(i)
        max_len = 10
        for row_cells in ws[col]:
            v = row_cells.value
            if v is None:
                continue
            max_len = max(max_len, min(40, len(str(v)) + 2))
        ws.column_dimensions[col].width = max_len

    summary_row = r + 1
    ws.cell(row=summary_row,     column=1, value='Total Income').font  = Font(bold=True)
    ws.cell(row=summary_row,     column=2, value=total_income).number_format = '#,##0.00'
    ws.cell(row=summary_row + 1, column=1, value='Total Expense').font = Font(bold=True)
    ws.cell(row=summary_row + 1, column=2, value=total_expense).number_format = '#,##0.00'
    ws.cell(row=summary_row + 2, column=1, value='Net Balance').font   = Font(bold=True)
    ws.cell(row=summary_row + 2, column=2, value=total_income - total_expense).number_format = '#,##0.00'

    buf = BytesIO()
    wb.save(buf)
    fname = 'spim_expenses_' + timezone.localtime().strftime('%Y-%m-%d_%H%M%S') + '.xlsx'
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{fname}"'
    return resp


@login_required
def category_list(request):
    return redirect('categories:expense_list')

@login_required
def delete_category(request, pk):
    c = get_object_or_404(Category, pk=pk, admin_id=get_admin_id(request.user))
    if request.method == 'POST':
        c.delete()
        messages.success(request, "Category removed.")
    return redirect('expenses:categories')
