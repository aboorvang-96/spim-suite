from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from .models import ExpenseCategory, IncomeCategory
from .forms import ExpenseCategoryForm, IncomeCategoryForm
from accounts.views import is_admin_user, get_admin_id
from finance.models import Transaction as FinanceTransaction

@login_required
def expense_category_list(request):
    admin_id = get_admin_id(request.user)
    expense_cats = ExpenseCategory.objects.filter(created_by__admin_id=admin_id)
    income_cats = IncomeCategory.objects.filter(created_by__admin_id=admin_id)

    # Process categories to add stats and type info
    all_categories = []

    for cat in expense_cats:
        cat.cat_type = 'expense'
        txns = FinanceTransaction.objects.filter(
            type='expense',
            category__name__iexact=cat.name,
            admin_id=admin_id,
        )
        cat.transaction_count = txns.count()
        cat.total_amount      = txns.aggregate(total=Sum('amount'))['total'] or 0
        all_categories.append(cat)
        
    for cat in income_cats:
        cat.cat_type = 'income'
        if hasattr(cat, 'incomes'):
            cat.transaction_count = cat.incomes.count()
            cat.total_amount = cat.incomes.aggregate(total=Sum('amount'))['total'] or 0
        else:
            cat.transaction_count = 0
            cat.total_amount = 0
        all_categories.append(cat)
        
    # Sort by name
    all_categories.sort(key=lambda x: x.name)
    
    return render(request, 'categories/categories_list.html', {'all_categories': all_categories})


@login_required
def expense_category_add(request):
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.created_by = request.user
            cat.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'id': cat.id, 'name': cat.name})
            messages.success(request, f'Category "{cat.name}" created successfully.')
            return redirect('categories:expense_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseCategoryForm()
    return render(request, 'categories/category_form.html', {'form': form, 'title': 'Add Expense Category', 'type': 'expense'})


@login_required
def expense_category_edit(request, pk):
    admin_id = get_admin_id(request.user)
    category = get_object_or_404(ExpenseCategory, pk=pk, created_by__admin_id=admin_id)
        
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return redirect('categories:expense_list')
    else:
        form = ExpenseCategoryForm(instance=category)
    return render(request, 'categories/category_form.html', {'form': form, 'title': 'Edit Expense Category', 'type': 'expense'})


@login_required
def expense_category_delete(request, pk):
    admin_id = get_admin_id(request.user)
    category = get_object_or_404(ExpenseCategory, pk=pk, created_by__admin_id=admin_id)
        
    if request.method == 'POST':
        name = category.name
        category.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, f'Category "{name}" deleted successfully.')
        return redirect('categories:expense_list')
    return render(request, 'categories/confirm_delete.html', {'object': category, 'type': 'expense'})


@login_required
def income_category_list(request):
    return redirect('categories:expense_list')


@login_required
def income_category_add(request):
    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.created_by = request.user
            cat.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'id': cat.id, 'name': cat.name})
            messages.success(request, f'Category "{cat.name}" created successfully.')
            return redirect('categories:income_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = IncomeCategoryForm()
    return render(request, 'categories/category_form.html', {'form': form, 'title': 'Add Income Category', 'type': 'income'})


@login_required
def income_category_edit(request, pk):
    admin_id = get_admin_id(request.user)
    category = get_object_or_404(IncomeCategory, pk=pk, created_by__admin_id=admin_id)
        
    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return redirect('categories:income_list')
    else:
        form = IncomeCategoryForm(instance=category)
    return render(request, 'categories/category_form.html', {'form': form, 'title': 'Edit Income Category', 'type': 'income'})


@login_required
def income_category_delete(request, pk):
    admin_id = get_admin_id(request.user)
    category = get_object_or_404(IncomeCategory, pk=pk, created_by__admin_id=admin_id)
        
    if request.method == 'POST':
        name = category.name
        category.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, f'Category "{name}" removed successfully.')
        return redirect('categories:income_list')
    return render(request, 'categories/confirm_delete.html', {'object': category, 'type': 'income'})
