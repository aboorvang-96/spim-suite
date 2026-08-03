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


def _dynamic_site_options(admin_id, month_yyyy_mm):
    """Sites to surface in the Expense-page site filter dropdown.

    Union of, restricted to the currently-viewed month:
      * projects.Site referenced by AttendanceRecord.site_ref
      * projects.Site referenced by projects.WorkLog.site
      * projects.Site referenced by finance.Transaction.site
      * distinct non-empty Transaction.location_site strings (legacy)

    Returns a list of {'id': <site_id or None>, 'name': <display>, 'kind':
    'fk'|'legacy'} sorted by name. FK entries preferred when the same name
    appears both as an FK and a legacy string (deduped on lowercase name).
    """
    if not month_yyyy_mm:
        return []
    from projects.models import Site
    site_ids = set()

    try:
        from attendance.models import AttendanceRecord
        site_ids.update(AttendanceRecord.objects
                        .filter(admin_id=admin_id,
                                date__startswith=month_yyyy_mm,
                                site_ref__isnull=False)
                        .values_list('site_ref_id', flat=True).distinct())
    except Exception:  # noqa: BLE001
        pass

    try:
        from projects.models import WorkLog
        site_ids.update(WorkLog.objects
                        .filter(admin_id=admin_id,
                                date__startswith=month_yyyy_mm,
                                site__isnull=False)
                        .values_list('site_id', flat=True).distinct())
    except Exception:  # noqa: BLE001
        pass

    site_ids.update(Transaction.objects
                    .filter(admin_id=admin_id,
                            date__startswith=month_yyyy_mm,
                            site__isnull=False)
                    .values_list('site_id', flat=True).distinct())

    fk_sites = list(Site.objects.filter(admin_id=admin_id, id__in=site_ids)
                    .values('id', 'name'))
    seen_lower = {(s['name'] or '').strip().lower() for s in fk_sites}

    legacy_names = (Transaction.objects
                    .filter(admin_id=admin_id, date__startswith=month_yyyy_mm)
                    .exclude(location_site__isnull=True)
                    .exclude(location_site='')
                    .values_list('location_site', flat=True).distinct())
    legacy_list = []
    for name in legacy_names:
        key = (name or '').strip().lower()
        if not key or key in seen_lower:
            continue
        seen_lower.add(key)
        legacy_list.append({'id': None, 'name': name.strip(), 'kind': 'legacy'})

    fk_list = [{'id': s['id'], 'name': s['name'], 'kind': 'fk'} for s in fk_sites]
    return sorted(fk_list + legacy_list,
                  key=lambda o: (o['name'] or '').strip().lower())


def _salary_breakdown_for(txs):
    """Given a list of expense Transactions (already scoped to one site or
    the whole page), return the salary breakdown structure the template
    renders under each site card:

        {
          'employees': [
             {'name': 'Rajkumar', 'total': Decimal,
              'attendance_rows': [{'date': ..., 'status': ..., 'amount': ...}],
              'payslip_rows':    [{'cycle_label': 'YYYY-MM', 'amount': ...}],
             }, ...
          ],
          'grand_total': Decimal,
        }
    """
    from decimal import Decimal as _D
    emp_map = {}
    for t in txs:
        src = getattr(t, 'source', '') or ''
        if src not in ('salary_attendance', 'salary_payslip'):
            continue
        emp = t.employee
        key = (emp.pk if emp else 0, getattr(emp, 'name', '') or 'Unknown')
        e = emp_map.setdefault(key, {
            'name':            key[1],
            'total':           _D('0'),
            'attendance_rows': [],
            'payslip_rows':    [],
        })
        e['total'] += (t.amount or _D('0'))
        if src == 'salary_attendance':
            e['attendance_rows'].append({
                'date':   t.date,
                'status': (t.attendance_record.status
                          if t.attendance_record_id and t.attendance_record else ''),
                'amount': t.amount,
            })
        else:  # salary_payslip
            # Monthly rows — pull cycle label from reference "SAL-<pk>-YYYY-MM"
            ref = t.reference or ''
            cycle = ref.split('-', 2)[-1] if ref.count('-') >= 2 else str(t.date)
            e['payslip_rows'].append({'cycle_label': cycle, 'amount': t.amount})
    for e in emp_map.values():
        e['attendance_rows'].sort(key=lambda r: r['date'] or datetime.date.min)
        e['payslip_rows'].sort(key=lambda r: r['cycle_label'])
    return {
        'employees':   sorted(emp_map.values(), key=lambda e: e['name']),
        'grand_total': sum((e['total'] for e in emp_map.values()), _D('0')),
    }


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

@login_required
def transaction_list(request):
    admin_id = get_admin_id(request.user)
    qs = Transaction.objects.filter(admin_id=admin_id, type='expense').select_related('category', 'branch')

    # ── Server-side filter params (applied on initial load / URL navigation) ──
    cat_id        = request.GET.get('category', '')
    month         = request.GET.get('month', '')
    search        = request.GET.get('search', '')
    account       = request.GET.get('account', '')
    income_source = request.GET.get('income_source', '')
    site_filter   = request.GET.get('site', '')  # '' | site_id | 'UNASSIGNED'

    if cat_id:        qs = qs.filter(category_id=cat_id)
    if month:         qs = qs.filter(date__startswith=month)
    if search:        qs = qs.filter(
        Q(description__icontains=search) | Q(vendor__icontains=search) | Q(reference__icontains=search)
    )
    if account:       qs = qs.filter(payment_mode__icontains=account)
    if income_source: qs = qs.filter(income_source__icontains=income_source)
    if site_filter:
        if site_filter == 'UNASSIGNED':
            qs = qs.filter(site__isnull=True).filter(
                Q(location_site__isnull=True) | Q(location_site='')
            )
        else:
            try:
                sid = int(site_filter)
                # Match on FK, OR on legacy string equal to that site's name
                # (case-insensitive) so rows created before FK adoption still
                # surface under the right filter.
                from projects.models import Site as _S
                site_obj = _S.objects.filter(admin_id=admin_id, id=sid).first()
                if site_obj:
                    qs = qs.filter(
                        Q(site_id=sid) | Q(location_site__iexact=site_obj.name)
                    )
                else:
                    qs = qs.filter(site_id=sid)
            except (ValueError, TypeError):
                pass

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

    # Source badge (Income/Expense restructure). Colors per spec:
    # Manual=gray, Salary-Attendance=blue, Salary-Payslip=purple,
    # Material=green, Other=default.
    _BADGE = {
        'manual':            ('Manual',              'src-manual'),
        'salary_attendance': ('Salary — Attendance', 'src-sal-att'),
        'salary_payslip':    ('Salary — Payslip',    'src-sal-pay'),
        'material':          ('Material',            'src-material'),
        'other':             ('Other',               'src-other'),
    }
    for t in transactions_list:
        src = (t.income_source or '').strip().lower()
        acc = (t.payment_mode or '').strip().lower()
        t.combo_data = combo_map.get((src, acc)) if (src and acc) else None
        src_code = getattr(t, 'source', '') or 'manual'
        label, klass = _BADGE.get(src_code, ('Manual', 'src-manual'))
        t.source_badge_label = label
        t.source_badge_class = klass

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
    # Attach salary breakdown per site card (post-restructure UI).
    for g in sites_grouped:
        g['salary_breakdown'] = _salary_breakdown_for(g.get('transactions') or [])

    # Site dropdown options — dynamic to the currently-viewed month. Falls
    # back to the current month when no month filter is set so the dropdown
    # is always populated with something useful.
    month_for_options = month or timezone.now().strftime('%Y-%m')
    site_options = _dynamic_site_options(admin_id, month_for_options)

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
        'filters': {
            'category': cat_id, 'month': month, 'search': search,
            'account': account, 'income_source': income_source,
            'site': site_filter,
        },
        'site_options': site_options,
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
        # Manual add flow ALWAYS books as source='manual'. Never allow the
        # 'salary_attendance' source through this endpoint — that's reserved
        # for attendance/signals.py. Any other user-submitted value is
        # coerced to 'manual' too.
        t.source = 'manual'
        # Mirror the picked Site's name into the legacy `location_site`
        # CharField so the existing string-grouped card view stays
        # consistent across old + new rows.
        if getattr(t, 'site_id', None):
            try:
                if t.site and t.site.name:
                    t.location_site = t.site.name
            except Exception:  # noqa: BLE001
                pass
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
        # Preserve the original source — the modal never surfaces `source`
        # so an edit should not silently reclassify a salary_attendance /
        # salary_payslip row as manual. Fall back to 'manual' only when the
        # row genuinely has no source yet (pre-0010 legacy data).
        if not getattr(obj, 'source', ''):
            obj.source = 'manual'
        if getattr(obj, 'site_id', None):
            try:
                if obj.site and obj.site.name:
                    obj.location_site = obj.site.name
            except Exception:  # noqa: BLE001
                pass
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
