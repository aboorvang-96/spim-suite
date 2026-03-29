from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from .models import Transaction, Category
from .forms import TransactionForm, CategoryForm

@login_required
def transaction_list(request):
    qs      = Transaction.objects.filter(user=request.user).select_related('category')
    tx_type = request.GET.get('type', '')
    cat_id  = request.GET.get('category', '')
    month   = request.GET.get('month', '')
    if tx_type: qs = qs.filter(type=tx_type)
    if cat_id:  qs = qs.filter(category_id=cat_id)
    if month:   qs = qs.filter(date__startswith=month)
    total_income  = qs.filter(type='income').aggregate(t=Sum('amount'))['t']  or 0
    total_expense = qs.filter(type='expense').aggregate(t=Sum('amount'))['t'] or 0
    return render(request, 'finance/list.html', {
        'transactions': qs[:200],
        'total_income':  total_income,
        'total_expense': total_expense,
        'balance':       total_income - total_expense,
        'categories':    Category.objects.filter(created_by=request.user),
        'filters':       {'type': tx_type, 'category': cat_id, 'month': month},
    })

@login_required
def add_transaction(request):
    form = TransactionForm(request.user, request.POST or None, initial={'date': timezone.now().date()})
    if request.method == 'POST' and form.is_valid():
        t = form.save(commit=False)
        t.user = request.user
        t.save()
        messages.success(request, "Transaction recorded.")
        return redirect('finance:list')
    return render(request, 'finance/form.html', {'form': form, 'title': 'Add Transaction'})

@login_required
def edit_transaction(request, pk):
    t    = get_object_or_404(Transaction, pk=pk, user=request.user)
    form = TransactionForm(request.user, request.POST or None, instance=t)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Transaction updated.")
        return redirect('finance:list')
    return render(request, 'finance/form.html', {'form': form, 'title': 'Edit Transaction', 'obj': t})

@login_required
def delete_transaction(request, pk):
    t = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        t.delete()
        messages.success(request, "Deleted.")
    return redirect('finance:list')

@login_required
def category_list(request):
    cats = Category.objects.filter(created_by=request.user)
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        c = form.save(commit=False)
        c.created_by = request.user
        c.save()
        messages.success(request, "Category added.")
        return redirect('finance:categories')
    return render(request, 'finance/categories.html', {'categories': cats, 'form': form})

@login_required
def delete_category(request, pk):
    c = get_object_or_404(Category, pk=pk, created_by=request.user)
    if request.method == 'POST':
        c.delete()
        messages.success(request, "Category removed.")
    return redirect('finance:categories')
