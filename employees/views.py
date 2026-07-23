from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
import calendar
import datetime
import json
import random
import secrets
import string
from decimal import Decimal
from django.contrib.auth.hashers import make_password
from .models import Employee, BankDetail, PFDetail, SalaryUpdate, SalaryStructure, JobRole, EmployeeLevel
from .forms import EmployeeForm, BankDetailForm, PFDetailForm, SalaryForm
from branches.models import LocationSite
from accounts.views import get_admin_id


def _sync_employee_location(employee, user):
    """Register an employee's location/site in the centralized LocationSite table."""
    admin_id = get_admin_id(user)
    loc  = (employee.location or '').strip()
    site = (employee.site or '').strip()
    if not loc and not site:
        return
    combined = f"{loc} / {site}" if loc and site else (loc or site)
    if not LocationSite.objects.filter(admin_id=admin_id, name__iexact=combined).exists():
        LocationSite.objects.create(admin_id=admin_id, name=combined, created_by=user)


def _generate_employee_id(admin_id):
    """Return the next available SPIMXXX employee ID for the given tenant."""
    existing_ids = Employee.objects.filter(admin_id=admin_id).values_list('employee_id', flat=True)
    max_num = 0
    for eid in existing_ids:
        if eid and eid.upper().startswith('SPIM'):
            try:
                num = int(eid[4:])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                pass
    return f"SPIM{(max_num + 1):03d}"


def _apply_role_level_salary(employee, admin_id, force=False):
    """
    Auto-fill an Employee's monetary fields from the matching SalaryStructure
    (job_role + level). Lookup keys: (admin_id, job_role, level). When `force`
    is True (Role/Level changed on edit), overwrites existing base_salary and
    fixed_allowance so the centralized config remains the source of truth.
    Otherwise preserves any explicit override the admin typed into the form.

    Custom-override guard: when Employee.salary_is_custom_override is True,
    base_salary is never touched (Case 3 / Case 4 of the manual-override
    spec). fixed_allowance is allowed to refresh because it represents the
    food-allowance line, which is configured per Role+Level, not per
    employee — admins manage food allowance via the Salary Config.
    """
    if getattr(employee, 'salary_is_custom_override', False):
        # Honor the per-employee manual override — do not refresh base_salary
        # from the centralized config, even when force=True.
        force_base = False
    else:
        force_base = force
    level_val = (employee.level or '').strip()
    if not level_val:
        return
    structure = None
    if employee.job_role_id:
        structure = SalaryStructure.objects.filter(
            admin_id=admin_id, job_role_id=employee.job_role_id, level=level_val,
        ).first()
    # Fallback: match by JobRole.name == Employee.designation so that the
    # Salary Config table works even when the employee has no explicit
    # JobRole FK (the Add modal stores role as free-text designation).
    if not structure:
        designation = (employee.designation or '').strip()
        if designation:
            structure = SalaryStructure.objects.filter(
                admin_id=admin_id,
                job_role__admin_id=admin_id,
                job_role__name__iexact=designation,
                level=level_val,
            ).first()
    if not structure:
        return
    if force_base or not employee.base_salary:
        employee.base_salary = structure.base_salary
    # `fixed_allowance` carries the food allowance in the existing schema.
    if force or not employee.fixed_allowance:
        employee.fixed_allowance = structure.food_allowance


def _generate_app_password():
    """
    Return a cryptographically random mobile-app password.

    Requirements (SPIM Lite):
      * Minimum 8 characters
      * Includes uppercase, lowercase, digits, special characters
      * Generated via `secrets` for cryptographic strength
    """
    uppers   = string.ascii_uppercase
    lowers   = string.ascii_lowercase
    digits   = string.digits
    specials = '!@#$%^&*'
    # Guarantee at least one of each required class
    required = [
        secrets.choice(uppers),
        secrets.choice(lowers),
        secrets.choice(digits),
        secrets.choice(specials),
    ]
    pool      = uppers + lowers + digits + specials
    remaining = [secrets.choice(pool) for _ in range(6)]  # 4 + 6 = 10 chars
    chars     = required + remaining
    # Shuffle without bias
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


def _location_sites_json(user):
    """Return a JSON string of all centralized location names for this tenant."""
    admin_id = get_admin_id(user)
    names = list(LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True))
    return json.dumps(names)


def timezone_month_map(month_name):
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
    }
    return months.get(month_name, 1)


@login_required
def employee_list(request):
    search_q = request.GET.get('q', '')
    location_f = request.GET.get('location', '')
    site_f = request.GET.get('site', '')
    admin_id = get_admin_id(request.user)
    qs = Employee.objects.filter(admin_id=admin_id)
    if search_q:
        qs = qs.filter(
            Q(name__icontains=search_q) |
            Q(employee_id__icontains=search_q) |
            Q(designation__icontains=search_q)
        )
    if location_f:
        qs = qs.filter(location=location_f)
    if site_f:
        qs = qs.filter(site=site_f)

    locations = Employee.objects.filter(admin_id=admin_id).values_list('location', flat=True).distinct().order_by('location')
    sites = Employee.objects.filter(admin_id=admin_id).values_list('site', flat=True).distinct().order_by('site')

    # ── Global master dropdowns (Task 4 / 2026-05-24) ──────────────────
    # Single source of truth per master. Roles/levels/locations/sites are
    # collected from EVERY table that already holds them so a value typed
    # anywhere in the system shows up in every dependent dropdown.
    def _dedup_sorted(values):
        seen = set()
        out  = []
        for v in values:
            v = (v or '').strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                out.append(v)
        return sorted(out, key=lambda x: x.lower())

    # Local re-import guards against a stale autoreload session where the
    # module-level import didn't get refreshed.
    from .models import (
        JobRole as _JobRole,
        SalaryStructure as _SalaryStructure,
        EmployeeLevel as _EmployeeLevel,
    )
    role_pool = list(
        Employee.objects.filter(admin_id=admin_id).values_list('designation', flat=True)
    ) + list(
        _JobRole.objects.filter(admin_id=admin_id).values_list('name', flat=True)
    )
    level_pool = list(
        Employee.objects.filter(admin_id=admin_id).values_list('level', flat=True)
    ) + list(
        _SalaryStructure.objects.filter(admin_id=admin_id).values_list('level', flat=True)
    ) + list(
        _EmployeeLevel.objects.filter(admin_id=admin_id).values_list('name', flat=True)
    )
    # Location pool — Employee.location PLUS the part before " / " in
    # LocationSite.name (centralized branches registry).
    loc_pool = list(Employee.objects.filter(admin_id=admin_id).values_list('location', flat=True))
    site_pool = list(Employee.objects.filter(admin_id=admin_id).values_list('site', flat=True))
    for combined in LocationSite.objects.filter(admin_id=admin_id).values_list('name', flat=True):
        if ' / ' in combined:
            l, s = combined.split(' / ', 1)
            loc_pool.append(l); site_pool.append(s)
        else:
            loc_pool.append(combined)

    return render(request, 'employees/list.html', {
        'employees':           qs.select_related('bank_details', 'pf_details'),
        'all_employees':       Employee.objects.filter(admin_id=admin_id).order_by('name'),
        'locations':           locations,
        'sites':               sites,
        'search_q':            search_q,
        'location_f':          location_f,
        'site_f':              site_f,
        'location_sites_json': _location_sites_json(request.user),
        'next_employee_id':    _generate_employee_id(admin_id),
        'preview_password':    _generate_app_password(),
        # Global masters — consumed by the four <datalist>s in the template.
        'master_roles':        _dedup_sorted(role_pool),
        'master_levels':       _dedup_sorted(level_pool),
        'master_locations':    _dedup_sorted(loc_pool),
        'master_sites':        _dedup_sorted(site_pool),
    })


@login_required
def add_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.created_by = request.user
            admin_id = get_admin_id(request.user)
            employee.admin_id = admin_id

            # Auto-generate Employee ID if blank, ensure uniqueness
            emp_id = (employee.employee_id or '').strip()
            if not emp_id:
                emp_id = _generate_employee_id(admin_id)
            while Employee.objects.filter(admin_id=admin_id, employee_id=emp_id).exists():
                emp_id = _generate_employee_id(admin_id)
            employee.employee_id = emp_id

            # Auto-generate Mobile App Password if blank.
            # The plaintext is shown ONCE in the admin UI (existing behavior)
            # but the source of truth for authentication is mobile_password_hash.
            if not (employee.mobile_app_password or '').strip():
                employee.mobile_app_password = _generate_app_password()
            employee.mobile_password_hash = make_password(employee.mobile_app_password)

            # SPIM Lite login id mirrors the Employee ID.
            employee.employee_login_id = employee.employee_id
            employee.mobile_account_active = True

            # Role + Level → SalaryStructure auto-fill (Task 5)
            _apply_role_level_salary(employee, admin_id)

            employee.save()
            _sync_employee_location(employee, request.user)
            messages.success(request, f"Employee {employee.name} added successfully.")

            bank_name = request.POST.get('bank_name')
            if bank_name:
                BankDetail.objects.create(
                    employee=employee,
                    bank_name=bank_name,
                    account_holder=request.POST.get('account_holder', ''),
                    account_number=request.POST.get('account_number', ''),
                    ifsc_code=request.POST.get('ifsc_code', ''),
                    branch=request.POST.get('branch', ''),
                )

            pf_number = request.POST.get('pf_number')
            if pf_number:
                PFDetail.objects.create(
                    employee=employee,
                    pf_number=pf_number,
                    uan_number=request.POST.get('uan_number', ''),
                    esic_number=request.POST.get('esic_number', ''),
                    status='added'
                )

            return redirect('employees:list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
            return redirect('employees:list')
    else:
        return redirect('employees:list')


@login_required
def edit_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=get_admin_id(request.user))
    original_emp_id     = employee.employee_id
    original_role       = (employee.designation or '').strip().lower()
    original_level      = (employee.level or '').strip().lower()
    original_job_role   = employee.job_role_id
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            new_emp_id = (form.cleaned_data.get('employee_id') or '').strip()
            if new_emp_id and new_emp_id != original_emp_id:
                employee.employee_login_id = new_emp_id
            updated = form.save()
            # Re-apply Salary Config when Role / Level / JobRole changed so
            # base_salary stays in sync with the centralized SalaryStructure.
            role_changed  = (updated.designation or '').strip().lower() != original_role
            level_changed = (updated.level or '').strip().lower() != original_level
            jr_changed    = updated.job_role_id != original_job_role
            if role_changed or level_changed or jr_changed:
                admin_id = get_admin_id(request.user)
                _apply_role_level_salary(updated, admin_id, force=True)
                updated.save(update_fields=['base_salary', 'fixed_allowance'])
            _sync_employee_location(updated, request.user)
            messages.success(request, f"Employee {employee.name} updated.")
            return redirect('employees:list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'employees/edit_form.html', {
        'form': form,
        'employee': employee,
        'location_sites_json': _location_sites_json(request.user),
    })


@login_required
def delete_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=get_admin_id(request.user))
    if request.method == 'POST':
        name = employee.name
        employee.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'name': name})
        messages.success(request, f"Employee {name} removed.")
    return redirect('employees:list')


@login_required
def employee_edit_ajax(request, pk):
    """AJAX-only endpoint: update core employee fields without a full-page reload."""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return redirect('employees:list')
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    employee = get_object_or_404(Employee, pk=pk, admin_id=get_admin_id(request.user))
    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'success': False, 'error': 'Name is required'})
    original_role  = (employee.designation or '').strip().lower()
    original_level = (employee.level or '').strip().lower()
    employee.name                = name
    posted_emp_id = request.POST.get('employee_id', employee.employee_id).strip()
    if posted_emp_id != employee.employee_id:
        employee.employee_login_id = posted_emp_id
    employee.employee_id         = posted_emp_id
    employee.designation         = request.POST.get('designation', employee.designation).strip()
    # Persist level / mobile / branch — previously silently dropped because
    # this handler only updated a hard-coded subset of fields. Without these
    # assignments, the in-page Edit modal would save (HTTP 200) but the new
    # level/mobile/branch would be lost on the server, breaking the
    # SPIM Lite reflection chain.
    employee.level               = request.POST.get('level', employee.level).strip()
    employee.mobile              = request.POST.get('mobile', employee.mobile).strip()
    employee.branch              = request.POST.get('branch', employee.branch).strip()
    employee.location            = request.POST.get('location', employee.location).strip()
    employee.site                = request.POST.get('site', employee.site).strip()
    posted_pw = request.POST.get('mobile_app_password', employee.mobile_app_password).strip()
    if posted_pw and posted_pw != employee.mobile_app_password:
        employee.mobile_app_password = posted_pw
        employee.mobile_password_hash = make_password(posted_pw)
    salary_str = request.POST.get('base_salary', '').strip()
    if salary_str:
        try:
            employee.base_salary = float(salary_str)
        except ValueError:
            pass
    # Auto-assign base salary from centralized Salary Config when role/level
    # changes (Tasks 3 / 4). When admin explicitly typed a base_salary in the
    # same submission we honor it (kept above); otherwise the structure value
    # wins. force=True ensures stale base salaries follow the new mapping.
    admin_id = get_admin_id(request.user)
    role_changed  = (employee.designation or '').strip().lower() != original_role
    level_changed = (employee.level or '').strip().lower() != original_level
    if (role_changed or level_changed) and not salary_str:
        _apply_role_level_salary(employee, admin_id, force=True)
    employee.save()
    _sync_employee_location(employee, request.user)
    return JsonResponse({'success': True})


@login_required
def export_json_employees(request):
    """Download all employees for this tenant as a JSON file."""
    from django.http import HttpResponse
    admin_id = get_admin_id(request.user)
    qs = Employee.objects.filter(admin_id=admin_id).values(
        'name', 'employee_id', 'designation', 'department',
        'location', 'site', 'base_salary', 'status', 'joining_date'
    )
    payload = json.dumps({'employees': list(qs)}, indent=2, default=str)
    resp = HttpResponse(payload, content_type='application/json')
    resp['Content-Disposition'] = 'attachment; filename="employees_export.json"'
    return resp


@login_required
def export_excel_employees(request):
    """Download the Employee Master list for this tenant as an XLSX file.

    Mirrors the Employee Master (`employee_list`) queryset so the export
    always reflects what the admin sees on screen: same tenant scope, same
    optional q/location/site filters, same model-default ordering by name.
    """
    from io import BytesIO
    from django.http import HttpResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    admin_id = get_admin_id(request.user)
    search_q   = request.GET.get('q', '')
    location_f = request.GET.get('location', '')
    site_f     = request.GET.get('site', '')

    employees = (
        Employee.objects.filter(admin_id=admin_id)
        .select_related('job_role', 'bank_details', 'pf_details')
    )
    if search_q:
        employees = employees.filter(
            Q(name__icontains=search_q) |
            Q(employee_id__icontains=search_q) |
            Q(designation__icontains=search_q)
        )
    if location_f:
        employees = employees.filter(location=location_f)
    if site_f:
        employees = employees.filter(site=site_f)
    # Employee.Meta.ordering = ['name'] — match Master page exactly.
    employees = employees.order_by('name')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Employees'

    headers = [
        'Employee ID', 'Employee Name', 'Mobile', 'Role', 'Level',
        'Department', 'Designation', 'Branch', 'Location', 'Site',
        'Status', 'Joining Date', 'Salary Type', 'Base Salary',
        'Fixed Allowance', 'Bank Details Status', 'PF Status',
    ]
    ws.append(headers)

    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='1E293B')
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for emp in employees:
        role_name = emp.job_role.name if emp.job_role_id else ''
        bank_status = ''
        if hasattr(emp, 'bank_details'):
            bank_status = emp.bank_details.get_status_display() or 'Added'
        else:
            bank_status = 'Not Added'
        pf_status = ''
        if hasattr(emp, 'pf_details'):
            pf_status = emp.pf_details.get_status_display() or 'Added'
        else:
            pf_status = 'Not Added'

        ws.append([
            emp.employee_id or '',
            emp.name or '',
            emp.mobile or '',
            role_name,
            emp.level or '',
            emp.department or '',
            emp.designation or '',
            emp.branch or '',
            emp.location or '',
            emp.site or '',
            emp.get_status_display() if emp.status else '',
            emp.joining_date,
            emp.get_salary_type_display() if emp.salary_type else '',
            float(emp.base_salary) if emp.base_salary is not None else 0,
            float(emp.fixed_allowance) if emp.fixed_allowance is not None else 0,
            bank_status,
            pf_status,
        ])

    # Format Joining Date column as text-date and salaries as numeric
    for row in ws.iter_rows(min_row=2, min_col=12, max_col=12):
        for cell in row:
            if cell.value:
                cell.number_format = 'yyyy-mm-dd'
    for row in ws.iter_rows(min_row=2, min_col=14, max_col=15):
        for cell in row:
            cell.number_format = '#,##0.00'

    # Auto-fit column widths based on the longest cell value per column
    for col_idx, column_cells in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in column_cells:
            val = cell.value
            if val is None:
                continue
            if hasattr(val, 'strftime'):
                length = len(val.strftime('%Y-%m-%d'))
            else:
                length = len(str(val))
            if length > max_len:
                max_len = length
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 40)

    ws.freeze_panes = 'A2'

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    filename = f"Employee_Master_{timezone.localdate().strftime('%Y-%m-%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def import_excel_employees(request):
    """Stub: accept Excel file upload (full implementation coming soon)."""
    messages.info(request, "Excel import is coming soon. Please use JSON import for now.")
    return redirect('employees:list')


@login_required
@require_POST
def import_json_employees(request):
    """Import employees from a previously exported JSON file.
    Supports both SPIM Suite export keys and SPIM Lite JSON keys.
    Uses update_or_create so re-importing the same file updates rather
    than duplicating records. Bank details are upserted when present."""
    json_file = request.FILES.get('json_file')
    if not json_file:
        messages.error(request, "No file selected.")
        return redirect('employees:list')
    try:
        data = json.loads(json_file.read())
        emp_list = data.get('employees', data) if isinstance(data, dict) else data
        admin_id = get_admin_id(request.user)
        count = 0
        for emp in emp_list:
            if not isinstance(emp, dict) or not emp.get('name'):
                continue

            # ── Field aliases: accept both export and SPIM Lite key names ──
            employee_id = emp.get('employee_id') or str(emp.get('id', ''))
            designation = emp.get('designation') or emp.get('role', '')
            # base_salary: prefer explicit key; fall back to 'salary'
            raw_salary  = emp.get('base_salary')
            if raw_salary is None:
                raw_salary = emp.get('salary', 0)

            employee_obj, _ = Employee.objects.update_or_create(
                admin_id    = admin_id,
                employee_id = employee_id,
                defaults={
                    'name':        emp.get('name', ''),
                    'designation': designation,
                    'department':  emp.get('department', ''),
                    'location':    emp.get('location', ''),
                    'site':        emp.get('site', ''),
                    'base_salary': raw_salary or 0,
                    'status':      emp.get('status', 'active'),
                    'created_by':  request.user,
                    # JSON contains per-employee individual salaries — mark as
                    # custom override so sc_save never silently overwrites them.
                    'salary_is_custom_override': True,
                }
            )
            count += 1

            # ── Bank details: upsert if any bank field is provided ──────────
            bank_name      = emp.get('bank', '')
            account_holder = emp.get('holder', '')
            account_number = emp.get('account', '')
            ifsc_code      = emp.get('ifsc', '')
            if any([bank_name, account_holder, account_number, ifsc_code]):
                BankDetail.objects.update_or_create(
                    employee=employee_obj,
                    defaults={
                        'bank_name':      bank_name,
                        'account_holder': account_holder,
                        'account_number': account_number,
                        'ifsc_code':      ifsc_code,
                    }
                )

        messages.success(request, f"Imported {count} employee(s) successfully.")
    except Exception as e:
        messages.error(request, f"Import failed: {str(e)}")
    return redirect('employees:list')


@login_required
def employee_list_json(request):
    """Return the employee list as JSON for the attendance page live-fetch.
    Bypasses browser HTML caching so salary changes are always reflected
    immediately without requiring a hard reload."""
    admin_id = get_admin_id(request.user)
    employees = Employee.objects.filter(admin_id=admin_id)
    emp_list = []
    for emp in employees:
        # EMP ID must come from the employee_id column only — never the PK.
        # `pk` is an internal-only field that lets the attendance JS resolve
        # the right Employee row when `employee_id` is blank. It is never
        # displayed as the EMP ID.
        emp_list.append({
            'id':           emp.employee_id or '',
            'pk':           emp.pk,
            'name':         emp.name,
            'dept':         emp.department or '',
            'role':         emp.designation or '',
            'mainLocation': emp.location or '',
            'site':         emp.site or '',
            'leave':        '0',
            'baseSalary':   float(emp.base_salary) if emp.base_salary else 0,
            'salaryType':   getattr(emp, 'salary_type', 'base_salary') or 'base_salary',
        })
    return JsonResponse({'employees': emp_list})


@login_required
def bank_details(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=get_admin_id(request.user))
    bank_detail, _ = BankDetail.objects.get_or_create(
        employee=employee,
        defaults={'bank_name': '', 'account_holder': '', 'account_number': '', 'ifsc_code': ''},
    )
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        if is_ajax:
            # Modal only sends bank_name/account_holder/account_number/ifsc_code.
            # Fill modal-excluded required fields from the current record to prevent
            # form validation failures on fields the modal never submits.
            post_data = request.POST.copy()
            if 'status' not in post_data:
                post_data['status'] = bank_detail.status or 'pending'
            if 'branch' not in post_data:
                post_data['branch'] = bank_detail.branch or ''
            form = BankDetailForm(post_data, instance=bank_detail)
        else:
            form = BankDetailForm(request.POST, instance=bank_detail)
        if form.is_valid():
            form.save()
            if is_ajax:
                return JsonResponse({'success': True})
            messages.success(request, "Bank details updated.")
            return redirect('employees:list')
        if is_ajax:
            return JsonResponse({'success': False, 'errors': form.errors.as_json()}, status=400)
    else:
        form = BankDetailForm(instance=bank_detail)
    return render(request, 'employees/bank_form.html', {'form': form, 'employee': employee})


@login_required
def pf_details(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=get_admin_id(request.user))
    pf_detail, _ = PFDetail.objects.get_or_create(employee=employee)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        if is_ajax:
            # Modal only sends pf_number and esic_number.
            # Fill modal-excluded required fields from the current record to prevent
            # form validation failures on fields the modal never submits.
            post_data = request.POST.copy()
            if 'status' not in post_data:
                post_data['status'] = pf_detail.status or 'pending'
            if 'uan_number' not in post_data:
                post_data['uan_number'] = pf_detail.uan_number or ''
            if 'employee_contribution' not in post_data:
                post_data['employee_contribution'] = str(pf_detail.employee_contribution or '0')
            if 'employer_contribution' not in post_data:
                post_data['employer_contribution'] = str(pf_detail.employer_contribution or '0')
            form = PFDetailForm(post_data, instance=pf_detail)
        else:
            form = PFDetailForm(request.POST, instance=pf_detail)
        if form.is_valid():
            form.save()
            if is_ajax:
                return JsonResponse({'success': True})
            messages.success(request, "PF details updated.")
            return redirect('employees:list')
        if is_ajax:
            return JsonResponse({'success': False, 'errors': form.errors.as_json()}, status=400)
    else:
        form = PFDetailForm(instance=pf_detail)
    return render(request, 'employees/pf_form.html', {'form': form, 'employee': employee})


@login_required
def salary_management(request, pk):
    employee = get_object_or_404(Employee, pk=pk, admin_id=get_admin_id(request.user))
    salaries = employee.salary_history.all()
    return render(request, 'employees/salary_list.html', {
        'employee': employee,
        'salaries': salaries,
    })


@login_required
def salary_dashboard(request):
    """
    Main Salary Management Dashboard (The premium multi-filter UI).
    """
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        # AJAX JSON Request: Return stats and salary list
        month_name = request.GET.get('month', '')
        year = request.GET.get('year', '')
        
        # Filters from UI
        f_location = request.GET.get('location', '')
        f_site = request.GET.get('site', '')
        f_bank = request.GET.get('bank', '')
        f_search = request.GET.get('search', '').lower()

        admin_id = get_admin_id(request.user)
        queryset = Employee.objects.filter(admin_id=admin_id).order_by('name')
        
        # Apply filters if provided
        if f_location:
            queryset = queryset.filter(location=f_location)
        if f_site:
            queryset = queryset.filter(site=f_site)
        if f_bank:
            queryset = queryset.filter(bank_details__bank_name=f_bank)
        if f_search:
            queryset = queryset.filter(Q(name__icontains=f_search) | Q(employee_id__icontains=f_search))

        emp_list = []
        total_net = 0
        total_ded = 0
        total_ot = 0
        total_advance = 0
        processed_count = 0

        # For selecting specific month salary
        target_date = None
        if month_name and year:
            try:
                m_idx = timezone_month_map(month_name)
                target_date = datetime.date(int(year), m_idx, 1)
            except: pass

        # Case 2 — back-fill base_salary for employees that have no salary on
        # record yet (and no manual override) from the centralized Salary
        # Config. Idempotent: only touches rows where base_salary == 0.
        for e in queryset:
            if (not e.base_salary) and (not e.salary_is_custom_override) and (e.level or '').strip():
                _apply_role_level_salary(e, admin_id, force=False)
                if e.base_salary:
                    e.save(update_fields=['base_salary', 'fixed_allowance'])

        for e in queryset:
            # Find salary record for specific month or last one
            if target_date:
                salary_record = e.salary_history.filter(month__year=target_date.year, month__month=target_date.month).first()
            else:
                salary_record = e.salary_history.order_by('-month').first()
            
            bank = getattr(e, 'bank_details', None)
            pf = getattr(e, 'pf_details', None)
            
            gross_base = float(salary_record.basic_salary if salary_record else e.base_salary)
            ot = float(salary_record.ot_allowance if salary_record else 0)
            advance = float(salary_record.advance_pay if salary_record else 0)
            ded = float(salary_record.total_deduction if salary_record else 0)
            pf_amount = float(salary_record.pf_employee_snapshot if salary_record else 0)
            # Always compute the attendance-prorated payable base so the Edit
            # Salary modal can render the same value as the dashboard list
            # (single source of truth — same helper the Save handler uses).
            # The compute is per (employee, month, base), so it's also valid
            # when a salary_record already exists.
            ae_month = (
                target_date
                or (salary_record.month if salary_record else timezone.now().date().replace(day=1))
            )
            try:
                _earn_dec, _paid_dec = _compute_attendance_breakdown(
                    e, ae_month, gross_base,
                )
                attendance_earnings = float(_earn_dec)
                attendance_paid_days = float(_paid_dec)
            except Exception as exc:
                # Defensive: never let a per-row compute kill the whole
                # dashboard. Surface in logs and fall back to gross_base.
                print(f'[salary_dashboard] attendance compute failed for emp {e.pk}: {exc}')
                attendance_earnings = gross_base
                attendance_paid_days = 0.0

            # Always derive net from the LIVE attendance_earnings so the
            # dashboard reflects current attendance data. salary_record.net_pay
            # is a snapshot stamped at Save time for payslip rendering — using
            # it here would lock the row at a stale value (e.g. ₹0 from an
            # earlier save when attendance had not yet been marked).
            net = attendance_earnings + ot - advance - ded

            if salary_record:
                processed_count += 1

            total_net += net
            total_ded += ded
            total_ot += ot
            total_advance += advance

            food_allowance = float(salary_record.food_allowance if salary_record else 0)
            food_usage     = float(salary_record.food_usage if salary_record else 0)

            emp_list.append({
                'id': e.id,
                'employee_name': e.name,
                'employee_id': e.employee_id,
                'role': e.designation or '',
                'level': e.level or '',
                'location': e.location,
                'site': e.site,
                'is_payslip_generated': bool(salary_record and salary_record.is_payslip_generated),
                'payslip_id': salary_record.id if salary_record else None,
                'month': month_name or (salary_record.month.strftime('%B') if salary_record else 'N/A'),
                'year': year or (salary_record.month.year if salary_record else 'N/A'),
                'base_salary': float(e.base_salary),
                # Salary Type surfaced so the Edit modal can render the
                # dropdown with the employee's current selection and swap
                # the "Base Salary" label to "Daily Salary" for daily-basis
                # rows. Defaults to 'base_salary' for rows created before
                # the field existed (migration 0012).
                'salary_type': getattr(e, 'salary_type', 'base_salary') or 'base_salary',
                'salary_is_custom_override': bool(e.salary_is_custom_override),
                'gross_salary': gross_base + ot, # simplified gross
                'advance_pay': advance,
                'deduction': ded,
                'pf_amount': pf_amount,
                'net_payable': net,
                # Server-computed payable base from AttendanceRecord rows for
                # the row's month — Edit Salary modal reads this instead of
                # its localStorage fallback so it always matches the page.
                'attendance_earnings': attendance_earnings,
                # Paid-days breakdown (Present + WeekOff + Holiday + 0.5·HalfDay)
                # surfaced so the Edit Salary modal can display it read-only.
                'paid_days': float(attendance_paid_days),
                'overtime': ot,
                'food_allowance': food_allowance,
                'food_usage': food_usage,
                'bank_name': bank.bank_name if bank else '',
                'account_holder': bank.account_holder if bank else '',
                'account_number': bank.account_number if bank else '',
                'ifsc_code': bank.ifsc_code if bank else '',
                'pf_number': pf.pf_number if pf else '',
                'esi_number': pf.esic_number if pf else '',
            })

        return JsonResponse({
            'salaries': emp_list,
            'stats': {
                'total_employees': queryset.count(),
                'processed_count': processed_count,
                'total_net_payable': total_net,
                'total_deductions': total_ded,
                'total_ot': total_ot,
                'total_advance': total_advance,
            },
            'filters': {
                'locations': list(Employee.objects.filter(admin_id=admin_id).values_list('location', flat=True).distinct()),
                'sites': list(Employee.objects.filter(admin_id=admin_id).values_list('site', flat=True).distinct()),
                'banks': list(BankDetail.objects.filter(employee__admin_id=admin_id).values_list('bank_name', flat=True).distinct()),
            }
        })

    # Provide the same master pools the Employee Add/Edit dropdowns use so
    # Salary Config's Role + Level <select>s render from a single source.
    from .models import JobRole as _JR, EmployeeLevel as _EL, SalaryStructure as _SS
    from branches.models import LocationSite as _LS
    def _dedup(values):
        seen = set(); out = []
        for v in values:
            v = (v or '').strip()
            if v and v.lower() not in seen:
                seen.add(v.lower()); out.append(v)
        return sorted(out, key=lambda x: x.lower())
    admin_id = get_admin_id(request.user)
    master_roles = _dedup(
        list(Employee.objects.filter(admin_id=admin_id).values_list('designation', flat=True)) +
        list(_JR.objects.filter(admin_id=admin_id).values_list('name', flat=True))
    )
    master_levels = _dedup(
        list(Employee.objects.filter(admin_id=admin_id).values_list('level', flat=True)) +
        list(_EL.objects.filter(admin_id=admin_id).values_list('name', flat=True)) +
        list(_SS.objects.filter(admin_id=admin_id).values_list('level', flat=True))
    )
    return render(request, 'employees/salary_manager.html', {
        'master_roles':  master_roles,
        'master_levels': master_levels,
    })


# ─── Server-side Salary Report Download ─────────────────────────────────────
# The previous Download Report button relied on jsPDF + SheetJS loaded from
# cdnjs.cloudflare.com. On networks that block cdnjs (corporate proxies,
# aggressive ad-blockers, some Railway egress paths) the libraries never
# parse and the click does nothing. This server-side path uses reportlab
# (PDF) and openpyxl (XLSX), both already pinned in requirements.txt
# (lines 32, 54), so no CDN dependency remains.
#
# The view mirrors salary_dashboard's JSON filter pipeline + per-employee
# salary derivation, then streams a binary file with Content-Disposition:
# attachment. The frontend simply navigates the browser to the URL — no
# client-side JS library involvement at all.
# ────────────────────────────────────────────────────────────────────────────
@login_required
def salary_report_download(request):
    """
    GET /employees/salary/report/download/?format=pdf|xlsx
        &month=June&year=2026
        &location=...&site=...&bank=...&search=...

    Returns a PDF (default) or XLSX file containing the same salary rows
    the Salary Management page is currently showing, with these 8 columns:
        EMP ID | EMP NAME | SITE | SALARY (₹) | BANK NAME | ACCOUNT HOLDER
        | ACCOUNT NUMBER | IFSC CODE
    Filename: Salary_Report_<Month>_<Year>.{pdf,xlsx}

    Auth note: @login_required protects this view against unauthenticated
    callers. If reached without a session it will 302 to LOGIN_URL (see
    config/settings.py). In practice this can only happen if a user's
    session expired between the page render and the download click — the
    salary_manager page itself is @login_required too, so an unauthenticated
    user can't see the Download button in the first place. The frontend
    uses an <a download> click pattern that does NOT replace the current
    URL, so if Django redirects to login the user stays on the salary
    page and can re-authenticate without losing context.
    """
    fmt = (request.GET.get('format') or 'pdf').strip().lower()
    if fmt not in ('pdf', 'xlsx'):
        fmt = 'pdf'

    month_name = (request.GET.get('month') or '').strip()
    year       = (request.GET.get('year') or '').strip()
    f_location = request.GET.get('location', '')
    f_site     = request.GET.get('site', '')
    f_bank     = request.GET.get('bank', '')
    f_search   = (request.GET.get('search', '') or '').lower()

    admin_id = get_admin_id(request.user)
    queryset = Employee.objects.filter(admin_id=admin_id).order_by('name')
    if f_location:
        queryset = queryset.filter(location=f_location)
    if f_site:
        queryset = queryset.filter(site=f_site)
    if f_bank:
        queryset = queryset.filter(bank_details__bank_name=f_bank)
    if f_search:
        queryset = queryset.filter(
            Q(name__icontains=f_search) | Q(employee_id__icontains=f_search)
        )

    target_date = None
    if month_name and year:
        try:
            m_idx = timezone_month_map(month_name)
            target_date = datetime.date(int(year), m_idx, 1)
        except Exception:
            target_date = None

    # Build rows — same derivation as salary_dashboard JSON branch.
    rows = []
    total_net = 0.0
    for e in queryset:
        # Mirror dashboard's idempotent base-salary back-fill so the download
        # never reports ₹0 for an employee just because their base hasn't
        # been viewed in the dashboard yet.
        if (not e.base_salary) and (not e.salary_is_custom_override) and (e.level or '').strip():
            _apply_role_level_salary(e, admin_id, force=False)
            if e.base_salary:
                e.save(update_fields=['base_salary', 'fixed_allowance'])

        if target_date:
            salary_record = e.salary_history.filter(
                month__year=target_date.year, month__month=target_date.month
            ).first()
        else:
            salary_record = e.salary_history.order_by('-month').first()

        gross_base = float(salary_record.basic_salary if salary_record else e.base_salary)
        ot         = float(salary_record.ot_allowance if salary_record else 0)
        advance    = float(salary_record.advance_pay if salary_record else 0)
        ded        = float(salary_record.total_deduction if salary_record else 0)
        ae_month   = (
            target_date
            or (salary_record.month if salary_record else timezone.now().date().replace(day=1))
        )
        try:
            earn_dec, _paid_dec = _compute_attendance_breakdown(e, ae_month, gross_base)
            attendance_earnings = float(earn_dec)
        except Exception as exc:
            print(f'[salary_report_download] attendance compute failed for emp {e.pk}: {exc}')
            attendance_earnings = gross_base
        net = attendance_earnings + ot - advance - ded

        bank = getattr(e, 'bank_details', None)
        rows.append({
            'emp_id':         e.employee_id or '',
            'emp_name':       e.name or '',
            'site':           e.site or '',
            'salary':         net,
            'bank_name':      bank.bank_name      if bank else '',
            'account_holder': bank.account_holder if bank else '',
            'account_number': bank.account_number if bank else '',
            'ifsc_code':      bank.ifsc_code      if bank else '',
        })
        total_net += net

    safe_month = (month_name or 'AllMonths').replace(' ', '_')
    safe_year  = (str(year) if year else 'AllYears').replace(' ', '_')
    filename_base = f"Salary_Report_{safe_month}_{safe_year}"
    period_label  = f"{month_name} {year}".strip() or "All Periods"

    if fmt == 'xlsx':
        return _render_salary_xlsx(rows, total_net, filename_base, period_label)
    return _render_salary_pdf(rows, total_net, filename_base, period_label)


def _render_salary_xlsx(rows, total_net, filename_base, period_label):
    """Build the salary report as an XLSX HttpResponse using openpyxl."""
    from io import BytesIO
    from django.http import HttpResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = 'Salary Report'

    headers = [
        'EMP ID', 'EMP NAME', 'SITE',
        'BANK NAME', 'ACCOUNT HOLDER', 'ACCOUNT NUMBER', 'IFSC CODE',
        'SALARY (₹)',
    ]
    ws.append(headers)
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill('solid', fgColor='1E293B')
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col_idx)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal='center')

    for r in rows:
        ws.append([
            r['emp_id'],
            r['emp_name'],
            r['site'],
            r['bank_name'],
            r['account_holder'],
            r['account_number'],
            r['ifsc_code'],
            float(r['salary'] or 0),
        ])

    # Blank separator + totals footer
    ws.append([])
    ws.append([
        f'Total Employees: {len(rows)}', '', '',
        '', 'Total Salary Paid', '', '',
        float(total_net or 0),
    ])

    widths = [14, 24, 18, 22, 26, 22, 18, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
    return response


def _render_salary_pdf(rows, total_net, filename_base, period_label):
    """Build the salary report as a landscape A4 PDF HttpResponse using reportlab."""
    from io import BytesIO
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title14', parent=styles['Title'], fontSize=14, alignment=0)
    sub_style   = ParagraphStyle('Sub8',    parent=styles['Normal'], fontSize=8)

    story = [
        Paragraph(f"Salary Report — {period_label}", title_style),
        Paragraph(
            f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            sub_style,
        ),
        Spacer(1, 6),
    ]

    table_data = [[
        'EMP ID', 'EMP NAME', 'SITE',
        'BANK NAME', 'ACCOUNT HOLDER', 'ACCOUNT NUMBER', 'IFSC CODE',
        'SALARY (Rs)',
    ]]
    for r in rows:
        table_data.append([
            r['emp_id']         or '-',
            r['emp_name']       or '-',
            r['site']           or '-',
            r['bank_name']      or '-',
            r['account_holder'] or '-',
            r['account_number'] or '-',
            r['ifsc_code']      or '-',
            '{:,.2f}'.format(float(r['salary'] or 0)),
        ])
    table_data.append([
        f'Total Employees: {len(rows)}', '', '',
        '', 'Total Salary Paid', '', '',
        '{:,.2f}'.format(float(total_net or 0)),
    ])

    col_widths = [55, 95, 75, 95, 110, 95, 70, 65]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0),  colors.HexColor('#1E293B')),
        ('TEXTCOLOR',  (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',   (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 7),
        ('ALIGN',      (7, 1), (7, -1),  'RIGHT'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F0FDF4')),
        ('TEXTCOLOR',  (0, -1), (-1, -1), colors.HexColor('#059669')),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(tbl)
    doc.build(story)

    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.pdf"'
    return response


def _compute_attendance_breakdown(employee, month_date, basic_salary):
    """
    Compute both the attendance-prorated payable base and the paid-days
    count for the given (employee, payroll month). Returns (final_salary,
    paid_days) both as Decimal.

    Cycle window: 26th of the previous month → 25th of `month_date`'s
    month — the SPIM 26→25 attendance cycle, matching the frontend
    attendance calendar.

    Future dates are excluded entirely (no pay for days that haven't
    happened yet). Future Sundays auto-marked Holiday by the backend
    backfill are also excluded by the explicit Sunday rule, kept as a
    defensive guard.

    See _compute_attendance_earnings for the formula and fallback semantics.
    """
    from attendance.models import AttendanceRecord

    # Coerce to Decimal to prevent float × Decimal TypeError
    basic_salary = Decimal(str(basic_salary))

    # ---- 26→25 cycle anchored on month_date's END month ----
    cycle_end = month_date.replace(day=25)
    if month_date.month == 1:
        prev = month_date.replace(year=month_date.year - 1, month=12)
    else:
        prev = month_date.replace(month=month_date.month - 1)
    cycle_start = prev.replace(day=26)

    # ---- CycleDays = actual calendar days in the cycle window ----
    cycle_days = (cycle_end - cycle_start).days + 1

    if cycle_days <= 0:
        # Defensive: never divide by zero.
        return basic_salary, Decimal('0')

    today = datetime.date.today()

    records = AttendanceRecord.objects.filter(
        employee=employee,
        date__gte=cycle_start,
        date__lte=cycle_end,
    ).filter(date__lte=today)

    # Salary Type branch. 'daily_basis' employees never receive the fixed
    # monthly-salary fallback and never divide by cycle_days — their
    # `base_salary` field holds a per-day rate and earnings are literally
    # rate × paid_days. 'base_salary' path below is byte-for-byte the
    # existing formula.
    is_daily = getattr(employee, 'salary_type', 'base_salary') == 'daily_basis'

    if not records.exists():
        if is_daily:
            # Daily-basis: no attendance → no earnings. Never surface the
            # per-day rate as a monthly "safe fallback".
            return Decimal('0'), Decimal('0')
        # No attendance marked — treat as fully paid (safe fallback).
        # Paid-days surfaced as CycleDays so the modal stays consistent
        # with the full-base earnings figure.
        return basic_salary, Decimal(str(cycle_days))

    # Defensive Sunday rule: even if a future-Sunday row leaked past the
    # date__lte=today filter, do not credit it.
    records_paid = records.exclude(
        date__week_day=1, date__gt=today,
    )

    present_days  = records_paid.filter(status='present').count()
    holiday_days  = records_paid.filter(status='holiday').count()
    half_days     = records_paid.filter(status='half_day').count()
    week_off_days = records_paid.filter(status='week_off').count()

    if is_daily:
        # Daily Basis: pay ONLY for full Present days.
        # Half Day / Holiday / Weekly Off / Sunday / Leave / Absent /
        # No Week Off all contribute 0 — daily-wage workers only earn
        # for days they were fully Present. This is the deliberate
        # business rule for this mode and differs from the Base Salary
        # paid-day formula, which stays untouched below.
        worked_days = Decimal(str(present_days))
        # daily_rate × worked_days — no cycle divisor, no cap.
        final_salary = (basic_salary * worked_days).quantize(Decimal('0.01'))
        return final_salary, worked_days

    # ---- PaidDays = pure sum of per-status weights (Base Salary only) ----
    paid_days = (
        Decimal(str(present_days))
        + Decimal(str(week_off_days))
        + Decimal(str(holiday_days))
        + (Decimal(str(half_days)) * Decimal('0.5'))
    )

    # ---- Final salary ----
    cycle_dec     = Decimal(str(cycle_days))
    daily_salary  = basic_salary / cycle_dec
    final_salary  = (daily_salary * paid_days).quantize(Decimal('0.01'))
    return final_salary, paid_days


def _compute_attendance_earnings(employee, month_date, basic_salary):
    """
    Attendance-prorated payable base from AttendanceRecord rows.

    Divisor:
      CycleDays = full calendar days in the month (28 / 29 / 30 / 31).

    Status pay weights (per business rule):
      - present     → 1.0  (full day pay)
      - week_off    → 1.0  (full day pay)
      - holiday     → 1.0  (full day pay; includes Sundays auto-marked Holiday)
      - half_day    → 0.5
      - leave       → 0.0
      - no_week_off → 0.0
      - absent      → 0.0

    PaidDays    = Present + WeekOff + Holiday + 0.5·HalfDay
    DailySalary = MonthlySalary / CycleDays
    FinalSalary = DailySalary × PaidDays

    Safe fallback: if no attendance records exist for the month, return
    the full basic_salary so payroll is never silently zeroed.

    The import of AttendanceRecord is deferred to avoid a circular import:
    attendance.models imports Employee from employees.models.
    """
    final_salary, _ = _compute_attendance_breakdown(employee, month_date, basic_salary)
    return final_salary


@login_required
@require_POST
def manage_ajax(request):
    """
    Unified AJAX endpoint for Salary Manager (salary_manager.html).
    """
    import json
    try:
        data = json.loads(request.body)
        emp_id = data.get('id')
        
        # 1. DELETE ACTION
        if data.get('action') == 'delete':
            employee = get_object_or_404(Employee, pk=emp_id, admin_id=get_admin_id(request.user))
            employee.delete()
            return JsonResponse({'success': True})

        # 1z. SALARY CONFIG CRUD ACTIONS (Tasks 3 + 4)
        # Body: { "action": "sc_list" }
        #     -> { success, configs: [{id, role, level, base_salary}, ...] }
        # Body: { "action": "sc_save", "role": "...", "level": "...", "base_salary": 30000 }
        #     -> upserts SalaryStructure(admin_id, JobRole(name=role), level)
        # Body: { "action": "sc_delete", "id": <pk> }
        #     -> deletes the SalaryStructure row (scoped to admin_id)
        # Source of truth: employees.SalaryStructure. Auto-applied to Employee
        # at Add and on role/level change via _apply_role_level_salary().
        if data.get('action') == 'sc_list':
            admin_id = get_admin_id(request.user)
            rows = (SalaryStructure.objects
                    .filter(admin_id=admin_id)
                    .select_related('job_role')
                    .order_by('job_role__name', 'level'))
            return JsonResponse({
                'success': True,
                'configs': [{
                    'id':          s.id,
                    'role':        s.job_role.name if s.job_role_id else '',
                    'level':       s.level,
                    'base_salary': float(s.base_salary),
                } for s in rows],
            })

        if data.get('action') == 'sc_save':
            role  = (data.get('role')  or '').strip()
            level = (data.get('level') or '').strip()
            try:
                base  = Decimal(str(data.get('base_salary') or 0))
            except Exception:
                base = Decimal('0')
            if not role or not level:
                return JsonResponse({'success': False, 'error': 'Role and Level are required.'}, status=400)
            if base <= 0:
                return JsonResponse({'success': False, 'error': 'Base salary must be greater than 0.'}, status=400)
            admin_id = get_admin_id(request.user)
            # All three DB writes are atomic: if the Employee bulk-update fails
            # the SalaryStructure write rolls back too — no partial state.
            with transaction.atomic():
                # Reuse-or-create JobRole by name (centralized role master).
                job_role, _ = JobRole.objects.get_or_create(admin_id=admin_id, name=role)
                structure, created = SalaryStructure.objects.update_or_create(
                    admin_id=admin_id, job_role=job_role, level=level,
                    defaults={'base_salary': base},
                )
                # Push the new base to every employee that already matches this
                # mapping so SPIM Lite Salary / Payslip generation reflect right
                # away (Task 4 — "Prevent stale values"). Employees with a manual
                # salary override are deliberately skipped (Case 3 of the
                # override spec).
                Employee.objects.filter(
                    admin_id=admin_id, level=level, job_role=job_role,
                    salary_is_custom_override=False,
                ).update(base_salary=base)
                Employee.objects.filter(
                    admin_id=admin_id, level=level, designation__iexact=role,
                    salary_is_custom_override=False,
                ).update(base_salary=base)
            return JsonResponse({
                'success': True, 'created': created,
                'config': {
                    'id': structure.id, 'role': role,
                    'level': level, 'base_salary': float(base),
                },
            })

        if data.get('action') == 'sc_delete':
            sid = data.get('id')
            if not sid:
                return JsonResponse({'success': False, 'error': 'id is required.'}, status=400)
            admin_id = get_admin_id(request.user)
            SalaryStructure.objects.filter(admin_id=admin_id, pk=sid).delete()
            return JsonResponse({'success': True})

        # 1a. MASTER ADD ACTION
        # Body: { "action": "master_add", "kind": "role|level|location|site", "value": "..." }
        # Upserts the new master value into the existing model for the
        # current tenant. Returns the canonical value so the client can
        # append it to the dropdown without a page reload.
        if data.get('action') == 'master_add':
            kind  = (data.get('kind')  or '').strip().lower()
            value = (data.get('value') or '').strip()
            if not value:
                return JsonResponse({'success': False, 'error': 'Value cannot be empty.'}, status=400)
            admin_id = get_admin_id(request.user)
            if kind == 'role':
                JobRole.objects.get_or_create(admin_id=admin_id, name=value)
            elif kind == 'level':
                EmployeeLevel.objects.get_or_create(admin_id=admin_id, name=value)
            elif kind in ('location', 'site'):
                # LocationSite holds combined "<location> / <site>" entries.
                # When admin adds a bare location or bare site, store it as
                # a standalone name so it shows up in either dropdown's pool.
                from branches.models import LocationSite as _LS
                _LS.objects.get_or_create(admin_id=admin_id, name=value, defaults={'created_by': request.user})
            else:
                return JsonResponse({'success': False, 'error': f'Unknown kind: {kind}'}, status=400)
            return JsonResponse({'success': True, 'kind': kind, 'value': value})

        # 1c. BATCH GENERATE PAYSLIPS ACTION
        # Body: { "action": "generate_payslips_batch", "month": "January", "year": "2026" }
        # Single-click flow:
        #   1. Flip is_payslip_generated on every SalaryUpdate row for the
        #      tenant + cycle. Skips rows that are already generated so a
        #      repeat click is a no-op for that subset.
        #   2. Delegate to the existing generate_salary_expenses flow, which
        #      is already idempotent via the Transaction.reference dedup key
        #      ("SAL-{employee_pk}-{YYYY-MM}"). No duplicate expense rows.
        #   3. If every row in the cycle was already generated AND every
        #      matching expense already exists, return an early "already
        #      generated" message without touching anything.
        if data.get('action') == 'generate_payslips_batch':
            month_name = (data.get('month') or '').strip()
            year_str   = (data.get('year') or '').strip()
            if not month_name or not year_str:
                return JsonResponse({'success': False, 'error': 'month and year are required.'}, status=400)
            try:
                target_date = datetime.date(int(year_str), timezone_month_map(month_name), 1)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Invalid month/year.'}, status=400)
            admin_id = get_admin_id(request.user)
            tenant_emps = Employee.objects.filter(admin_id=admin_id)
            rows = SalaryUpdate.objects.filter(
                employee__in=tenant_emps,
                month__year=target_date.year,
                month__month=target_date.month,
            )
            if not rows.exists():
                return JsonResponse({
                    'success': False,
                    'error': f'No salary records for {month_name} {year_str}. Process salaries before generating payslips.',
                }, status=400)

            already_locked = rows.filter(is_payslip_generated=True).count()
            total          = rows.count()

            # If every row is already locked, treat as a no-op so a stray
            # double-click does not re-trigger expense generation.
            if already_locked == total:
                return JsonResponse({
                    'success': True,
                    'already_generated': True,
                    'message': f'Payslips already generated for {month_name} {year_str}.',
                    'locked':  total,
                })

            # Lock all rows for this cycle
            rows.filter(is_payslip_generated=False).update(
                is_payslip_generated=True,
                payslip_generated_at=timezone.now(),
                payslip_generated_by=request.user,
            )

            # Reuse the idempotent expense-generation path. We call its
            # internals via the public view by reconstructing the body.
            from django.test import RequestFactory
            rf      = RequestFactory()
            sub_req = rf.post(
                '/employees/generate-salary-expenses/',
                data=json.dumps({'month': month_name, 'year': year_str}),
                content_type='application/json',
            )
            sub_req.user = request.user
            sub_resp = generate_salary_expenses(sub_req)
            try:
                sub_data = json.loads(sub_resp.content.decode('utf-8'))
            except Exception:
                sub_data = {}

            return JsonResponse({
                'success': True,
                'already_generated': False,
                'locked':  total,
                'expense_created': sub_data.get('created', 0),
                'expense_skipped': sub_data.get('skipped', 0),
                'message': f'Payslips generated for {month_name} {year_str}. '
                           f'{sub_data.get("created", 0)} expense entries created, '
                           f'{sub_data.get("skipped", 0)} already existed.',
            })

        # 1b. GENERATE PAYSLIP ACTION (Task 4)
        # Body: { "action": "generate_payslip", "id": <employee_pk>, "month": "January", "year": "2026" }
        # Flips the payslip lock on the SalaryUpdate row for the given cycle.
        # Employee can only download once this is set.
        if data.get('action') == 'generate_payslip':
            employee = get_object_or_404(Employee, pk=emp_id, admin_id=get_admin_id(request.user))
            month_name = (data.get('month') or '').strip()
            year_str   = (data.get('year') or '').strip()
            if not month_name or not year_str:
                return JsonResponse({'success': False, 'error': 'month and year are required.'}, status=400)
            try:
                target_date = datetime.date(int(year_str), timezone_month_map(month_name), 1)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'Invalid month/year.'}, status=400)
            salary_record = SalaryUpdate.objects.filter(
                employee=employee, month=target_date,
            ).first()
            if not salary_record:
                return JsonResponse({
                    'success': False,
                    'error': 'No salary record for this cycle. Process salary before generating the payslip.',
                }, status=400)
            salary_record.is_payslip_generated = True
            salary_record.payslip_generated_at = timezone.now()
            salary_record.payslip_generated_by = request.user
            salary_record.save(update_fields=[
                'is_payslip_generated', 'payslip_generated_at', 'payslip_generated_by',
            ])
            return JsonResponse({'success': True, 'payslip_id': salary_record.id, 'is_generated': True})
            
        # 2. BANK UPDATE
        if 'bank' in data:
            employee = get_object_or_404(Employee, pk=emp_id, admin_id=get_admin_id(request.user))
            bank_data = data['bank']
            bank_detail, _ = BankDetail.objects.get_or_create(employee=employee)
            bank_detail.bank_name = bank_data.get('bank_name', '')
            bank_detail.account_holder = bank_data.get('holder', '')
            bank_detail.account_number = bank_data.get('account', '')
            bank_detail.ifsc_code = bank_data.get('ifsc', '')
            bank_detail.save()
            return JsonResponse({'success': True})

        # 3. PF UPDATE
        if 'pf' in data:
            employee = get_object_or_404(Employee, pk=emp_id, admin_id=get_admin_id(request.user))
            pf_data = data['pf']
            pf_detail, _ = PFDetail.objects.get_or_create(employee=employee)
            pf_detail.pf_number = pf_data.get('pf_number', '')
            pf_detail.esic_number = pf_data.get('esic', '')
            pf_detail.save()
            return JsonResponse({'success': True})

        # 4. SALARY ADJUSTMENT (or Create New)
        if 'salary' in data:
            employee = get_object_or_404(Employee, pk=emp_id, admin_id=get_admin_id(request.user))

            # Persist Role + Level back to the Employee record so the SPIM Lite
            # profile and salary chain stay in sync (Task 1 + Task 2). The
            # Salary Edit modal previously kept these in localStorage only,
            # which is why Level disappeared in SPIM Lite even though the
            # admin had "set" it via the salary modal.
            posted_role  = (data.get('role')  or '').strip()
            posted_level = (data.get('level') or '').strip()
            emp_dirty_fields = []
            if posted_role and posted_role != (employee.designation or ''):
                employee.designation = posted_role
                emp_dirty_fields.append('designation')
            if posted_level and posted_level != (employee.level or ''):
                employee.level = posted_level
                emp_dirty_fields.append('level')
            # Salary Type persistence. Blank / unknown values fall back to
            # 'base_salary' so the existing payroll flow is preserved. Only
            # a real change writes to the DB so untouched rows stay clean.
            posted_stype = (data.get('salary_type') or '').strip().lower()
            if posted_stype not in ('base_salary', 'daily_basis'):
                posted_stype = ''
            if posted_stype and posted_stype != (getattr(employee, 'salary_type', 'base_salary') or 'base_salary'):
                employee.salary_type = posted_stype
                emp_dirty_fields.append('salary_type')
            try:
                posted_base = Decimal(str(data.get('salary') or 0))
            except Exception:
                posted_base = Decimal('0')
            if posted_base > 0 and posted_base != employee.base_salary:
                employee.base_salary = posted_base
                emp_dirty_fields.append('base_salary')
                # Manual-override detection (Case 3). Compare the typed value
                # against the current Salary Config for this Role + Level. If
                # it differs, mark the employee as overridden so neither future
                # Salary Config edits nor role/level changes overwrite it.
                # If it matches the config exactly, clear the override flag so
                # the row resumes following the centralized mapping.
                admin_id = get_admin_id(request.user)
                cfg_base = None
                if employee.job_role_id and (employee.level or '').strip():
                    s = SalaryStructure.objects.filter(
                        admin_id=admin_id, job_role_id=employee.job_role_id,
                        level=employee.level.strip(),
                    ).first()
                    if s:
                        cfg_base = Decimal(str(s.base_salary))
                if cfg_base is None and (employee.designation or '').strip() and (employee.level or '').strip():
                    s = SalaryStructure.objects.filter(
                        admin_id=admin_id,
                        job_role__admin_id=admin_id,
                        job_role__name__iexact=employee.designation.strip(),
                        level=employee.level.strip(),
                    ).first()
                    if s:
                        cfg_base = Decimal(str(s.base_salary))
                new_override = (cfg_base is None) or (posted_base != cfg_base)
                if new_override != employee.salary_is_custom_override:
                    employee.salary_is_custom_override = new_override
                    emp_dirty_fields.append('salary_is_custom_override')
            if emp_dirty_fields:
                employee.save(update_fields=emp_dirty_fields)

            # Use provided month/year or default to current
            month_name = data.get('month', '')
            year = data.get('year', '')
            
            if month_name and year:
                m_idx = timezone_month_map(month_name)
                target_date = datetime.date(int(year), m_idx, 1)
            else:
                target_date = timezone.now().date().replace(day=1)

            salary_record, created = SalaryUpdate.objects.get_or_create(
                employee=employee,
                month=target_date,
                defaults={'created_by': request.user}
            )
            
            def _parse_decimal(val):
                if val is None or str(val).strip() == '':
                    return Decimal('0')
                try:
                    return Decimal(str(val))
                except Exception:
                    return Decimal('0')

            basic          = _parse_decimal(data.get('salary', 0))
            ot             = _parse_decimal(data.get('ot', 0))
            advance        = _parse_decimal(data.get('advance', 0))
            deduction      = _parse_decimal(data.get('deduction', 0))
            pf_amount      = _parse_decimal(data.get('pf_amount', 0))
            food_allowance = _parse_decimal(data.get('food_allowance', 0))
            food_usage     = _parse_decimal(data.get('food_usage', 0))

            # food_adjustment: positive → added to pay, negative → deducted
            food_adjustment = food_allowance - food_usage

            salary_record.basic_salary         = basic
            salary_record.ot_allowance         = ot
            salary_record.advance_pay          = advance
            salary_record.total_deduction      = deduction
            salary_record.pf_employee_snapshot = pf_amount
            salary_record.food_allowance       = food_allowance
            salary_record.food_usage           = food_usage

            # Compute the payable base server-side from AttendanceRecord rows.
            # The client-sent attendance_earnings is discarded — the server
            # derives the value directly from the database to prevent payload
            # manipulation.
            payable_base = _compute_attendance_earnings(employee, target_date, basic)
            salary_record.net_pay = payable_base + ot - advance - deduction + food_adjustment
            salary_record.save()
            
            return JsonResponse({'success': True})

        # 5. ADD NEW EMPLOYEE
        if 'name' in data:
            employee = Employee.objects.create(
                name=data['name'],
                designation=data.get('role', ''),
                location=data.get('location', ''),
                site=data.get('site', ''),
                base_salary=data.get('salary', 0),
                admin_id=get_admin_id(request.user),
                created_by=request.user
            )
            # Handle nested bank/pf if provided
            if 'bank' in data:
                b = data['bank']
                BankDetail.objects.create(
                    employee=employee,
                    bank_name=b.get('bank_name', ''),
                    account_holder=b.get('holder', ''),
                    account_number=b.get('account', ''),
                    ifsc_code=b.get('ifsc', '')
                )
            if 'pf' in data:
                p = data['pf']
                PFDetail.objects.create(
                    employee=employee,
                    pf_number=p.get('pf_number', ''),
                    esic_number=p.get('esic', '')
                )
            return JsonResponse({'success': True, 'id': employee.id})

        return JsonResponse({'success': False, 'error': 'Invalid request data'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def add_salary(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(Employee, pk=employee_id, admin_id=get_admin_id(request.user))
        form = SalaryForm(request.POST)
        if form.is_valid():
            salary = form.save(commit=False)
            salary.employee = employee
            salary.created_by = request.user
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
    from dashboard.models import CompanySettings
    admin_id = get_admin_id(request.user)
    salary   = get_object_or_404(SalaryUpdate, pk=pk, employee__admin_id=admin_id)
    return render(request, 'employees/payslip.html', {
        'salary':   salary,
        'employee': salary.employee,
        'company':  CompanySettings.get_settings(admin_id),
    })


@login_required
@require_POST
def generate_salary_expenses(request):
    """
    Generate one expense Transaction per employee salary record for the given
    month/year.  Duplicate generation is blocked via a stable reference key
    stored on the Transaction (SAL-{employee_pk}-{YYYY-MM}).  Employee-level
    payroll details are NOT written to any expense field shown in the UI.
    """
    from finance.models import Transaction, Category

    try:
        data = json.loads(request.body)
        month_name = data.get('month', '').strip()
        year_str   = data.get('year', '').strip()

        if not month_name or not year_str:
            return JsonResponse({'success': False, 'error': 'Month and year are required.'})

        m_idx       = timezone_month_map(month_name)
        year        = int(year_str)
        target_date = datetime.date(year, m_idx, 1)
        admin_id    = get_admin_id(request.user)

        # Optional: income source and account for balance combo linking.
        # When provided, generated salary expenses will deduct from the matching
        # income source/account balance.  When omitted, expenses are recorded
        # without combo linkage (no balance deduction), which is the legacy
        # behaviour.
        income_source_val = data.get('income_source', '').strip()
        account_val       = data.get('account', '').strip()

        # Resolve all employees belonging to this tenant
        tenant_employees = Employee.objects.filter(admin_id=admin_id)

        salary_records = SalaryUpdate.objects.filter(
            employee__in=tenant_employees,
            month__year=target_date.year,
            month__month=target_date.month,
        ).select_related('employee')

        if not salary_records.exists():
            return JsonResponse({
                'success': False,
                'error': f'No salary records found for {month_name} {year}. Process salaries first.',
            })

        # Get or create the "Salary" expense category for this tenant
        salary_category, _ = Category.objects.get_or_create(
            admin_id=admin_id,
            name='Salary',
            type='expense',
            defaults={'created_by': request.user, 'modified_by': request.user},
        )

        # Expense date = last day of the payroll month
        last_day     = calendar.monthrange(year, m_idx)[1]
        expense_date = datetime.date(year, m_idx, last_day)
        description  = f"Salary payout for {month_name} {year}"

        created_count = 0
        skipped_count = 0

        for record in salary_records:
            emp     = record.employee
            ref_key = f"SAL-{emp.pk}-{target_date.strftime('%Y-%m')}"

            # Dedup: skip if already generated for this employee + cycle
            if Transaction.objects.filter(
                admin_id=admin_id,
                reference=ref_key,
                type='expense',
            ).exists():
                skipped_count += 1
                continue

            loc  = (emp.location or '').strip()
            site = (emp.site or '').strip()
            location_site = f"{loc} / {site}" if loc and site else (loc or site or '')

            Transaction.objects.create(
                user          = request.user,
                type          = 'expense',
                category      = salary_category,
                amount        = record.net_pay,
                description   = description,
                date          = expense_date,
                purpose       = 'Employee Salary',
                location_site = location_site,
                reference     = ref_key,
                income_source = income_source_val,
                payment_mode  = account_val,
                admin_id      = admin_id,
                created_by    = request.user,
            )
            created_count += 1

        msg = f"{created_count} expense(s) generated for {month_name} {year}."
        if skipped_count:
            msg += f" {skipped_count} skipped (already exist)."

        return JsonResponse({'success': True, 'created': created_count, 'skipped': skipped_count, 'message': msg})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
