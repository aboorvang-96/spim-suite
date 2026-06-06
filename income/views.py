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
        
    # Filters
    category_id   = request.GET.get('category', '')
    date_from     = request.GET.get('date_from', '')
    date_to       = request.GET.get('date_to', '')
    search        = request.GET.get('search', '')
    amount_min    = request.GET.get('amount_min', '')
    amount_max    = request.GET.get('amount_max', '')
    month         = request.GET.get('month', '')
    account       = request.GET.get('account', '')
    income_source = request.GET.get('income_source', '')

    if category_id:   incomes = incomes.filter(category_id=category_id)
    if date_from:     incomes = incomes.filter(date__gte=date_from)
    if date_to:       incomes = incomes.filter(date__lte=date_to)
    if search:        incomes = incomes.filter(Q(title__icontains=search) | Q(source__icontains=search) | Q(description__icontains=search))
    if amount_min:    incomes = incomes.filter(amount__gte=amount_min)
    if amount_max:    incomes = incomes.filter(amount__lte=amount_max)
    if month:         incomes = incomes.filter(date__startswith=month)
    if account:       incomes = incomes.filter(payment_mode__icontains=account)
    if income_source: incomes = incomes.filter(payment_by__icontains=income_source)

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
    accounts_grouped = _group_incomes_by_account(incomes_list)
    sites_grouped    = _group_incomes_by_site(incomes_list, request.user)

    return render(request, 'income/list.html', {
        'incomes':          incomes_list,
        'accounts_grouped': accounts_grouped,
        'sites_grouped':    sites_grouped,
        'categories':       categories,
        'total':            total,
        'count':            count,
        'average':          average,
        'total_balance':    sum(c['balance'] for c in balance_combos),
        'filters': {
            'category': category_id, 'date_from': date_from, 'date_to': date_to,
            'search': search, 'amount_min': amount_min, 'amount_max': amount_max,
            'month': month, 'account': account, 'income_source': income_source,
        },
        'is_admin':            is_admin,
        'location_sites_json': _location_sites_json(request.user),
        'income_sources_json': _shared_sources_json(request.user),
        'accounts_json':       _shared_accounts_json(request.user),
        'balance_data':        balance_combos,
    })


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


def _group_incomes_by_site(incomes, user):
    """
    Site-based card view (Income/Expense restructure).

    Groups incomes by `location_site` (case-insensitive). For each site
    returns a dict with credit (sum of Income amounts for that site),
    debit (sum of expense Transaction amounts for the SAME site), and
    balance = credit - debit. The expense lookup is scoped to the same
    admin_id (tenant) so cross-tenant data never bleeds in.

    Sort order: most recent activity first (latest income date).
    """
    import datetime as _dt
    from decimal import Decimal as _D
    from accounts.views import get_admin_id, is_admin_user
    admin_id = get_admin_id(user)

    # Build the site → debit map in a single sweep over expense Transactions
    # for this tenant. Empty/None location_site rows are folded into the
    # "(No Site)" bucket so admins can still see them.
    #
    # Defensive: the cross-module expense query is wrapped in try/except so
    # a transient Transaction-side failure (e.g. mid-deploy when one
    # migration has run and the other hasn't) degrades to an empty debit
    # map instead of 500-ing the Income page. `.only(...)` skips the new
    # `expense_category` column entirely so the SELECT works even if the
    # column hasn't been added yet on the Transaction table.
    debit_map = {}
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
    except Exception:
        debit_map = {}

    groups = {}
    for i in incomes:
        site = (getattr(i, 'location_site', None) or '').strip()
        key  = site.lower()
        g = groups.get(key)
        if g is None:
            g = {
                'site':         site or '(No Site)',
                'site_key':     key,
                'credit':       _D('0'),
                'debit':        debit_map.get(key, _D('0')),
                'balance':      _D('0'),
                'count':        0,
                'latest_date':  i.date,
                'transactions': [],
            }
            groups[key] = g
        g['credit'] += (i.amount or _D('0'))
        g['count']  += 1
        g['transactions'].append(i)
        if i.date and (g['latest_date'] is None or i.date > g['latest_date']):
            g['latest_date'] = i.date
            g['site']        = site or '(No Site)'

    # Also surface sites that have expenses but zero income — admin still
    # needs to see those in the site card list.
    for key, debit in debit_map.items():
        if key in groups:
            continue
        # Re-derive a display name from the most recent expense row of this site
        site_disp = ''
        latest = expense_qs.filter(location_site__iexact=key).order_by('-date').first()
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

    for g in groups.values():
        g['balance'] = g['credit'] - g['debit']
        g['transactions'].sort(
            key=lambda x: (x.date or _dt.date.min),
            reverse=True,
        )

    return sorted(
        groups.values(),
        key=lambda g: (g['latest_date'] or _dt.date.min),
        reverse=True,
    )


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

    form = IncomeForm(request.user, request.POST)
    ajax = _is_ajax(request)

    if form.is_valid():
        income = form.save(commit=False)
        income.user     = request.user
        income.admin_id = get_admin_id(request.user)
        income.save()
        if income.location_site:
            admin_id = get_admin_id(request.user)
            name = income.location_site.strip()
            if name and not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
                LocationSite.objects.create(admin_id=admin_id, name=name, created_by=request.user)
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


@login_required
def income_edit(request, pk):
    if is_admin_user(request.user):
        income = get_object_or_404(Income, pk=pk, admin_id=get_admin_id(request.user))
    else:
        income = get_object_or_404(Income, pk=pk, user=request.user)

    # Modal-only flow: GET bounces to the list.
    if request.method != 'POST':
        return redirect('income:list')

    form = IncomeForm(request.user, request.POST, instance=income)
    ajax = _is_ajax(request)

    if form.is_valid():
        income = form.save(commit=False)
        income.admin_id = get_admin_id(request.user)
        income.save()
        if income.location_site:
            admin_id = get_admin_id(request.user)
            name = income.location_site.strip()
            if name and not LocationSite.objects.filter(admin_id=admin_id, name__iexact=name).exists():
                LocationSite.objects.create(admin_id=admin_id, name=name, created_by=request.user)
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
