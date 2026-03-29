from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import ExpenseCategory, IncomeCategory
from .forms import ExpenseCategoryForm, IncomeCategoryForm


from accounts.views import is_admin_user


@login_required
def expense_category_list(request):
    if is_admin_user(request.user):
        categories = ExpenseCategory.objects.all()
    else:
        categories = ExpenseCategory.objects.filter(created_by=request.user)
    return render(request, 'categories/expense_list.html', {'categories': categories, 'type': 'expense'})


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
    if is_admin_user(request.user):
        category = get_object_or_404(ExpenseCategory, pk=pk)
    else:
        category = get_object_or_404(ExpenseCategory, pk=pk, created_by=request.user)
        
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return redirect('categories:expense_list')
    else:
        form = ExpenseCategoryForm(instance=category)
    return render(request, 'categories/category_form.html', {'form': form, 'title': 'Edit Expense Category', 'type': 'expense'})


@login_required
def expense_category_delete(request, pk):
    if is_admin_user(request.user):
        category = get_object_or_404(ExpenseCategory, pk=pk)
    else:
        category = get_object_or_404(ExpenseCategory, pk=pk, created_by=request.user)
        
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
    if is_admin_user(request.user):
        categories = IncomeCategory.objects.all()
    else:
        categories = IncomeCategory.objects.filter(created_by=request.user)
    return render(request, 'categories/income_list.html', {'categories': categories, 'type': 'income'})


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
    if is_admin_user(request.user):
        category = get_object_or_404(IncomeCategory, pk=pk)
    else:
        category = get_object_or_404(IncomeCategory, pk=pk, created_by=request.user)
        
    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully.')
            return redirect('categories:income_list')
    else:
        form = IncomeCategoryForm(instance=category)
    return render(request, 'categories/category_form.html', {'form': form, 'title': 'Edit Income Category', 'type': 'income'})


@login_required
def income_category_delete(request, pk):
    if is_admin_user(request.user):
        category = get_object_or_404(IncomeCategory, pk=pk)
    else:
        category = get_object_or_404(IncomeCategory, pk=pk, created_by=request.user)
        
    if request.method == 'POST':
        name = category.name
        category.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, f'Category "{name}" deleted successfully.')
        return redirect('categories:income_list')
    return render(request, 'categories/confirm_delete.html', {'object': category, 'type': 'income'})
