from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Project, Task
from .forms import ProjectForm, TaskForm

@login_required
def project_list(request):
    qs = Project.objects.all() if request.user.is_admin else Project.objects.filter(owner=request.user)
    return render(request, 'projects/list.html', {'projects': qs.select_related('client','owner')})

@login_required
def project_detail(request, pk):
    p = get_object_or_404(Project, pk=pk)
    return render(request, 'projects/detail.html', {
        'project': p, 'tasks': p.tasks.select_related('assigned_to'), 'task_form': TaskForm()
    })

@login_required
def add_project(request):
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False)
        p.owner = request.user
        p.save()
        messages.success(request, "Project created.")
        return redirect('projects:detail', pk=p.pk)
    return render(request, 'projects/form.html', {'form': form, 'title': 'New Project'})

@login_required
def edit_project(request, pk):
    p    = get_object_or_404(Project, pk=pk)
    form = ProjectForm(request.POST or None, instance=p)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Project updated.")
        return redirect('projects:detail', pk=p.pk)
    return render(request, 'projects/form.html', {'form': form, 'title': 'Edit Project', 'obj': p})

@login_required
def delete_project(request, pk):
    p = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        p.delete()
        messages.success(request, "Deleted.")
    return redirect('projects:list')

@login_required
def add_task(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    form    = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        t = form.save(commit=False)
        t.project = project
        t.save()
        messages.success(request, "Task added.")
    return redirect('projects:detail', pk=project_pk)

@login_required
def update_task_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    ns   = request.POST.get('status')
    if ns in dict(Task.STATUS):
        task.status = ns
        task.save()
    return redirect('projects:detail', pk=task.project_id)

@login_required
def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk)
    pid  = task.project_id
    if request.method == 'POST':
        task.delete()
        messages.success(request, "Task removed.")
    return redirect('projects:detail', pk=pid)
