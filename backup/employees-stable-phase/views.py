from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Employee, BankDetail, PFDetail, SalaryUpdate
from .forms import EmployeeForm, BankDetailForm, PFDetailForm, SalaryUpdateForm
from django.db.models import Q

@login_required
def employee_list(request):
    admin_id = request.user.admin_id
    search_q = request.GET.get('q', '')
    designation_f = request.GET.get('designation', '')
    status_f = request.GET.get('status', '')
    
    qs = Employee.objects.filter(admin_id=admin_id).select_related('bank_details', 'pf_details')
    if search_q:
        qs = qs.filter(Q(name__icontains=search_q) | Q(employee_id__icontains=search_q))
    if designation_f:
        qs = qs.filter(designation=designation_f)
    if status_f:
        qs = qs.filter(status=status_f)
    
    # Get unique values for filters
    designations = Employee.objects.filter(admin_id=admin_id).values_list('designation', flat=True).distinct()
    statuses = Employee.STATUS_CHOICES
    
    # Get all employees for filters (not just filtered)
    all_employees = Employee.objects.filter(admin_id=admin_id)
    locations = all_employees.values_list('location', flat=True).distinct()
    sites = all_employees.values_list('site', flat=True).distinct()
    
    return render(request, 'employees/list.html', {
        'employees': qs,
        'designations': designations,
        'statuses': statuses,
        'locations': locations,
        'sites': sites,
        'search_q': search_q,
        'designation_f': designation_f,
        'status_f': status_f,
        'active_employees': 'active'
    })

@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=request.user.admin_id)
    history = employee.salary_history.all().order_by('-month')
    
    return render(request, 'employees/detail.html', {
        'employee': employee,
        'history': history,
        'active_employees': 'active'
    })

@login_required
def add_step1_details(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            emp = form.save(commit=False)
            emp.admin_id = request.user.admin_id
            emp.created_by = request.user
            emp.save()
            messages.success(request, f"Details for {emp.name} saved. Proceed to Bank Details.")
            return redirect('employees:add_step2_bank', pk=emp.pk)
    else:
        form = EmployeeForm()
    return render(request, 'employees/wizard/step1_details.html', {'form': form, 'step': 1})

@login_required
def add_step2_bank(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=request.user.admin_id)
    bank, created = BankDetail.objects.get_or_create(employee=employee)
    if request.method == 'POST':
        form = BankDetailForm(request.POST, instance=bank)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank details saved. Proceed to PF Details.")
            return redirect('employees:add_step3_pf', pk=employee.pk)
    else:
        form = BankDetailForm(instance=bank)
    return render(request, 'employees/wizard/step_base.html', {'form': form, 'employee': employee, 'step': 2, 'title': 'Bank Details'})

@login_required
def add_step3_pf(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=request.user.admin_id)
    pf, created = PFDetail.objects.get_or_create(employee=employee)
    if request.method == 'POST':
        form = PFDetailForm(request.POST, instance=pf)
        if form.is_valid():
            form.save()
            messages.success(request, "PF details saved. Proceed to Salary Setup.")
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = PFDetailForm(instance=pf)
    return render(request, 'employees/wizard/step_base.html', {'form': form, 'employee': employee, 'step': 3, 'title': 'PF Details'})

@login_required
def process_salary(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=request.user.admin_id)
    if request.method == 'POST':
        form = SalaryUpdateForm(request.POST)
        if form.is_valid():
            salary = form.save(commit=False)
            salary.employee = employee
            salary.admin_id = request.user.admin_id
            salary.created_by = request.user
            # Auto-fill snapshots from current PFDetail
            if hasattr(employee, 'pf_details'):
                salary.pf_employer_snapshot = employee.pf_details.employer_contribution
                salary.pf_employee_snapshot = employee.pf_details.employee_contribution
            
            salary.save()
            messages.success(request, f"Salary processed for {salary.month.strftime('%B %Y')}")
            return redirect('employees:detail', pk=employee.pk)
    else:
        # Default with base salary
        form = SalaryUpdateForm(initial={'basic_salary': employee.base_salary, 'extra_allowance': employee.fixed_allowance})
    return render(request, 'employees/process_salary.html', {'form': form, 'employee': employee})

@login_required
def delete_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=request.user.admin_id)
    name = employee.name
    employee.delete()
    messages.success(request, f"Employee {name} removed from system.")
    return redirect('employees:list')

# ═══════════════════════════════════════════════════════
#    PAYSLIP GENERATION
# ═══════════════════════════════════════════════════════
@login_required
def view_payslip(request, salary_id):
    """Display payslip for a specific salary record"""
    from .payslip import PayslipGenerator
    
    salary = get_object_or_404(SalaryUpdate, id=salary_id, admin_id=request.user.admin_id)
    generator = PayslipGenerator(salary)
    context = generator.get_payslip_data()
    context['salary_id'] = salary_id
    context['employee'] = salary.employee
    
    return render(request, 'employees/payslip.html', context)

@login_required
def download_payslip_pdf(request, salary_id):
    """Download payslip as PDF"""
    from django.http import HttpResponse
    from .payslip import PayslipGenerator
    
    salary = get_object_or_404(SalaryUpdate, id=salary_id, admin_id=request.user.admin_id)
    generator = PayslipGenerator(salary)
    payslip_data = generator.get_payslip_data()
    
    # Try to generate PDF using reportlab or weasyprint
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from io import BytesIO
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=12,
            alignment=1  # Center
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=10,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=8,
            borderPadding=5,
            borderColor=colors.HexColor('#e5e7eb'),
            borderWidth=1,
            backColor=colors.HexColor('#f3f4f6')
        )
        
        elements = []
        
        # Header
        elements.append(Paragraph("SALARY PAYSLIP", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # General Info
        month_str = payslip_data['month'].strftime('%B %Y')
        general_data = [
            ['EMPLOYEE NAME', payslip_data['employee_name'], 'EMPLOYEE ID', payslip_data['employee_id']],
            ['DESIGNATION', payslip_data['designation'], 'LOCATION', payslip_data['location']],
            ['PAYROLL MONTH', month_str, 'GENERATED', payslip_data['generated_on'].strftime('%d-%m-%Y')],
        ]
        
        general_table = Table(general_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
        general_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(general_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Earnings
        elements.append(Paragraph("EARNINGS", heading_style))
        earnings_data = [
            ['DESCRIPTION', 'AMOUNT'],
            ['Basic Salary', f"₹{payslip_data['basic_salary']:,.2f}"],
            ['Extra Allowance', f"₹{payslip_data['extra_allowance']:,.2f}"],
            ['OT / Extra Allowance', f"₹{payslip_data['ot_allowance']:,.2f}"],
            ['Total Earnings', f"₹{payslip_data['total_earnings']:,.2f}"],
        ]
        
        earnings_table = Table(earnings_data, colWidths=[3*inch, 2*inch])
        earnings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0fdf4')),
        ]))
        elements.append(earnings_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Deductions
        elements.append(Paragraph("DEDUCTIONS", heading_style))
        deductions_data = [
            ['DESCRIPTION', 'AMOUNT'],
            ['Advance Pay', f"₹{payslip_data['advance_pay']:,.2f}"],
            ['Total Deductions', f"₹{payslip_data['total_deduction']:,.2f}"],
        ]
        
        deductions_table = Table(deductions_data, colWidths=[3*inch, 2*inch])
        deductions_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(deductions_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # Net Pay
        net_data = [['NET PAY (After Deductions)', f"₹{payslip_data['net_pay']:,.2f}"]]
        net_table = Table(net_data, colWidths=[3*inch, 2*inch])
        net_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#16a34a')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
        ]))
        elements.append(net_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Bank Details
        elements.append(Paragraph("BANK DETAILS", heading_style))
        bank_data = [
            ['Bank Name', payslip_data['bank_name']],
            ['Account Holder', payslip_data['account_holder']],
            ['Account Number', payslip_data['account_number']],
            ['IFSC Code', payslip_data['ifsc_code']],
        ]
        
        bank_table = Table(bank_data, colWidths=[1.5*inch, 3.5*inch])
        bank_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(bank_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # PF Details (Payslip Only)
        elements.append(Paragraph("STATUTORY DEDUCTIONS (PF)", heading_style))
        pf_data = [
            ['PF Number', payslip_data['pf_number']],
            ['ESIC Number', payslip_data['esic_number']],
            ['UAN Number', payslip_data['uan_number']],
            ['PF Contribution', f"₹{payslip_data['pf_amount']:,.2f}"],
            ['Employer Contribution', f"₹{payslip_data['pf_employer']:,.2f}"],
        ]
        
        pf_table = Table(pf_data, colWidths=[1.5*inch, 3.5*inch])
        pf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbeb')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        elements.append(pf_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Payslip_{payslip_data["employee_name"]}_{month_str}.pdf"'
        return response
        
    except ImportError:
        # Fallback if reportlab not available
        return HttpResponse("PDF generation requires reportlab package.", status=400)

import json
from django.http import JsonResponse
from decimal import Decimal

@login_required
def manage_employee_ajax(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            admin_id = request.user.admin_id
            
            # Step 1: Employee
            emp_id = data.get('id')
            if emp_id:
                emp = Employee.objects.get(id=emp_id, admin_id=admin_id)
            else:
                emp = Employee(admin_id=admin_id, created_by=request.user)
                
            emp.name = data.get('name', emp.name)
            emp.designation = data.get('role', emp.designation)
            emp.location = data.get('location', emp.location)
            emp.site = data.get('site', emp.site)
            emp.base_salary = Decimal(data.get('salary', 0) or 0)
            emp.save()

            # Step 2: Bank
            bank_data = data.get('bank', {})
            if bank_data.get('bank_name') or bank_data.get('account_number'):
                bank, _ = BankDetail.objects.get_or_create(employee=emp)
                bank.bank_name = bank_data.get('bank_name', bank.bank_name)
                bank.account_holder = bank_data.get('holder', bank.account_holder)
                bank.account_number = bank_data.get('account', bank.account_number)
                bank.ifsc_code = bank_data.get('ifsc', bank.ifsc_code)
                bank.save()

            # Step 3: PF
            pf_data = data.get('pf', {})
            if pf_data.get('pf_number') or pf_data.get('uan_number'):
                pf, _ = PFDetail.objects.get_or_create(employee=emp)
                pf.pf_number = pf_data.get('pf_number', pf.pf_number)
                pf.uan_number = pf_data.get('uan_number', pf.uan_number)
                pf.esic_number = pf_data.get('esic', pf.esic_number)
                pf.status = 'added'
                pf.save()
            
            return JsonResponse({'success': True, 'id': emp.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def salary_manager(request):
    return render(request, 'employees/salary_manager.html')
