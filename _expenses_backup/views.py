from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Expense, Receipt
from .forms import ExpenseForm, ReceiptUploadForm
import os


from accounts.views import is_admin_user


@login_required
def expense_list(request):
    if is_admin_user(request.user):
        expenses = Expense.objects.select_related('category', 'user').all()
    else:
        expenses = Expense.objects.filter(user=request.user).select_related('category')
    
    # Filters
    category_id = request.GET.get('category')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search')

    if category_id:
        expenses = expenses.filter(category_id=category_id)
    if status:
        expenses = expenses.filter(status=status)
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    if search:
        expenses = expenses.filter(Q(title__icontains=search) | Q(description__icontains=search))

    from categories.models import ExpenseCategory
    categories = ExpenseCategory.objects.filter(created_by=request.user)
    total = sum(e.amount for e in expenses)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = [{
            'id': e.id,
            'title': e.title,
            'amount': str(e.amount),
            'category': e.category.name if e.category else 'Uncategorized',
            'user': e.user.username if is_admin_user(request.user) else None,
            'date': str(e.date),
            'status': e.status,
            'payment_method': e.get_payment_method_display(),
        } for e in expenses]
        return JsonResponse({'expenses': data, 'total': str(total)})

    return render(request, 'expenses/list.html', {
        'expenses': expenses,
        'categories': categories,
        'total': total,
        'filters': {'category': category_id, 'status': status, 'date_from': date_from, 'date_to': date_to, 'search': search},
        'is_admin': is_admin_user(request.user),
    })


@login_required
def expense_add(request):
    if request.method == 'POST':
        form = ExpenseForm(request.user, request.POST)
        receipt_form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            # Handle receipt upload
            receipt_file = request.FILES.get('file')
            if receipt_file:
                ext = os.path.splitext(receipt_file.name)[1].lower().lstrip('.')
                if ext in ['jpg', 'jpeg', 'png', 'pdf']:
                    file_type = ext if ext != 'jpeg' else 'jpg'
                    Receipt.objects.create(expense=expense, file=receipt_file, file_type=file_type)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'expense': {
                        'id': expense.id,
                        'title': expense.title,
                        'amount': str(expense.amount),
                        'date': str(expense.date),
                        'category': expense.category.name if expense.category else 'Uncategorized',
                        'status': expense.status,
                    }
                })
            messages.success(request, f'Expense "{expense.title}" added successfully.')
            return redirect('expenses:list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ExpenseForm(request.user)
        receipt_form = ReceiptUploadForm()
    return render(request, 'expenses/form.html', {
        'form': form,
        'receipt_form': receipt_form,
        'title': 'Add Expense',
        'action': 'Add',
    })


@login_required
def expense_edit(request, pk):
    if is_admin_user(request.user):
        expense = get_object_or_404(Expense, pk=pk)
    else:
        expense = get_object_or_404(Expense, pk=pk, user=request.user)
        
    if request.method == 'POST':
        form = ExpenseForm(request.user, request.POST, instance=expense)
        receipt_form = ReceiptUploadForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save()
            receipt_file = request.FILES.get('file')
            if receipt_file:
                ext = os.path.splitext(receipt_file.name)[1].lower().lstrip('.')
                if ext in ['jpg', 'jpeg', 'png', 'pdf']:
                    file_type = ext if ext != 'jpeg' else 'jpg'
                    Receipt.objects.create(expense=expense, file=receipt_file, file_type=file_type)
            messages.success(request, f'Expense "{expense.title}" updated.')
            return redirect('expenses:list')
    else:
        form = ExpenseForm(request.user, instance=expense)
        receipt_form = ReceiptUploadForm()
    return render(request, 'expenses/form.html', {
        'form': form,
        'receipt_form': receipt_form,
        'expense': expense,
        'title': 'Edit Expense',
        'action': 'Update',
    })


@login_required
def expense_delete(request, pk):
    if is_admin_user(request.user):
        expense = get_object_or_404(Expense, pk=pk)
    else:
        expense = get_object_or_404(Expense, pk=pk, user=request.user)
        
    if request.method == 'POST':
        title = expense.title
        expense.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, f'Expense "{title}" deleted.')
        return redirect('expenses:list')
    return render(request, 'expenses/confirm_delete.html', {'expense': expense})


@login_required
def expense_detail(request, pk):
    if is_admin_user(request.user):
        expense = get_object_or_404(Expense, pk=pk)
    else:
        expense = get_object_or_404(Expense, pk=pk, user=request.user)
    return render(request, 'expenses/detail.html', {'expense': expense})
