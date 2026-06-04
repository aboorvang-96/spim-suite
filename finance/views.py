from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
import json
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
    values ('source', 'account') keep the original casing from the income record."""
    from income.models import Income
    admin_id = get_admin_id(user)
    income_qs  = Income.objects.filter(admin_id=admin_id)
    expense_qs = Transaction.objects.filter(admin_id=admin_id, type='expense')

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


def _is_ajax(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
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

    if cat_id:        qs = qs.filter(category_id=cat_id)
    if month:         qs = qs.filter(date__startswith=month)
    if search:        qs = qs.filter(
        Q(description__icontains=search) | Q(vendor__icontains=search) | Q(reference__icontains=search)
    )
    if account:       qs = qs.filter(payment_mode__icontains=account)
    if income_source: qs = qs.filter(income_source__icontains=income_source)

    total_expense = qs.aggregate(t=Sum('amount'))['t'] or 0

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
    transactions_list = list(qs[:200])
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

    # Group the filtered transactions by Account for the new
    # one-card-per-account list view. Header summary / filters /
    # add-edit-delete URLs are intentionally unchanged.
    accounts_grouped = _group_expenses_by_account(transactions_list)

    return render(request, 'finance/list.html', {
        'transactions':        transactions_list,
        'transactions_json':   transactions_json,
        'accounts_grouped':    accounts_grouped,
        'total_expense':       total_expense,
        'this_month_expense':  this_month_expense,
        'expense_count':       expense_count,
        'categories':          Category.objects.filter(admin_id=admin_id, type='expense'),
        'filters': {
            'category': cat_id, 'month': month, 'search': search,
            'account': account, 'income_source': income_source,
        },
        'location_sites_json':  _location_sites_json(request.user),
        'income_sources_json':  _shared_sources_json(request.user),
        'accounts_json':        _shared_accounts_json(request.user),
        'balance_data':         balance_combos,
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
