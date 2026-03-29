from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Employee, BankDetail, PFDetail, Salary, Payslip
from .forms import EmployeeForm, BankDetailForm, PFDetailForm, SalaryForm
from datetime import datetime
import json
from django.http import JsonResponse

@login_required
def employee_list(request):
    search_q = request.GET.get('q', '')
    location_f = request.GET.get('location', '')
    site_f = request.GET.get('site', '')
    qs = Employee.objects.filter(created_by=request.user)
    if search_q:
        qs = qs.filter(name__icontains=search_q)
    if location_f:
        qs = qs.filter(location=location_f)
    if site_f:
        qs = qs.filter(site=site_f)
    
    locations = Employee.objects.filter(created_by=request.user).values_list('location', flat=True).distinct().order_by('location')
    sites = Employee.objects.filter(created_by=request.user).values_list('site', flat=True).distinct().order_by('site')
    
    return render(request, 'employees/list.html', {
        'employees': qs.select_related('bank_details', 'pf_details'),
        'locations': locations,
        'sites': sites,
        'search_q': search_q,
        'location_f': location_f,
        'site_f': site_f,
    })

@login_required
def add_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.created_by = request.user
            employee.save()
            messages.success(request, f"Employee {employee.name} added successfully.")
            
            # Step 2: Handle optional bank details
            bank_name = request.POST.get('bank_name')
            if bank_name:
                BankDetail.objects.create(
                    employee=employee,
                    bank_name=bank_name,
                    account_holder=request.POST.get('account_holder', ''),
                    account_number=request.POST.get('account_number', ''),
                    ifsc_code=request.POST.get('ifsc_code', '')
                )
            
            return redirect('employees:list')
    else:
        form = EmployeeForm()
    return render(request, 'employees/add_form.html', {'form': form, 'title': 'Add Employee'})

@login_required
def edit_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f"Employee {employee.name} updated.")
            return redirect('employees:list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'employees/edit_form.html', {'form': form, 'employee': employee})

@login_required
def delete_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk, created_by=request.user)
    if request.method == 'POST':
        name = employee.name
        employee.delete()
        messages.success(request, f"Employee {name} removed.")
    return redirect('employees:list')

@login_required
def bank_details(request, pk):
    employee = get_object_or_404(Employee, pk=pk, created_by=request.user)
    bank_detail, created = BankDetail.objects.get_or_create(employee=employee)
    if request.method == 'POST':
        form = BankDetailForm(request.POST, instance=bank_detail)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank details updated.")
            return redirect('employees:list')
    else:
        form = BankDetailForm(instance=bank_detail)
    return render(request, 'employees/bank_form.html', {'form': form, 'employee': employee})

@login_required
def pf_details(request, pk):
    employee = get_object_or_404(Employee, pk=pk, created_by=request.user)
    pf_detail, created = PFDetail.objects.get_or_create(employee=employee)
    if request.method == 'POST':
        form = PFDetailForm(request.POST, instance=pf_detail)
        if form.is_valid():
            form.save()
            messages.success(request, "PF details updated.")
            return redirect('employees:list')
    else:
        form = PFDetailForm(instance=pf_detail)
    return render(request, 'employees/pf_form.html', {'form': form, 'employee': employee})

@login_required
def salary_management(request, pk):
    employee = get_object_or_404(Employee, pk=pk, created_by=request.user)
    salaries = employee.salaries.all()
    return render(request, 'employees/salary_list.html', {
        'employee': employee,
        'salaries': salaries,
    })

@login_required
def add_salary(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(Employee, pk=employee_id, created_by=request.user)
        form = SalaryForm(request.POST)
        if form.is_valid():
            salary = form.save(commit=False)
            salary.employee = employee
            salary.save()
            messages.success(request, f"Salary record added for {employee.name}.")
            return redirect('employees:salary_management', pk=employee.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            return redirect('employees:salary_management', pk=employee.pk)
    return redirect('employees:list')

@login_required
def generate_payslip(request, pk):
    salary = get_object_or_404(Salary, pk=pk, employee__created_by=request.user)
    # Generate unique reference if not exists
    if not hasattr(salary, 'payslip'):
        ref = f"PS-{salary.employee.id}-{salary.month.strftime('%Y%m')}"
        Payslip.objects.create(salary=salary, reference_number=ref)
    
    return render(request, 'employees/payslip.html', {
        'salary': salary,
        'employee': salary.employee,
        'payslip': salary.payslip
    })
