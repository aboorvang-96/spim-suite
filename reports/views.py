from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from finance.models import Transaction, Category
import json

@login_required
def reports_index(request):
    user = request.user
    year = int(request.GET.get('year', timezone.now().year))
    txns = Transaction.objects.filter(date__year=year) if user.is_admin else Transaction.objects.filter(user=user, date__year=year)

    monthly = []
    for m in range(1, 13):
        inc = txns.filter(type='income',  date__month=m).aggregate(t=Sum('amount'))['t'] or 0
        exp = txns.filter(type='expense', date__month=m).aggregate(t=Sum('amount'))['t'] or 0
        monthly.append({'month': m, 'label': str(m).zfill(2) + '/' + str(year), 'income': float(inc), 'expense': float(exp)})

    exp_cats = []
    for cat in Category.objects.filter(type='expense'):
        total = txns.filter(type='expense', category=cat).aggregate(t=Sum('amount'))['t'] or 0
        if total:
            exp_cats.append({'name': cat.name, 'total': float(total), 'color': cat.color})

    total_income  = txns.filter(type='income').aggregate(t=Sum('amount'))['t']  or 0
    total_expense = txns.filter(type='expense').aggregate(t=Sum('amount'))['t'] or 0

    return render(request, 'reports/index.html', {
        'monthly_data':  json.dumps(monthly),
        'category_data': json.dumps(exp_cats),
        'total_income':  total_income,
        'total_expense': total_expense,
        'net':           total_income - total_expense,
        'year':          year,
        'years':         list(range(2022, timezone.now().year + 2)),
    })
