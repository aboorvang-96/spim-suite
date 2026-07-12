from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import MultipleObjectsReturned
from employees.models import Employee
from accounts.views import get_admin_id
from .models import AttendanceRecord
from .utils import display_status
import datetime
import json

@login_required
def index(request):
    try:
        admin_id = get_admin_id(request.user)
        employees = Employee.objects.filter(admin_id=admin_id)
    except AttributeError:
        # Prevent multi-tenant data leakage - require valid admin_id
        return HttpResponseForbidden("User must have valid admin context to access attendance")
        
    emp_list = []
    for emp in employees:
        # EMP ID must come from the employee_id column only — never the PK.
        # Employees missing an employee_id surface as blank so admins can
        # spot and backfill them via the (now unlocked) Edit form.
        # `pk` is a separate, internal-only field used by the client so
        # save/edit/delete still resolve to the right Employee row when
        # `employee_id` happens to be blank. It is never displayed as
        # the EMP ID.
        emp_list.append({
            'id': emp.employee_id or '',
            'pk': emp.pk,
            'name': emp.name,
            'dept': emp.department or '',
            'role': emp.designation or '',
            'mainLocation': emp.location or '',
            'site': emp.site or '',
            'leave': '0',
            'baseSalary': float(emp.base_salary) if emp.base_salary else 0,
            'salaryType': emp.salary_type or 'base_salary'
        })
        
    context = {
        'employees_json': json.dumps(emp_list)
    }
    return render(request, 'attendance/index.html', context)

@login_required
def save_attendance(request):
    if request.method == 'POST':
        try:
            # Prefer JSON body; fall back to form-POST field named 'data' or 'records'
            content_type = request.content_type or ''
            if 'application/json' in content_type:
                data = json.loads(request.body)
            else:
                try:
                    data = json.loads(request.body)
                except (json.JSONDecodeError, ValueError):
                    raw = request.POST.get('data') or request.POST.get('records') or '[]'
                    data = json.loads(raw)
            admin_id = get_admin_id(request.user)
            
            # Assuming data is a list of attendance records
            for record in data:
                emp_id = record.get('empId')
                emp_pk = record.get('pk')
                # Find employee by employee_id, falling back to the explicit
                # `pk` field, then to numeric empId (legacy localStorage rows
                # that stored the PK in the empId slot). Empty empId is no
                # longer a hard skip — when the client provides `pk`, the
                # lookup still resolves. This is the fix for the silent
                # "26 admin marks vanish on refresh" + "1 employee missing"
                # bugs caused by employees with a blank employee_id column.
                emp = None
                if emp_id:
                    try:
                        emp = Employee.objects.get(employee_id=emp_id, admin_id=admin_id)
                    except (Employee.DoesNotExist, MultipleObjectsReturned):
                        emp = None
                if emp is None and emp_pk:
                    try:
                        emp = Employee.objects.get(pk=emp_pk, admin_id=admin_id)
                    except (Employee.DoesNotExist, MultipleObjectsReturned, ValueError, TypeError):
                        emp = None
                if emp is None and emp_id:
                    try:
                        emp = Employee.objects.get(id=emp_id, admin_id=admin_id)
                    except (Employee.DoesNotExist, MultipleObjectsReturned, ValueError):
                        emp = None
                if emp is None:
                    continue
                
                date = record.get('date')
                status = record.get('status', 'Present').lower()
                # Site / Working Site (new — Mod 1 sync from admin UI).
                # Optional; when omitted the existing record's values
                # survive via the `defaults` mechanism below.
                site_val         = (record.get('site')         or '').strip()
                working_site_val = (record.get('workingSite')  or record.get('working_site') or '').strip()
                # Status mapping to match our model (extended for new
                # payroll rules — holiday / week_off / no_week_off are now
                # distinct enums; UI variants like "Weekly Off" normalise
                # to 'week_off'). 'half day' kept for back-compat.
                status_map = {
                    'present':      'present',
                    'absent':       'absent',
                    'half day':     'half_day',
                    'half_day':     'half_day',
                    'half-day':     'half_day',
                    'leave':        'leave',
                    'holiday':      'holiday',
                    'week off':     'week_off',
                    'week_off':     'week_off',
                    'weekly off':   'week_off',
                    'no week off':  'no_week_off',
                    'no_week_off':  'no_week_off',
                }
                model_status = status_map.get(status, 'present')
                
                defaults = {
                    'admin_id': admin_id,
                    'status':   model_status,
                    'source':   'admin',
                    'created_by': request.user,
                }
                # Only persist site / working_site when the client actually
                # sent them, so an admin bulk save that omits the new fields
                # doesn't wipe out a value previously set by the employee.
                if site_val:
                    defaults['site'] = site_val
                if working_site_val:
                    defaults['working_site'] = working_site_val

                # Remarks: persist when supplied. Once a non-empty remark
                # is saved the row is locked; further remark changes require
                # an explicit unlock so a bulk save can't clobber the note.
                remarks_raw = record.get('remarks')
                remarks_val = (remarks_raw or '').strip() if remarks_raw is not None else None

                existing = AttendanceRecord.objects.filter(
                    employee=emp, date=date,
                ).only('remarks', 'remarks_locked').first()

                if remarks_val is not None:
                    if existing and existing.remarks_locked:
                        # Locked — keep existing remark, ignore incoming.
                        pass
                    else:
                        defaults['remarks'] = remarks_val
                        defaults['remarks_locked'] = bool(remarks_val)

                AttendanceRecord.objects.update_or_create(
                    employee=emp,
                    date=date,
                    defaults=defaults,
                )
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def load_attendance(request):
    """Return DB attendance records for this org so all linked admins share visibility."""
    admin_id = get_admin_id(request.user)
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    qs = AttendanceRecord.objects.filter(admin_id=admin_id).select_related('employee')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    # STATUS_DISPLAY + Sunday-remap live in attendance.utils.display_status,
    # so this view and the SPIM Lite HR mobile endpoint call the same helper
    # (no duplicated Sunday logic).
    records = [{
        'empId':   r.employee.employee_id or '',
        'empPk':   r.employee.pk,  # internal lookup key — never displayed as EMP ID
        'empName': r.employee.name,
        'date':    r.date.isoformat(),
        'status':  display_status(r),
        # Site / Working Site — defensive getattr so this view stays alive
        # even before migration 0004 has been applied to the Suite DB.
        'site':        getattr(r, 'site',         '') or '',
        'workingSite': getattr(r, 'working_site', '') or '',
        'remarks':        getattr(r, 'remarks', '') or '',
        'remarksLocked':  bool(getattr(r, 'remarks_locked', False)),
    } for r in qs]

    return JsonResponse({'success': True, 'records': records})


@login_required
def delete_attendance(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            admin_id = get_admin_id(request.user)
            emp_id = data.get('empId')
            emp_pk = data.get('pk')
            date = data.get('date')
            if not emp_id and not emp_pk:
                return JsonResponse({'success': False, 'error': 'Employee ID is required'})
            # Mirror save_attendance's lookup order so legacy records with a
            # blank employee_id can still be deleted via their `pk` field.
            emp = None
            if emp_id:
                try:
                    emp = Employee.objects.get(employee_id=emp_id, admin_id=admin_id)
                except (Employee.DoesNotExist, MultipleObjectsReturned):
                    emp = None
            if emp is None and emp_pk:
                try:
                    emp = Employee.objects.get(pk=emp_pk, admin_id=admin_id)
                except (Employee.DoesNotExist, MultipleObjectsReturned, ValueError, TypeError):
                    emp = None
            if emp is None and emp_id:
                try:
                    emp = Employee.objects.get(id=emp_id, admin_id=admin_id)
                except (Employee.DoesNotExist, MultipleObjectsReturned, ValueError):
                    emp = None
            if emp is None:
                return JsonResponse({'success': False, 'error': 'Employee not found'})
            
            AttendanceRecord.objects.filter(employee=emp, date=date, admin_id=admin_id).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def unlock_remarks(request):
    """Clear the remarks_locked flag on a single (employee, date) row so
    the admin can edit the remark. The remark text itself is preserved."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request'})
    try:
        data     = json.loads(request.body or '{}')
        admin_id = get_admin_id(request.user)
        emp_id   = data.get('empId')
        emp_pk   = data.get('pk')
        date     = data.get('date')
        if not date:
            return JsonResponse({'success': False, 'error': 'Date is required'})

        emp = None
        if emp_id:
            try:
                emp = Employee.objects.get(employee_id=emp_id, admin_id=admin_id)
            except (Employee.DoesNotExist, MultipleObjectsReturned):
                emp = None
        if emp is None and emp_pk:
            try:
                emp = Employee.objects.get(pk=emp_pk, admin_id=admin_id)
            except (Employee.DoesNotExist, MultipleObjectsReturned, ValueError, TypeError):
                emp = None
        if emp is None:
            return JsonResponse({'success': False, 'error': 'Employee not found'})

        updated = AttendanceRecord.objects.filter(
            employee=emp, date=date, admin_id=admin_id,
        ).update(remarks_locked=False)
        return JsonResponse({'success': True, 'updated': updated})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
