from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.http import JsonResponse
from finance.models import Transaction
from income.models import Income
from projects.models import Project
from invoices.models import Invoice
from accounts.views import get_admin_id
from dateutil.relativedelta import relativedelta
from .models import CompanySettings
from .forms import CompanySettingsForm
import json

@login_required
def index(request):
    user     = request.user
    today    = timezone.now().date()
    admin_id = get_admin_id(user)

    if user.is_admin:
        txns      = Transaction.objects.filter(admin_id=admin_id)
        income_qs = Income.objects.filter(admin_id=admin_id)
        projects  = Project.objects.filter(owner__admin_id=admin_id)
        invoices  = Invoice.objects.filter(created_by__admin_id=admin_id)
    else:
        txns      = Transaction.objects.filter(user=user)
        income_qs = Income.objects.filter(user=user)
        projects  = Project.objects.filter(owner=user)
        invoices  = Invoice.objects.filter(created_by=user)

    # Total income = Income model only (canonical income source, matches Reports)
    total_income  = income_qs.aggregate(t=Sum('amount'))['t'] or 0
    total_expense = txns.filter(type='expense').aggregate(t=Sum('amount'))['t'] or 0

    chart = []
    for i in range(5, -1, -1):
        ms      = today.replace(day=1) - relativedelta(months=i)
        me      = ms + relativedelta(months=1)
        inc = income_qs.filter(date__gte=ms, date__lt=me).aggregate(t=Sum('amount'))['t'] or 0
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
        'company':          CompanySettings.get_settings(admin_id),
    })


@login_required
def company_settings(request):
    admin_id = get_admin_id(request.user)
    instance = CompanySettings.get_settings(admin_id)

    if request.method == 'POST':
        form = CompanySettingsForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.admin_id    = admin_id
            obj.modified_by = request.user
            obj.save()
            messages.success(request, 'Company details updated successfully.')
            return redirect('dashboard:index')
    else:
        form = CompanySettingsForm(instance=instance)

    return render(request, 'dashboard/company_settings.html', {
        'form':    form,
        'company': instance,
    })


@login_required
def company_settings_json(request):
    admin_id = get_admin_id(request.user)
    company = CompanySettings.get_settings(admin_id)
    if not company:
        return JsonResponse({
            'name': '',
            'address': '',
            'contact_number': '',
            'gst_number': '',
            'email': '',
        })
    return JsonResponse({
        'name':              company.name or '',
        'address':           company.address or '',
        'contact_number':    company.contact_number or '',
        'gst_number':        company.gst_number or '',
        'email':             company.email or '',
        'managing_director': company.managing_director or '',
    })
