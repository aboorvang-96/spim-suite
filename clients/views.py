from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Client
from .forms import ClientForm

@login_required
def client_list(request):
    q  = request.GET.get('q', '')
    qs = Client.objects.all() if request.user.is_admin else Client.objects.filter(added_by=request.user)
    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(company__icontains=q) | qs.filter(email__icontains=q)
    return render(request, 'clients/list.html', {'clients': qs.distinct(), 'q': q})

@login_required
def client_detail(request, pk):
    qs = Client.objects.all() if request.user.is_admin else Client.objects.filter(added_by=request.user)
    c  = get_object_or_404(qs, pk=pk)
    return render(request, 'clients/detail.html', {'client': c, 'projects': c.projects.all()})

@login_required
def add_client(request):
    form = ClientForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        c = form.save(commit=False)
        c.added_by = request.user
        c.save()
        messages.success(request, "Client added.")
        return redirect('clients:detail', pk=c.pk)
    return render(request, 'clients/form.html', {'form': form, 'title': 'Add Client'})

@login_required
def edit_client(request, pk):
    qs = Client.objects.all() if request.user.is_admin else Client.objects.filter(added_by=request.user)
    c  = get_object_or_404(qs, pk=pk)
    form = ClientForm(request.POST or None, instance=c)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Updated.")
        return redirect('clients:detail', pk=c.pk)
    return render(request, 'clients/form.html', {'form': form, 'title': 'Edit Client', 'obj': c})

@login_required
def delete_client(request, pk):
    qs = Client.objects.all() if request.user.is_admin else Client.objects.filter(added_by=request.user)
    c  = get_object_or_404(qs, pk=pk)
    if request.method == 'POST':
        c.delete()
        messages.success(request, "Deleted.")
    return redirect('clients:list')
