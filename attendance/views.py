from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db import transaction
from django.db.models import Count
from employees.models import Employee
from accounts.views import get_admin_id
from accounts.date_utils import validate_not_future
from projects.models import MachineLocation, ProjectClient, Site
from .models import AttendanceRecord
from .services import apply_worklog_sideeffect, cleanup_worklog_on_delete
from .utils import display_status
import datetime
import json


# Map every casing / spacing variant the client might POST to the model
# enum. Extended for the payroll rules — holiday / week_off / no_week_off
# are distinct; 'half day' preserved for back-compat.
_STATUS_MAP = {
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


def _resolve_employee(admin_id, emp_id, emp_pk):
    """Same three-step resolution used by save/delete/unlock — kept in one
    place so the fallback order stays consistent across all write paths."""
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
    return emp


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

    # Read-only Projects registry for the Add-Machine modal's site dropdown
    # (grouped by client). Embedded at render — no extra endpoint needed.
    project_clients = list(
        ProjectClient.objects.filter(admin_id=admin_id, is_active=True)
        .values('id', 'name').order_by('name')
    )
    project_sites = list(
        Site.objects.filter(admin_id=admin_id, is_active=True)
        .values('id', 'name', 'client_id').order_by('name')
    )

    context = {
        'employees_json': json.dumps(emp_list),
        # UX-only gate — the "+ Add machine" affordance in the row-level
        # autocomplete hides for non-admins. The authoritative check still
        # lives on /projects/machines/add/ via @admin_required.
        'is_admin':       bool(getattr(request.user, 'is_admin', False)),
        'project_clients_json': json.dumps(project_clients),
        'project_sites_json':   json.dumps(project_sites),
    }
    return render(request, 'attendance/index.html', context)


@login_required
def save_attendance(request):
    """
    Bulk upsert AttendanceRecord rows.

    Per-record atomic transactions: each record's attendance write + its
    optional projects.WorkLog side-effect (see attendance.services) succeed
    or fail together. A failure on one row does not roll back the others —
    failed rows are surfaced in the `failures` list so the client can
    highlight them for the admin.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request'})

    try:
        # Prefer JSON body; fall back to form-POST field named 'data'/'records'.
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            data = json.loads(request.body)
        else:
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                raw = request.POST.get('data') or request.POST.get('records') or '[]'
                data = json.loads(raw)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Malformed payload: {e}'})

    admin_id = get_admin_id(request.user)
    saved = 0
    failures = []

    for idx, record in enumerate(data):
        emp_id = record.get('empId')
        emp_pk = record.get('pk')
        emp    = _resolve_employee(admin_id, emp_id, emp_pk)
        if emp is None:
            # Silent skip — matches historical behaviour for unresolvable
            # rows so a bad localStorage entry doesn't break a bulk save.
            continue

        date_val = record.get('date')
        # Reject malformed / future dates up front (IST-anchored) so the
        # row fails with the standard message instead of surfacing whatever
        # update_or_create happens to raise. Model.save() still re-checks
        # as a backstop for any other write path.
        try:
            validate_not_future(date_val, "Attendance date")
        except ValidationError as e:
            failures.append({
                'rowIndex':   idx,
                'employeeId': emp_id or '',
                'error':      '; '.join(e.messages),
            })
            continue
        raw_status = (record.get('status') or 'Present').lower()
        model_status = _STATUS_MAP.get(raw_status, 'present')

        # Optional per-record fields. Only persisted when supplied so an
        # admin bulk save that omits them doesn't clobber a value set
        # earlier by SPIM Lite.
        site_val         = (record.get('site')        or '').strip()
        working_site_val = (record.get('workingSite') or record.get('working_site') or '').strip()

        # New (2026-07): machine FK + work_details free-text.
        machine_id_raw = record.get('machineId') or record.get('machine_id')
        try:
            machine_id = int(machine_id_raw) if machine_id_raw else None
        except (TypeError, ValueError):
            machine_id = None

        # Client/Site FK pair (2026-07 Client/Site column).
        def _as_id(*keys):
            for k in keys:
                if k in record:
                    try:
                        return int(record.get(k) or 0) or None, True
                    except (TypeError, ValueError):
                        return None, True
            return None, False

        client_id, client_in_payload = _as_id('clientId', 'client_id')
        site_id,   site_in_payload   = _as_id('siteId')

        work_details_val = record.get('workDetails')
        if work_details_val is None:
            work_details_val = record.get('work_details')
        work_details_val = (work_details_val or '').strip()

        defaults = {
            'admin_id':   admin_id,
            'status':     model_status,
            'source':     'admin',
            'created_by': request.user,
        }
        if site_val:
            defaults['site'] = site_val
        if working_site_val:
            defaults['working_site'] = working_site_val

        # `machineId` present in payload → authoritative for this save
        # (including clearing to null via explicit "" / null / 0).
        if 'machineId' in record or 'machine_id' in record:
            defaults['machine'] = None
            if machine_id:
                machine_obj = MachineLocation.objects.filter(
                    pk=machine_id, admin_id=admin_id,
                ).first()
                if not machine_obj:
                    failures.append({
                        'rowIndex':   idx,
                        'employeeId': emp_id or '',
                        'error':      'Machine not found for this tenant.',
                    })
                    continue
                defaults['machine'] = machine_obj

        # Same convention for work_details — presence in payload means
        # authoritative, so admins can clear it by sending an empty string.
        if 'workDetails' in record or 'work_details' in record:
            defaults['work_details'] = work_details_val

        # Client/Site FKs — presence in payload is authoritative (null
        # clears). Both are validated against the tenant; when a Site is
        # resolved, the legacy `site` CharField is refreshed with its name
        # so mobile/HR consumers keep seeing a coherent site string.
        site_obj = None
        if site_in_payload:
            defaults['site_ref'] = None
            if site_id:
                site_obj = Site.objects.filter(
                    pk=site_id, admin_id=admin_id,
                ).select_related('client').first()
                if not site_obj:
                    failures.append({
                        'rowIndex':   idx,
                        'employeeId': emp_id or '',
                        'error':      'Site not found for this tenant.',
                    })
                    continue
                defaults['site_ref'] = site_obj
                defaults['site']     = site_obj.name
        if client_in_payload:
            defaults['client'] = None
            if client_id:
                client_obj = ProjectClient.objects.filter(
                    pk=client_id, admin_id=admin_id,
                ).first()
                if not client_obj:
                    failures.append({
                        'rowIndex':   idx,
                        'employeeId': emp_id or '',
                        'error':      'Client not found for this tenant.',
                    })
                    continue
                defaults['client'] = client_obj

        # Defense against tampering: a machine pick must agree with the
        # site pick. The UI enforces this (Flow 1 filter / Flow 2 confirm);
        # a mismatching payload is rejected rather than silently repaired.
        if defaults.get('machine') and site_id \
                and defaults['machine'].site_id != site_id:
            failures.append({
                'rowIndex':   idx,
                'employeeId': emp_id or '',
                'error':      'Machine does not belong to the selected site.',
            })
            continue

        # Remarks: persist when supplied, and lock the row once a non-empty
        # remark is stored. Locked rows silently ignore incoming remark
        # changes until the admin explicitly unlocks.
        remarks_raw = record.get('remarks')
        remarks_val = (remarks_raw or '').strip() if remarks_raw is not None else None

        existing_snapshot = AttendanceRecord.objects.filter(
            employee=emp, date=date_val,
        ).only('remarks', 'remarks_locked', 'machine_id').first()

        if remarks_val is not None:
            if existing_snapshot and existing_snapshot.remarks_locked:
                pass  # keep existing; block the bulk overwrite
            else:
                defaults['remarks'] = remarks_val
                defaults['remarks_locked'] = bool(remarks_val)

        prev_machine_id = existing_snapshot.machine_id if existing_snapshot else None

        try:
            with transaction.atomic():
                rec, _ = AttendanceRecord.objects.update_or_create(
                    employee=emp,
                    date=date_val,
                    defaults=defaults,
                )
                # WorkLog side-effect. Raises on cross-tenant machine, DB
                # errors, etc. — atomic block rolls back the attendance row
                # AND any partial M2M write.
                apply_worklog_sideeffect(rec, prev_machine_id, request.user)
        except ValidationError as e:
            # Model.save() raises this for future dates (and any other
            # clean() rule). Surface the joined message rather than the
            # repr so the UI shows a clean sentence.
            failures.append({
                'rowIndex':   idx,
                'employeeId': emp_id or '',
                'error':      '; '.join(e.messages),
            })
            continue
        except Exception as e:
            failures.append({
                'rowIndex':   idx,
                'employeeId': emp_id or '',
                'error':      str(e),
            })
            continue

        saved += 1

    return JsonResponse({
        'success':  True,
        'saved':    saved,
        'failures': failures,
    })


@login_required
def load_attendance(request):
    """Return DB attendance records for this org so all linked admins share visibility."""
    admin_id = get_admin_id(request.user)
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    qs = (
        AttendanceRecord.objects
        .filter(admin_id=admin_id)
        .select_related('employee', 'machine', 'client', 'site_ref', 'site_ref__client')
    )
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
        # New (2026-07): machine FK + work_details for the Attendance ↔
        # Projects integration. `machineId` is null when the row isn't
        # linked to a machine; `machineName` is a display convenience
        # so the client doesn't need a second lookup.
        'machineId':   r.machine_id,
        'machineName': r.machine.name if r.machine_id else '',
        'workDetails': getattr(r, 'work_details', '') or '',
        # Client/Site FK pair (2026-07). Null for rows saved before the
        # Client/Site column existed. Label is precomputed server-side so
        # the client hydrates the input without a second lookup.
        'clientId':        r.client_id,
        'siteId':          r.site_ref_id,
        'clientSiteLabel': (
            f'{r.site_ref.client.name} / {r.site_ref.name}'
            if r.site_ref_id and r.site_ref.client_id
            else (r.site_ref.name if r.site_ref_id else '')
        ),
    } for r in qs]

    return JsonResponse({'success': True, 'records': records})


@login_required
def delete_attendance(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request'})
    try:
        data = json.loads(request.body)
        admin_id = get_admin_id(request.user)
        emp_id = data.get('empId')
        emp_pk = data.get('pk')
        date_val = data.get('date')
        if not emp_id and not emp_pk:
            return JsonResponse({'success': False, 'error': 'Employee ID is required'})
        emp = _resolve_employee(admin_id, emp_id, emp_pk)
        if emp is None:
            return JsonResponse({'success': False, 'error': 'Employee not found'})

        # Snapshot machine_id BEFORE the row is gone so we can peel the
        # employee off the linked WorkLog's M2M. Never delete the WorkLog
        # itself — pruning empty WorkLogs is a Projects-side concern.
        qs = AttendanceRecord.objects.filter(
            employee=emp, date=date_val, admin_id=admin_id,
        )
        machine_ids = list(qs.values_list('machine_id', flat=True))

        with transaction.atomic():
            qs.delete()
            for mid in machine_ids:
                if mid:
                    cleanup_worklog_on_delete(admin_id, date_val, mid, emp)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


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
        date_val = data.get('date')
        if not date_val:
            return JsonResponse({'success': False, 'error': 'Date is required'})

        emp = _resolve_employee(admin_id, emp_id, emp_pk)
        if emp is None:
            return JsonResponse({'success': False, 'error': 'Employee not found'})

        updated = AttendanceRecord.objects.filter(
            employee=emp, date=date_val, admin_id=admin_id,
        ).update(remarks_locked=False)
        return JsonResponse({'success': True, 'updated': updated})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def machine_suggest(request):
    """
    GET /attendance/machines/suggest/?q=<query>[&site_id=<id>]

    Returns up to 10 tenant-scoped MachineLocation matches for the given
    substring (case-insensitive, ordered by name). When `q` is empty,
    returns the first 10 by name so the input can offer options on focus
    before the user types anything.

    `site_id` (optional) narrows matches to machines assigned to that Site —
    used by the attendance table once a row's Client/Site is chosen. Each
    row also carries the machine's site_id + client_id so the client can
    auto-fill Client/Site when a machine is picked first (Flow 2).
    """
    admin_id = get_admin_id(request.user)
    q = (request.GET.get('q') or '').strip()
    qs = MachineLocation.objects.filter(admin_id=admin_id)
    try:
        site_id = int(request.GET.get('site_id') or 0) or None
    except (TypeError, ValueError):
        site_id = None
    if site_id:
        qs = qs.filter(site_id=site_id)
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.select_related('site', 'site__client').order_by('name')[:10]
    rows = [{
        'id':          m.pk,
        'name':        m.name,
        'site_id':     m.site_id,
        'client_id':   m.site.client_id if m.site_id else None,
        'site_label':  (
            f'{m.site.client.name} / {m.site.name}'
            if m.site_id and m.site.client_id else (m.site.name if m.site_id else '')
        ),
    } for m in qs]
    return JsonResponse(rows, safe=False)


@login_required
def client_site_suggest(request):
    """
    GET /attendance/client-sites/suggest/?q=<query>

    Returns up to 10 active "Client / Site" combos from the Projects
    registry, matched case-insensitively against the combined label.
    Ordered by usage frequency (count of attendance rows linked to the
    site) descending, then label — so alphabetical until usage accrues.
    """
    admin_id = get_admin_id(request.user)
    q = (request.GET.get('q') or '').strip().lower()
    sites = (
        Site.objects
        .filter(admin_id=admin_id, is_active=True, client__is_active=True)
        .select_related('client')
        .annotate(usage=Count('attendance_entries'))
    )
    rows = []
    for s in sites:
        label = f'{s.client.name} / {s.name}'
        if q and q not in label.lower():
            continue
        rows.append({
            'client_id': s.client_id,
            'site_id':   s.pk,
            'label':     label,
            'usage':     s.usage,
        })
    rows.sort(key=lambda r: (-r['usage'], r['label'].lower()))
    return JsonResponse(
        [{k: r[k] for k in ('client_id', 'site_id', 'label')} for r in rows[:10]],
        safe=False,
    )
