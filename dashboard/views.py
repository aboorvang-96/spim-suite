from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from finance.models import Transaction
from projects.models import Project
from invoices.models import Invoice
from dateutil.relativedelta import relativedelta
import json

@login_required
def index(request):
    user  = request.user
    today = timezone.now().date()

    txns     = Transaction.objects.all() if user.is_admin else Transaction.objects.filter(user=user)
    projects = Project.objects.all()     if user.is_admin else Project.objects.filter(owner=user)
    invoices = Invoice.objects.all()     if user.is_admin else Invoice.objects.filter(created_by=user)

    total_income  = txns.filter(type='income').aggregate(t=Sum('amount'))['t']  or 0
    total_expense = txns.filter(type='expense').aggregate(t=Sum('amount'))['t'] or 0

    chart = []
    for i in range(5, -1, -1):
        ms  = today.replace(day=1) - relativedelta(months=i)
        me  = ms + relativedelta(months=1)
        inc = txns.filter(type='income',  date__gte=ms, date__lt=me).aggregate(t=Sum('amount'))['t'] or 0
        exp = txns.filter(type='expense', date__gte=ms, date__lt=me).aggregate(t=Sum('amount'))['t'] or 0
        chart.append({'month': ms.strftime('%b %y'), 'income': float(inc), 'expense': float(exp)})

    return render(request, 'dashboard/index.html', {
        'balance':          total_income - total_expense,
        'total_income':     total_income,
        'total_expense':    total_expense,
        'active_projects':  projects.filter(status='active').count(),
        'pending_invoices': invoices.filter(status__in=['sent','draft']).count(),
        'overdue_invoices': invoices.filter(status='overdue').count(),
        'recent_txns':      txns.select_related('category').order_by('-date','-created_at')[:8],
        'chart_data':       json.dumps(chart),
    })
