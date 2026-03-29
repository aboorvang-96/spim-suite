from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Income
from .forms import IncomeForm


from accounts.views import is_admin_user


@login_required
def income_list(request):
    if is_admin_user(request.user):
        incomes = Income.objects.select_related('category', 'user').all()
    else:
        incomes = Income.objects.filter(user=request.user).select_related('category')
        
    # Filters
    category_id = request.GET.get('category')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search')

    if category_id:
        incomes = incomes.filter(category_id=category_id)
    if date_from:
        incomes = incomes.filter(date__gte=date_from)
    if date_to:
        incomes = incomes.filter(date__lte=date_to)
    if search:
        incomes = incomes.filter(Q(title__icontains=search) | Q(source__icontains=search) | Q(description__icontains=search))

    from categories.models import IncomeCategory
    categories = IncomeCategory.objects.filter(created_by=request.user)
    total = sum(i.amount for i in incomes)

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
        } for i in incomes]
        return JsonResponse({'incomes': data, 'total': str(total)})

    return render(request, 'income/list.html', {
        'incomes': incomes,
        'categories': categories,
        'total': total,
        'filters': {'category': category_id, 'date_from': date_from, 'date_to': date_to, 'search': search},
        'is_admin': is_admin_user(request.user),
    })


@login_required
def income_add(request):
    if request.method == 'POST':
        form = IncomeForm(request.user, request.POST)
        if form.is_valid():
            income = form.save(commit=False)
            income.user = request.user
            income.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'income': {
                        'id': income.id,
                        'title': income.title,
                        'amount': str(income.amount),
                        'date': str(income.date),
                        'category': income.category.name if income.category else 'Uncategorized',
                    }
                })
            messages.success(request, f'Income "{income.title}" added successfully.')
            return redirect('income:list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = IncomeForm(request.user)
    return render(request, 'income/form.html', {'form': form, 'title': 'Add Income', 'action': 'Add'})


@login_required
def income_edit(request, pk):
    if is_admin_user(request.user):
        income = get_object_or_404(Income, pk=pk)
    else:
        income = get_object_or_404(Income, pk=pk, user=request.user)
        
    if request.method == 'POST':
        form = IncomeForm(request.user, request.POST, instance=income)
        if form.is_valid():
            income = form.save()
            messages.success(request, f'Income "{income.title}" updated.')
            return redirect('income:list')
    else:
        form = IncomeForm(request.user, instance=income)
    return render(request, 'income/form.html', {'form': form, 'income': income, 'title': 'Edit Income', 'action': 'Update'})


@login_required
def income_delete(request, pk):
    if is_admin_user(request.user):
        income = get_object_or_404(Income, pk=pk)
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
