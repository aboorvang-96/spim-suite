from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import LoginForm, RegisterForm

def is_admin_user(user):
    return user.is_authenticated and getattr(user, 'role', 'user') == 'admin'

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard:index')
    return render(request, 'accounts/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Welcome, ' + (user.full_name or user.username) + '!')
        return redirect('dashboard:index')
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    
    success = False
    if request.method == 'POST':
        email = request.POST.get('email')
        # Simple implementation - just show success message
        # In production, you'd send an actual email with a reset link
        success = True
        messages.info(request, f'Password reset instructions sent to {email}')
        return render(request, 'accounts/forgot_password.html', {'success': True, 'email': email})
    
    return render(request, 'accounts/forgot_password.html', {'form': type('Form', (), {'email': type('Field', (), {'value': lambda self: '', 'errors': []})()})()})
