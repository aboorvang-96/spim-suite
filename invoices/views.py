from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Invoice
from .forms import InvoiceForm, ItemFormSet

@login_required
def invoice_list(request):
    status = request.GET.get('status', '')
    qs     = Invoice.objects.all() if request.user.is_admin else Invoice.objects.filter(created_by=request.user)
    if status:
        qs = qs.filter(status=status)
    return render(request, 'invoices/list.html', {
        'invoices': qs.select_related('client'), 'status_filter': status
    })

@login_required
def invoice_detail(request, pk):
    return render(request, 'invoices/detail.html', {'invoice': get_object_or_404(Invoice, pk=pk)})

@login_required
def add_invoice(request):
    form    = InvoiceForm(request.POST or None)
    formset = ItemFormSet(request.POST or None)
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        inv = form.save(commit=False)
        inv.created_by = request.user
        inv.save()
        formset.instance = inv
        formset.save()
        messages.success(request, 'Invoice ' + inv.invoice_number + ' created.')
        return redirect('invoices:detail', pk=inv.pk)
    return render(request, 'invoices/form.html', {'form': form, 'formset': formset, 'title': 'New Invoice'})

@login_required
def edit_invoice(request, pk):
    inv     = get_object_or_404(Invoice, pk=pk)
    form    = InvoiceForm(request.POST or None, instance=inv)
    formset = ItemFormSet(request.POST or None, instance=inv)
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, "Invoice updated.")
        return redirect('invoices:detail', pk=inv.pk)
    return render(request, 'invoices/form.html', {'form': form, 'formset': formset, 'title': 'Edit Invoice', 'obj': inv})

@login_required
def delete_invoice(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        inv.delete()
        messages.success(request, "Deleted.")
    return redirect('invoices:list')

@login_required
def mark_paid(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        inv.status = 'paid'
        inv.save()
        messages.success(request, "Marked as paid.")
    return redirect('invoices:detail', pk=pk)
