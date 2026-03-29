from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils.decorators import method_decorator
from django.views import View
from datetime import date
from expenses.models import Expense
from income.models import Income
from categories.models import ExpenseCategory, IncomeCategory
import json


@login_required
def api_expenses(request):
    user = request.user
    if request.method == 'GET':
        expenses = Expense.objects.filter(user=user).select_related('category').order_by('-date')[:50]
        data = [{
            'id': e.id,
            'title': e.title,
            'amount': str(e.amount),
            'category': e.category.name if e.category else None,
            'category_color': e.category.color if e.category else '#6366f1',
            'date': str(e.date),
            'description': e.description,
            'payment_method': e.payment_method,
            'status': e.status,
        } for e in expenses]
        return JsonResponse({'success': True, 'expenses': data})
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            from expenses.forms import ExpenseForm
            form = ExpenseForm(user, body)
            if form.is_valid():
                expense = form.save(commit=False)
                expense.user = user
                expense.save()
                return JsonResponse({'success': True, 'id': expense.id, 'title': expense.title, 'amount': str(expense.amount)}, status=201)
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_income(request):
    user = request.user
    if request.method == 'GET':
        incomes = Income.objects.filter(user=user).select_related('category').order_by('-date')[:50]
        data = [{
            'id': i.id,
            'title': i.title,
            'amount': str(i.amount),
            'category': i.category.name if i.category else None,
            'category_color': i.category.color if i.category else '#10b981',
            'date': str(i.date),
            'source': i.source,
            'description': i.description,
            'payment_mode': i.payment_mode,
        } for i in incomes]
        return JsonResponse({'success': True, 'income': data})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_dashboard(request):
    user = request.user
    today = date.today()
    total_income = Income.objects.filter(user=user).aggregate(total=Sum('amount'))['total'] or 0
    total_expense = Expense.objects.filter(user=user).aggregate(total=Sum('amount'))['total'] or 0
    month_income = Income.objects.filter(user=user, date__month=today.month, date__year=today.year).aggregate(total=Sum('amount'))['total'] or 0
    month_expense = Expense.objects.filter(user=user, date__month=today.month, date__year=today.year).aggregate(total=Sum('amount'))['total'] or 0

    return JsonResponse({
        'success': True,
        'total_income': str(total_income),
        'total_expense': str(total_expense),
        'balance': str(total_income - total_expense),
        'month_income': str(month_income),
        'month_expense': str(month_expense),
        'month_balance': str(month_income - month_expense),
    })
