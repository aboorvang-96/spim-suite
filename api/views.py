"""
SPIM Suite mobile API.

Public routes (no auth):
    POST /api/mobile/login/
    POST /api/mobile/reset-password/   (admin-side reset; uses Django session auth)

Authenticated routes (Bearer <token>):
    POST /api/mobile/change-password/
    GET  /api/mobile/profile/
    GET  /api/mobile/attendance/
    GET  /api/mobile/payslips/
    GET  /api/mobile/worklogs/

All authenticated routes are filtered to the employee that owns the token.
There is no way to query another employee's data through these endpoints.
"""
import json
import logging
import traceback
from functools import wraps
from datetime import date, datetime, timedelta

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Sum

from employees.models import Employee, SalaryUpdate, BankDetail
from attendance.models import AttendanceRecord
from attendance.utils import ensure_sunday_holidays, display_status
from projects.models import WorkLog, MachineLocation
from .models import MobileAuthToken

# Dedicated logger for the SPIM Lite mobile API. Surfaces silent save
# failures (admin_id mismatch, DB errors, lock conflicts) in Railway logs
# so the intermittent attendance-sync bug is debuggable. Configure once at
# module load — Django's root logger settings forward records to console.
_log = logging.getLogger('spim.api.mobile')


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return {}


def _extract_token(request):
    """
    Pull a bearer token from (in order):
      1. Authorization: Bearer <token> header
      2. X-Auth-Token header
      3. ?token=<token> query string  — only used for browser-opened links
         such as payslip downloads where custom headers cannot be set.
    """
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    header_tok = (request.headers.get('X-Auth-Token') or '').strip()
    if header_tok:
        return header_tok
    return (request.GET.get('token') or '').strip()


def mobile_auth_required(view_func):
    """
    Decorator: resolve the bearer token, attach `request.employee`, or 401.
    Inactive employee accounts (mobile_account_active=False) are rejected.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        key = _extract_token(request)
        if not key:
            return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)
        try:
            tok = MobileAuthToken.objects.select_related('employee').get(key=key)
        except MobileAuthToken.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid or expired token.'}, status=401)
        emp = tok.employee
        if not emp.mobile_account_active:
            return JsonResponse({'success': False, 'error': 'Account disabled.'}, status=403)
        # Touch last_used (auto_now updates on save)
        tok.save(update_fields=['last_used'])
        request.employee = emp
        request.mobile_token = tok
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------------------------------------------------------------------------
# Mobile auth endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def mobile_login(request):
    """
    POST { "login_id": "SPIM001", "password": "...", "device_info": "optional" }
    -> { success, token, employee: {id, employee_id, name, ...}, password_reset_required }
    """
    data       = _json_body(request)
    login_id   = (data.get('login_id') or '').strip()
    password   = data.get('password') or ''
    device     = (data.get('device_info') or '')[:255]

    if not login_id or not password:
        return JsonResponse({'success': False, 'error': 'login_id and password required.'}, status=400)

    # Look up by employee_login_id first, fall back to employee_id for back-compat.
    emp = Employee.objects.filter(employee_login_id=login_id).first() \
        or Employee.objects.filter(employee_id=login_id).first()

    if not emp or not emp.mobile_account_active:
        return JsonResponse({'success': False, 'error': 'Invalid credentials.'}, status=401)

    # Verify against hash; if hash is empty (legacy row), fall back to plaintext
    # compare against mobile_app_password, then upgrade to a hash.
    valid = False
    if emp.mobile_password_hash:
        valid = check_password(password, emp.mobile_password_hash)
    elif emp.mobile_app_password and password == emp.mobile_app_password:
        valid = True
        emp.mobile_password_hash = make_password(password)
        emp.save(update_fields=['mobile_password_hash'])

    if not valid:
        return JsonResponse({'success': False, 'error': 'Invalid credentials.'}, status=401)

    token = MobileAuthToken.objects.create(employee=emp, device_info=device)

    return JsonResponse({
        'success': True,
        'token': token.key,
        'password_reset_required': emp.mobile_password_reset_required,
        'employee': {
            'id':            emp.id,
            'employee_id':   emp.employee_id,
            'login_id':      emp.employee_login_id or emp.employee_id,
            'name':          emp.name,
            'designation':   emp.designation,
            'department':    emp.department,
            'location':      emp.location,
            'site':          emp.site,
            # Surfaced at login so SPIM Lite clients that cache the login
            # response (and don't refetch /profile/) still see Level / Mobile
            # / Branch / Base Salary in the profile screen.
            'level':         emp.level,
            'mobile':        emp.mobile,
            'branch':        emp.branch,
            'base_salary':   str(emp.base_salary),
        },
    })


@csrf_exempt
@require_POST
@mobile_auth_required
def mobile_change_password(request):
    """
    POST { "current_password": "...", "new_password": "...", "confirm_password": "..." }
    Authenticated employee changes their own password.
    """
    data    = _json_body(request)
    current = data.get('current_password') or ''
    new_pw  = data.get('new_password') or ''
    confirm = data.get('confirm_password') or ''

    if not current or not new_pw or not confirm:
        return JsonResponse({'success': False, 'error': 'All password fields are required.'}, status=400)
    if new_pw != confirm:
        return JsonResponse({'success': False, 'error': 'New password and confirmation do not match.'}, status=400)
    if len(new_pw) < 8:
        return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters.'}, status=400)

    emp = request.employee
    # Verify current password (hash, then legacy plaintext fallback)
    if emp.mobile_password_hash:
        ok = check_password(current, emp.mobile_password_hash)
    else:
        ok = bool(emp.mobile_app_password) and current == emp.mobile_app_password
    if not ok:
        return JsonResponse({'success': False, 'error': 'Current password is incorrect.'}, status=400)

    emp.mobile_password_hash           = make_password(new_pw)
    emp.mobile_app_password            = ''  # never retain plaintext after a self-change
    emp.mobile_password_reset_required = False
    emp.save(update_fields=['mobile_password_hash', 'mobile_app_password', 'mobile_password_reset_required'])

    # Invalidate all other tokens for this employee; keep the current one.
    MobileAuthToken.objects.filter(employee=emp).exclude(pk=request.mobile_token.pk).delete()

    return JsonResponse({'success': True})


@csrf_exempt
@login_required
@require_POST
def mobile_reset_password(request):
    """
    Admin-side reset. Uses Django session auth (admin logged into SPIM Suite).
    POST { "employee_id": <pk>, "new_password": "optional — auto-generated if blank" }
    -> { success, new_password }   (plaintext returned ONCE for the admin)
    """
    # Defer import to avoid circulars / unrelated coupling
    from accounts.views import get_admin_id
    from employees.views import _generate_app_password

    data    = _json_body(request)
    emp_pk  = data.get('employee_id')
    new_pw  = (data.get('new_password') or '').strip()

    if not emp_pk:
        return JsonResponse({'success': False, 'error': 'employee_id required.'}, status=400)
    try:
        emp = Employee.objects.get(pk=emp_pk, admin_id=get_admin_id(request.user))
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found.'}, status=404)

    if not new_pw:
        new_pw = _generate_app_password()
    elif len(new_pw) < 8:
        return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters.'}, status=400)

    emp.mobile_app_password            = new_pw  # shown once to admin
    emp.mobile_password_hash           = make_password(new_pw)
    emp.mobile_password_reset_required = True    # employee should change on next login
    emp.mobile_account_active          = True
    emp.save(update_fields=[
        'mobile_app_password', 'mobile_password_hash',
        'mobile_password_reset_required', 'mobile_account_active',
    ])
    # Force re-login on all devices
    MobileAuthToken.objects.filter(employee=emp).delete()

    return JsonResponse({'success': True, 'new_password': new_pw})


# ---------------------------------------------------------------------------
# Mobile data endpoints — STRICTLY scoped to request.employee
# ---------------------------------------------------------------------------

@mobile_auth_required
@require_http_methods(['GET'])
def mobile_profile(request):
    """
    Full employee snapshot. Strictly scoped to request.employee — there is no
    employee-id query parameter and no listing variant.
    """
    emp  = request.employee
    bank = getattr(emp, 'bank_details', None)
    pf   = getattr(emp, 'pf_details', None)
    job  = emp.job_role

    # Latest payslip (most recent SalaryUpdate row)
    latest = SalaryUpdate.objects.filter(employee=emp).order_by('-month').first()
    latest_salary = None
    if latest:
        latest_salary = {
            'month':           latest.month.strftime('%Y-%m'),
            'basic_salary':    str(latest.basic_salary),
            'extra_allowance': str(latest.extra_allowance),
            'ot_allowance':    str(latest.ot_allowance),
            'advance_pay':     str(latest.advance_pay),
            'total_deduction': str(latest.total_deduction),
            'food_allowance':  str(latest.food_allowance),
            'food_usage':      str(latest.food_usage),
            'pf_employee':     str(latest.pf_employee_snapshot),
            'pf_employer':     str(latest.pf_employer_snapshot),
            'net_pay':         str(latest.net_pay),
        }

    # Company block — sourced from dashboard.CompanySettings for the
    # employee's tenant so SPIM Lite renders the same Company Name / Logo /
    # Address / Phone / Email as the Suite. Deferred import keeps this
    # module loadable when dashboard is not installed in some environments.
    company_block = None
    try:
        from dashboard.models import CompanySettings  # deferred to avoid cycles
        cs = CompanySettings.get_settings(emp.admin_id)
        if cs:
            logo_url = ''
            try:
                if cs.logo and hasattr(cs.logo, 'url'):
                    logo_url = request.build_absolute_uri(cs.logo.url)
            except Exception:
                logo_url = ''
            company_block = {
                'name':              cs.name or '',
                'logo_url':          logo_url,
                'address':           cs.address or '',
                'contact_number':    cs.contact_number or '',
                'email':             cs.email or '',
                'gst_number':        cs.gst_number or '',
                'managing_director': cs.managing_director or '',
            }
    except Exception:
        company_block = None

    # Attendance summary for the current calendar month
    today = date.today()
    month_qs = AttendanceRecord.objects.filter(
        employee=emp, date__year=today.year, date__month=today.month,
    )
    attendance_summary = {
        'month':    today.strftime('%Y-%m'),
        'present':  month_qs.filter(status='present').count(),
        'half_day': month_qs.filter(status='half_day').count(),
        'absent':   month_qs.filter(status='absent').count(),
        'leave':    month_qs.filter(status='leave').count(),
    }

    return JsonResponse({
        'success': True,
        'profile': {
            'id':                 emp.id,
            'employee_id':        emp.employee_id,
            'login_id':           emp.employee_login_id or emp.employee_id,
            'name':               emp.name,
            'designation':        emp.designation,
            'department':         emp.department,
            'location':           emp.location,
            'site':               emp.site,
            # New fields (Task 2 + Task 5)
            'level':              emp.level,
            'mobile':             emp.mobile,
            'branch':             emp.branch,
            'base_salary':        str(emp.base_salary),
            'salary_is_custom_override': bool(emp.salary_is_custom_override),
            'fixed_allowance':    str(emp.fixed_allowance),
            'joining_date':       str(emp.joining_date) if emp.joining_date else None,
            'status':             emp.status,
            'job_role': {
                'name':         job.name,
                'salary_type':  job.salary_type,
                'base_salary':  str(job.base_salary),
            } if job else None,
            'bank': {
                'bank_name':      bank.bank_name      if bank else '',
                'account_holder': bank.account_holder if bank else '',
                'account_number': bank.account_number if bank else '',
                'ifsc_code':      bank.ifsc_code      if bank else '',
                'branch':         bank.branch         if bank else '',
            } if bank else None,
            'pf': {
                'pf_number':             pf.pf_number             if pf else '',
                'uan_number':            pf.uan_number            if pf else '',
                'esic_number':           pf.esic_number           if pf else '',
                'employee_contribution': str(pf.employee_contribution) if pf else '0',
                'employer_contribution': str(pf.employer_contribution) if pf else '0',
            } if pf else None,
            'latest_salary':      latest_salary,
            'attendance_summary': attendance_summary,
            # Company details for the SPIM Lite dashboard. Frontend should
            # safely skip individual fields that are empty strings.
            'company':            company_block,
        },
    })


@csrf_exempt
@mobile_auth_required
@require_http_methods(['GET', 'POST'])
def mobile_attendance(request):
    """
    GET  -> own attendance records (optional ?month=YYYY-MM filter).
    POST -> create own attendance for a single date (locked once created).
            Body: { "date": "YYYY-MM-DD" (optional, defaults today), "status": "present|absent|half_day|leave" }

    Locking rules (Suite ⇄ Lite sync hardening):
      * If a record already exists with source='admin', the employee cannot
        overwrite it. Response: HTTP 409 with the locked record.
      * If a record already exists with source='employee' and the status
        matches, the response is idempotent success (safe to retry).
      * If a record already exists with source='employee' but the status
        differs, the employee cannot self-correct — HTTP 409. Admin can
        still override via the Suite admin save endpoint, which writes
        source='admin' and re-locks the row.
      * No existing record → create a new employee-sourced row.

    The presence of a record (any source) is the lock. Every record in the
    response carries `locked: true` so SPIM Lite can render the lock state
    without inferring it from `source`.
    """
    emp = request.employee

    if request.method == 'POST':
        # ─── Parse + validate request body ──────────────────────────────
        data         = _json_body(request)
        date_str     = (data.get('date') or '').strip() or date.today().isoformat()
        status_val   = (data.get('status') or 'present').strip().lower()
        # Site / Working Site fields (new — Mod 2/3). Both optional. When
        # the SPIM Lite client doesn't send them (older builds), the
        # employee's home-site is used as a sensible default so the Suite
        # registry still gets a populated Site column.
        site_val         = (data.get('site') or '').strip()
        working_site_val = (data.get('working_site') or '').strip()
        if not site_val:
            site_val = (emp.site or '').strip()

        valid_status = {s for s, _ in AttendanceRecord.STATUS_CHOICES}
        if status_val not in valid_status:
            _log.warning(
                'mobile_attendance POST rejected: invalid status emp=%s status=%s',
                emp.pk, status_val,
            )
            return JsonResponse(
                {'success': False, 'error': f'Invalid status. Allowed: {sorted(valid_status)}'},
                status=400,
            )
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            _log.warning(
                'mobile_attendance POST rejected: bad date emp=%s date=%r',
                emp.pk, date_str,
            )
            return JsonResponse({'success': False, 'error': 'date must be YYYY-MM-DD.'}, status=400)
        # Don't allow marking attendance for future dates
        if d > date.today():
            return JsonResponse({'success': False, 'error': 'Cannot mark attendance for a future date.'}, status=400)

        # ─── Resolve admin_id robustly ──────────────────────────────────
        # Bug 1 root cause: when emp.admin_id was 'PENDING' / blank /
        # mismatched, the AttendanceRecord landed in a tenancy bucket the
        # Suite's `filter(admin_id=admin_id)` queries never touched, so
        # the mark "saved successfully" from the mobile side but vanished
        # in the Suite registry. Fall back to the employee's creator's
        # admin_id when the direct field is unusable.
        effective_admin_id = (emp.admin_id or '').strip()
        if not effective_admin_id or effective_admin_id == 'PENDING':
            creator = getattr(emp, 'created_by', None)
            if creator is not None and getattr(creator, 'admin_id', None):
                effective_admin_id = creator.admin_id
                _log.info(
                    'mobile_attendance: emp=%s admin_id was %r, resolved via creator → %r',
                    emp.pk, emp.admin_id, effective_admin_id,
                )
        if not effective_admin_id:
            _log.error(
                'mobile_attendance: emp=%s has no usable admin_id; mark will be invisible to Suite',
                emp.pk,
            )
            return JsonResponse({
                'success': False,
                'error': 'Employee account is missing tenant scope. Please ask your admin to refresh your profile.',
            }, status=500)

        # ─── Lock enforcement ───────────────────────────────────────────
        # Never destructively overwrite an existing row from the mobile
        # path. This stops APK background-sync POSTs from silently
        # overwriting admin marks. EXCEPTION: a Sunday-auto-Holiday row
        # (source='admin' but stamped purely by the lazy backfill) should
        # NOT prevent the employee from claiming Present for that Sunday —
        # the previous behaviour was the root cause of the intermittent
        # "marks vanish" symptom on Sundays touched by ensure_sunday_holidays.
        existing = AttendanceRecord.objects.filter(employee=emp, date=d).first()
        if existing is not None:
            payload_record = {
                'id':           existing.id,
                'date':         str(existing.date),
                'status':       existing.status,
                'source':       existing.source,
                'site':         getattr(existing, 'site', '') or '',
                'working_site': getattr(existing, 'working_site', '') or '',
                'locked':       True,
            }
            # Detect the auto-Sunday-Holiday case: source='admin' + status='holiday'
            # + the date IS a Sunday + the row has no human-set audit fields.
            # The lazy ensure_sunday_holidays helper creates rows with
            # created_by=NULL and status='holiday'. Those should be
            # overwritable by the employee mark.
            is_auto_sunday = (
                existing.source == 'admin'
                and existing.status == 'holiday'
                and existing.created_by_id is None
                and d.weekday() == 6  # Sunday
            )
            if existing.source == 'admin' and not is_auto_sunday:
                return JsonResponse({
                    'success': False,
                    'error':   'Attendance for this date has been set by the admin and is locked.',
                    'locked':  True,
                    'record':  payload_record,
                }, status=409)
            if existing.source == 'employee':
                if existing.status == status_val:
                    # Idempotent retry — same value the employee already marked.
                    return JsonResponse({
                        'success': True,
                        'created': False,
                        'locked':  True,
                        'record':  payload_record,
                    })
                return JsonResponse({
                    'success': False,
                    'error':   'You have already marked attendance for this date.',
                    'locked':  True,
                    'record':  payload_record,
                }, status=409)
            # is_auto_sunday → fall through to upsert below

        # ─── Save (or upsert auto-Sunday-Holiday) ────────────────────────
        # Wrapped in try/except so transient DB errors surface in Railway
        # logs and return a meaningful error to the mobile client instead
        # of the generic 500 the previous code emitted.
        try:
            rec, created = AttendanceRecord.objects.update_or_create(
                employee=emp,
                date=d,
                defaults={
                    'status':       status_val,
                    'source':       'employee',
                    'admin_id':     effective_admin_id,
                    'site':         site_val,
                    'working_site': working_site_val,
                },
            )
        except Exception as exc:
            _log.exception(
                'mobile_attendance save failed: emp=%s date=%s status=%s admin_id=%s err=%s',
                emp.pk, d, status_val, effective_admin_id, exc,
            )
            return JsonResponse({
                'success': False,
                'error':   f'Could not save attendance: {exc.__class__.__name__}: {exc}',
            }, status=500)

        _log.info(
            'mobile_attendance saved: emp=%s date=%s status=%s site=%r ws=%r admin_id=%s created=%s',
            emp.pk, d, status_val, site_val, working_site_val, effective_admin_id, created,
        )
        return JsonResponse({
            'success': True,
            'created': created,
            'locked':  True,
            'record': {
                'id':           rec.id,
                'date':         str(rec.date),
                'status':       rec.status,
                'source':       rec.source,
                'site':         rec.site or '',
                'working_site': rec.working_site or '',
                'locked':       True,
            },
        })

    # GET
    qs    = AttendanceRecord.objects.filter(employee=emp).order_by('-date')
    month = (request.GET.get('month') or '').strip()
    if month:
        try:
            y, m = month.split('-')
            year_i, month_i = int(y), int(m)
            qs = qs.filter(date__year=year_i, date__month=month_i)
            # Lazy Sunday auto-Holiday backfill scoped to this employee for
            # the requested month — guarantees that when the Lite app
            # fetches a month's attendance, every Sunday already exists
            # as a 'holiday' row (created here if missing, untouched if
            # the admin has already overridden it).
            try:
                import calendar as _cal
                last_day = _cal.monthrange(year_i, month_i)[1]
                ensure_sunday_holidays(
                    emp.admin_id,
                    date(year_i, month_i, 1),
                    date(year_i, month_i, last_day),
                    employees=[emp],
                )
                # Re-query so the freshly-created rows are included in the
                # response. Cheap — same indexes as the original query.
                qs = AttendanceRecord.objects.filter(
                    employee=emp,
                    date__year=year_i,
                    date__month=month_i,
                ).order_by('-date')
            except (ValueError, TypeError):
                pass
        except (ValueError, IndexError):
            pass
    records = [{
        'id':     r.id,
        'date':   str(r.date),
        'status': r.status,
        'source': r.source,
        # Site / Working Site — defensive getattr keeps the GET working
        # even before migration 0004 has been applied to the Lite-facing DB.
        'site':         getattr(r, 'site',         '') or '',
        'working_site': getattr(r, 'working_site', '') or '',
        # Presence of a record == locked. Explicit flag so SPIM Lite can
        # render the lock state without inferring it from `source`.
        'locked': True,
    } for r in qs[:200]]
    return JsonResponse({'success': True, 'attendance': records})


@mobile_auth_required
@require_http_methods(['GET'])
def mobile_payslips(request):
    """
    List payslips for the authenticated employee. Every row is returned
    (admins may need visibility of pending months too), but only rows with
    is_generated=True are downloadable — see mobile_payslip_download.
    """
    emp = request.employee
    rows = SalaryUpdate.objects.filter(employee=emp).order_by('-month')[:60]
    payslips = [{
        'id':              s.id,
        'is_generated':    s.is_payslip_generated,
        'generated_at':    s.payslip_generated_at.isoformat() if s.payslip_generated_at else None,
        'month':           s.month.strftime('%Y-%m'),
        'basic_salary':    str(s.basic_salary),
        'ot_allowance':    str(s.ot_allowance),
        'advance_pay':     str(s.advance_pay),
        'total_deduction': str(s.total_deduction),
        'food_allowance':  str(s.food_allowance),
        'food_usage':      str(s.food_usage),
        'net_pay':         str(s.net_pay),
    } for s in rows]
    return JsonResponse({'success': True, 'payslips': payslips})


@csrf_exempt
@mobile_auth_required
@require_http_methods(['GET', 'POST'])
def mobile_worklogs(request):
    """
    GET  -> work logs where this employee is in the M2M `employees` set.
    POST -> employee submits an end-of-day machine log; reflects directly into
            SPIM Suite Projects → Machine Work Summary.

            Body: {
              machine_no: "G001",            # required, must already exist as a MachineLocation
              status:     "Painting",         # written to WorkLog.work_details
              remarks:    "...",
              tmp:        4,                  # Total Man Power
              date:       "2026-05-24"        # optional, defaults today
            }

            Single source of truth: writes the existing `projects.WorkLog`
            row (same one the admin reads in the Suite). Upsert keyed on
            (admin_id, date, location) — the same 3-tuple used by the admin
            `work_log_upsert` endpoint in projects/views.py. `site` is now
            merged data (last-write-wins on non-empty value), not part of
            identity, so two employees on the same machine/date with
            different stored sites still collapse into one WorkLog row.
            The employee is added to the M2M `employees` set, TMP grows
            via max(existing, posted) so multiple punches do not double
            count. created_by stays NULL (mobile-originated row).
    """
    emp = request.employee

    if request.method == 'POST':
        data        = _json_body(request)
        machine_no  = (data.get('machine_no') or '').strip()
        # Accept multiple field names for work status: SPIM Lite may send
        # 'status' (original spec), 'work_status', or 'work_details' (the
        # DB column name mirrored in GET responses). Fall through in priority
        # order so whichever the client sends is captured.
        status_val  = (data.get('status') or data.get('work_status') or data.get('work_details') or '').strip()
        remarks_val = (data.get('remarks')    or '').strip()
        tmp_val     = data.get('tmp')
        date_str    = (data.get('date')       or '').strip() or date.today().isoformat()

        if not machine_no:
            return JsonResponse({'success': False, 'error': 'machine_no is required.'}, status=400)
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'date must be YYYY-MM-DD.'}, status=400)
        if d > date.today():
            return JsonResponse({'success': False, 'error': 'Cannot log work for a future date.'}, status=400)

        machine = MachineLocation.objects.filter(admin_id=emp.admin_id, name=machine_no).first()
        if not machine:
            return JsonResponse(
                {'success': False, 'error': f'Machine "{machine_no}" not found for this tenant.'},
                status=400,
            )

        try:
            tmp_int = int(tmp_val) if tmp_val not in (None, '') else 0
            if tmp_int < 0:
                tmp_int = 0
        except (TypeError, ValueError):
            tmp_int = 0

        site_val = (emp.site or '').strip()

        # Identity is (admin_id, date, location) — matches projects.work_log_upsert.
        # site is merged into defaults / overwritten on collision when non-empty.
        wl, created = WorkLog.objects.get_or_create(
            admin_id=emp.admin_id,
            date=d,
            location=machine,
            defaults={
                'site':         site_val,
                'work_details': status_val,
                'remarks':      remarks_val,
                'tmp':          tmp_int,
            },
        )
        if not created:
            # Merge — non-empty values overwrite existing, TMP grows.
            dirty = []
            if site_val and site_val != (wl.site or ''):
                wl.site = site_val
                dirty.append('site')
            if status_val and status_val != (wl.work_details or ''):
                wl.work_details = status_val
                dirty.append('work_details')
            if remarks_val and remarks_val != (wl.remarks or ''):
                wl.remarks = remarks_val
                dirty.append('remarks')
            if tmp_int > (wl.tmp or 0):
                wl.tmp = tmp_int
                dirty.append('tmp')
            if dirty:
                dirty.append('updated_at')
                wl.save(update_fields=dirty)
        wl.employees.add(emp)

        return JsonResponse({
            'success': True,
            'created': created,
            'worklog': {
                'id':           wl.id,
                'date':         str(wl.date),
                'location':     wl.location.name if wl.location_id else '',
                'site':         wl.site,
                'work_details': wl.work_details,
                'remarks':      wl.remarks,
                'tmp':          wl.tmp,
            },
        })

    # GET
    qs   = WorkLog.objects.select_related('location').filter(employees=emp).order_by('-date')[:200]
    logs = [{
        'id':           w.id,
        'date':         str(w.date),
        'location':     w.location.name if w.location_id else '',
        'site':         w.site,
        'work_details': w.work_details,
        'remarks':      w.remarks,
        'tmp':          w.tmp,
    } for w in qs]
    return JsonResponse({'success': True, 'worklogs': logs})


@mobile_auth_required
@require_http_methods(['GET'])
def mobile_machines(request):
    """
    Return every MachineLocation belonging to this employee's tenant (Task 1).

    Business rule: admin only registers Machine Numbers / Locations under the
    Suite's Projects module. They do NOT assign machines to specific
    employees. Each employee picks their machine themselves in SPIM Lite.
    """
    emp = request.employee
    qs  = MachineLocation.objects.filter(admin_id=emp.admin_id).order_by('name')
    machines = [{'id': m.id, 'machine_no': m.name} for m in qs]
    return JsonResponse({'success': True, 'machines': machines})


@mobile_auth_required
@require_http_methods(['GET'])
def mobile_sites(request):
    """
    Return every site known to this employee's tenant (Mod 2/3).

    Source list is the union of:
      * `branches.LocationSite.name` for the tenant (admin-managed registry
        used by the Suite's Site / Working Site dropdowns).
      * Distinct `Employee.site` values currently configured for the tenant.
      * The employee's own `site` field — guarantees the dropdown always
        contains their default even when the admin hasn't catalogued it yet.

    SPIM Lite calls this once at attendance-screen load time to populate
    the Site dropdown that drives `site` in the mobile_attendance POST.
    """
    emp = request.employee
    sites = set()

    try:
        from branches.models import LocationSite
        for name in LocationSite.objects.filter(admin_id=emp.admin_id).values_list('name', flat=True):
            n = (name or '').strip()
            if n:
                sites.add(n)
    except Exception as exc:
        _log.warning('mobile_sites: LocationSite lookup failed for emp=%s err=%s', emp.pk, exc)

    try:
        for name in Employee.objects.filter(admin_id=emp.admin_id).values_list('site', flat=True):
            n = (name or '').strip()
            if n:
                sites.add(n)
    except Exception as exc:
        _log.warning('mobile_sites: Employee.site sweep failed for emp=%s err=%s', emp.pk, exc)

    own = (emp.site or '').strip()
    if own:
        sites.add(own)

    return JsonResponse({
        'success': True,
        'sites':   sorted(sites),
        'default': own,
    })


@mobile_auth_required
@require_http_methods(['GET'])
def mobile_payslip_download(request, pk):
    """
    Render the existing payslip template (templates/employees/payslip.html)
    scoped to the authenticated employee. Returns HTML; the mobile client
    opens it in an external browser/WebView where the user can print to PDF.
    Cross-employee access is blocked because the query joins on request.employee.

    Locked until admin clicks "Generate Payslip" (Task 4): a not-yet-generated
    payslip returns 403.
    """
    from dashboard.models import CompanySettings  # deferred to avoid import cycles
    salary = get_object_or_404(SalaryUpdate, pk=pk, employee=request.employee)
    if not salary.is_payslip_generated:
        return JsonResponse(
            {'success': False, 'error': 'Payslip not yet generated by admin.'},
            status=403,
        )
    return render(request, 'employees/payslip.html', {
        'salary':   salary,
        'employee': salary.employee,
        'company':  CompanySettings.get_settings(salary.employee.admin_id),
    })


@csrf_exempt
@mobile_auth_required
@require_http_methods(['GET', 'POST'])
def mobile_bank_details(request):
    """
    GET  -> the authenticated employee's bank details (matches the `bank`
            block in /api/mobile/profile/ but in its own focused payload).
    POST -> upsert the authenticated employee's bank details.
            Body: { bank_name, account_holder, account_number, ifsc_code, branch }
            Whichever fields are missing keep their current value. The row
            is the same BankDetail OneToOne that the Suite already reads,
            so updates from mobile are visible immediately to admin.
    """
    emp = request.employee

    if request.method == 'POST':
        data = _json_body(request)
        # Pull current row (or create empty) so partial payloads work.
        bank, _ = BankDetail.objects.get_or_create(
            employee=emp,
            defaults={
                'bank_name':      '',
                'account_holder': '',
                'account_number': '',
                'ifsc_code':      '',
            },
        )
        for src, attr in (
            ('bank_name', 'bank_name'),
            ('account_holder', 'account_holder'),
            ('account_number', 'account_number'),
            ('ifsc_code', 'ifsc_code'),
            ('branch', 'branch'),
        ):
            if src in data and data[src] is not None:
                setattr(bank, attr, str(data[src]).strip())
        # An employee-edited row is no longer "verified" until admin re-checks.
        if bank.status == 'verified':
            bank.status = 'modified'
        bank.save()

    bank = getattr(emp, 'bank_details', None)
    return JsonResponse({
        'success': True,
        'bank': {
            'bank_name':      bank.bank_name      if bank else '',
            'account_holder': bank.account_holder if bank else '',
            'account_number': bank.account_number if bank else '',
            'ifsc_code':      bank.ifsc_code      if bank else '',
            'branch':         bank.branch         if bank else '',
            'status':         bank.status         if bank else 'pending',
        },
    })


@mobile_auth_required
@require_POST
def mobile_logout(request):
    """Revoke the current device token."""
    request.mobile_token.delete()
    return JsonResponse({'success': True})


# ---------------------------------------------------------------------------
# Salary cycle summary (26th prev month -> 25th current month)
# ---------------------------------------------------------------------------

@mobile_auth_required
@require_http_methods(['GET'])
def mobile_salary(request):
    """
    Current salary cycle summary for the authenticated employee.

    Cycle window: 26th of previous month -> 25th of current month, anchored
    to today. The SalaryUpdate row whose `month` matches the cycle-end's
    year+month is used (SPIM Suite convention). If no row exists yet, all
    monetary fields default to '0.00' so SPIM Lite can render the cycle
    without a separate empty state.

    Notes:
      * `hra` is not tracked on SalaryUpdate today; surfaced as '0.00' to
        keep the response shape stable. Update only the one line below if a
        column is added later.
      * `allowances` = extra_allowance + ot_allowance + food_allowance
        (the three additive components SalaryUpdate already stores).
      * `deductions` = total_deduction (kept as a single rolled-up figure
        to match how the Suite UI shows it).
    """
    emp   = request.employee
    today = date.today()

    # Cycle window
    if today.day >= 26:
        cycle_start = today.replace(day=26)
        if today.month == 12:
            cycle_end = date(today.year + 1, 1, 25)
        else:
            cycle_end = date(today.year, today.month + 1, 25)
    else:
        if today.month == 1:
            cycle_start = date(today.year - 1, 12, 26)
        else:
            cycle_start = date(today.year, today.month - 1, 26)
        cycle_end = today.replace(day=25)

    sal = SalaryUpdate.objects.filter(
        employee=emp,
        month__year=cycle_end.year,
        month__month=cycle_end.month,
    ).first()

    # Attendance counts inside the cycle window (drives present/absent days).
    att_qs = AttendanceRecord.objects.filter(
        employee=emp,
        date__gte=cycle_start,
        date__lte=cycle_end,
    )
    present_days = att_qs.filter(status='present').count()
    absent_days  = att_qs.filter(status='absent').count()

    # Live net salary — same helper the Suite Salary dashboard uses, so SPIM
    # Lite sees the current attendance-prorated payable base instead of a
    # stale SalaryUpdate.net_pay snapshot (which is stamped at Save time and
    # can be 0 for cycles with no manual save yet).
    # Deferred import: employees.views imports from attendance.models, which
    # already depends on employees.models — keeping this import inside the
    # function avoids any chance of an import-time cycle through api.views.
    from employees.views import _compute_attendance_breakdown
    net_salary_amount, paid_days_dec = _compute_attendance_breakdown(
        emp, cycle_end.replace(day=1), float(emp.base_salary),
    )
    net_salary   = str(round(net_salary_amount, 2))
    paid_days    = float(paid_days_dec)
    basic_salary = str(emp.base_salary)
    hra          = '0.00'  # not modelled on SalaryUpdate

    # Allowances + deductions still come from the SalaryUpdate row (the
    # admin-entered figures); fall back to 0.00 when no row exists yet.
    if sal:
        allowances = str(sal.extra_allowance + sal.ot_allowance + sal.food_allowance)
        deductions = str(sal.total_deduction)
    else:
        allowances = '0.00'
        deductions = '0.00'

    return JsonResponse({
        'success': True,
        'salary': {
            'basic_salary': basic_salary,
            'hra':          hra,
            'allowances':   allowances,
            'deductions':   deductions,
            'net_salary':   net_salary,
            'paid_days':    paid_days,
            'present_days': present_days,
            'absent_days':  absent_days,
            'cycle_start':  str(cycle_start),
            'cycle_end':    str(cycle_end),
        },
    })


# ---------------------------------------------------------------------------
# Dashboard summary (lightweight; for SPIM Lite home tab)
# ---------------------------------------------------------------------------

@mobile_auth_required
@require_http_methods(['GET'])
def mobile_dashboard(request):
    """
    Focused dashboard payload for the authenticated employee. Mirrors fields
    already surfaced by `mobile_profile` so SPIM Lite's home tab can render
    in a single round-trip instead of pulling the full profile snapshot.

    Fields:
      * employee identity (name, designation, department)
      * today_attendance_status  -> AttendanceRecord.status for today, or None
      * current_month_present_days / current_month_absent_days
      * latest_net_salary  -> most recent SalaryUpdate.net_pay (or '0.00')
      * company.name / company.logo_url  -> dashboard.CompanySettings
    """
    emp   = request.employee
    today = date.today()

    # Today's attendance (None if not yet marked)
    todays_rec   = AttendanceRecord.objects.filter(employee=emp, date=today).first()
    today_status = todays_rec.status if todays_rec else None

    # 26→25 cycle anchored on today — same window mobile_salary uses, so the
    # home tab and the salary tab agree on the active cycle.
    if today.day >= 26:
        cycle_start = today.replace(day=26)
        if today.month == 12:
            cycle_end = date(today.year + 1, 1, 25)
        else:
            cycle_end = date(today.year, today.month + 1, 25)
    else:
        if today.month == 1:
            cycle_start = date(today.year - 1, 12, 26)
        else:
            cycle_start = date(today.year, today.month - 1, 26)
        cycle_end = today.replace(day=25)

    # Cycle attendance counts, capped at today so future-dated rows (auto
    # Sunday holidays etc.) do not inflate the present/absent figures.
    cycle_qs = AttendanceRecord.objects.filter(
        employee=emp,
        date__gte=cycle_start,
        date__lte=cycle_end,
    ).filter(date__lte=today)
    present_days = cycle_qs.filter(status='present').count()
    absent_days  = cycle_qs.filter(status__in=['absent', 'leave', 'no_week_off']).count()

    # Live net salary — same helper the Suite Salary dashboard uses, so the
    # SPIM Lite home tab no longer surfaces a stale SalaryUpdate.net_pay.
    # Deferred import to avoid any import-time cycle through api.views.
    from employees.views import _compute_attendance_breakdown
    latest_net_salary_amount, _paid_dec = _compute_attendance_breakdown(
        emp, cycle_end.replace(day=1), float(emp.base_salary),
    )
    latest_net_salary = str(round(latest_net_salary_amount, 2))

    # Company block — deferred import (matches mobile_profile's pattern).
    company_name = ''
    company_logo = ''
    try:
        from dashboard.models import CompanySettings  # deferred to avoid cycles
        cs = CompanySettings.get_settings(emp.admin_id)
        if cs:
            company_name = cs.name or ''
            try:
                if cs.logo and hasattr(cs.logo, 'url'):
                    company_logo = request.build_absolute_uri(cs.logo.url)
            except Exception:
                company_logo = ''
    except Exception:
        pass

    return JsonResponse({
        'success': True,
        'dashboard': {
            'name':                       emp.name,
            'designation':                emp.designation,
            'department':                 emp.department,
            'today_attendance_status':    today_status,
            'current_month_present_days': present_days,
            'current_month_absent_days':  absent_days,
            'latest_net_salary':          latest_net_salary,
            'company': {
                'name':     company_name,
                'logo_url': company_logo,
            },
        },
    })


# ---------------------------------------------------------------------------
# Legacy stub endpoints (kept for backward-compatibility; not wired into urls
# unless the consumer app exists). Imports are deferred so this module always
# loads cleanly even when optional apps are absent.
# ---------------------------------------------------------------------------

@login_required
def api_expenses(request):
    from finance.models import Transaction
    user = request.user
    if request.method == 'GET':
        qs = Transaction.objects.filter(user=user, type='expense').select_related('category').order_by('-date')[:50]
        data = [{
            'id':       t.id,
            'amount':   str(t.amount),
            'category': t.category.name if t.category else None,
            'date':     str(t.date),
        } for t in qs]
        return JsonResponse({'success': True, 'expenses': data})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_income(request):
    from income.models import Income
    user = request.user
    if request.method == 'GET':
        qs = Income.objects.filter(user=user).order_by('-date')[:50]
        data = [{
            'id':     i.id,
            'amount': str(i.amount),
            'date':   str(i.date),
        } for i in qs]
        return JsonResponse({'success': True, 'income': data})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_dashboard(request):
    from finance.models import Transaction
    from income.models import Income
    user  = request.user
    today = date.today()
    total_income  = Income.objects.filter(user=user).aggregate(total=Sum('amount'))['total'] or 0
    total_expense = Transaction.objects.filter(user=user, type='expense').aggregate(total=Sum('amount'))['total'] or 0
    return JsonResponse({
        'success': True,
        'total_income':  str(total_income),
        'total_expense': str(total_expense),
        'balance':       str(total_income - total_expense),
    })


# ---------------------------------------------------------------------------
# SPIM Lite HR endpoints — read-only, HR-gated, tenant-scoped
# ---------------------------------------------------------------------------
#
# These endpoints exist because every other /api/mobile/* endpoint is
# self-scoped to request.employee. HR needs to view other employees under
# the SAME admin_id (tenant). Every endpoint below is:
#   * bearer-token authenticated (via mobile_hr_required → mobile_auth_required)
#   * HR-gated (403 if the caller isn't HR)
#   * admin_id-scoped (404 if the target employee belongs to another tenant)
#   * read-only (GET only)
#
# Business logic is REUSED from existing helpers — no duplication:
#   * ensure_sunday_holidays  (attendance.utils)
#   * display_status          (attendance.utils — single source of truth)
#   * _compute_attendance_breakdown  (employees.views — same helper mobile_salary uses)
# ---------------------------------------------------------------------------

_HR_KEYWORD = 'hr'


def _is_hr_employee(emp):
    """
    HR detection mirrors SPIM Lite's utils/permissions.ts:isHrUser — scan
    designation / department / level (trim + lowercase) for the substring
    'hr'. Kept as a substring match so both server and client agree on
    who is HR without a schema change.
    """
    if emp is None:
        return False
    for field in (
        getattr(emp, 'designation', '') or '',
        getattr(emp, 'department', '') or '',
        getattr(emp, 'level', '') or '',
    ):
        if _HR_KEYWORD in field.strip().lower():
            return True
    return False


def _hr_effective_admin_id(emp):
    """
    Resolve the effective admin_id (tenant) for an HR mobile caller.

    Mirrors the fallback already used by mobile_attendance for the same
    reason: some Employee rows land with admin_id='PENDING' or blank
    (created before the tenant was finalised). In that case the row's
    creator (Employee.created_by, a Django User) still carries the real
    admin_id, so we prefer that. Without this resolver, HR endpoints
    would filter on 'PENDING' and either return legacy noise or nothing.

    Returns the resolved admin_id string, or '' if unresolvable.
    """
    if emp is None:
        return ''
    direct = (getattr(emp, 'admin_id', '') or '').strip()
    if direct and direct != 'PENDING':
        return direct
    creator = getattr(emp, 'created_by', None)
    if creator is not None:
        creator_admin = (getattr(creator, 'admin_id', '') or '').strip()
        if creator_admin:
            return creator_admin
    return direct  # possibly '' — caller decides how to handle


def mobile_hr_required(view_func):
    """
    Decorator: mobile_auth_required + HR gate. Layers on top of the
    existing token auth without modifying it. Non-HR callers get 403.
    """
    @wraps(view_func)
    @mobile_auth_required
    def _wrapped(request, *args, **kwargs):
        if not _is_hr_employee(request.employee):
            return JsonResponse(
                {'success': False, 'error': 'HR privileges required.'},
                status=403,
            )
        return view_func(request, *args, **kwargs)
    return _wrapped


@mobile_hr_required
@require_http_methods(['GET'])
def mobile_hr_employees(request):
    """
    GET /api/mobile/hr/employees/

    Returns every employee under the HR caller's admin_id. Mirrors the
    dict shape of employees.views.employee_list_json (so a future Lite
    client can share a picker component with the Suite web view). No
    calculation, no aggregation — just the reused queryset.
    """
    hr_admin_id = _hr_effective_admin_id(request.employee)
    qs = Employee.objects.filter(admin_id=hr_admin_id).order_by('name')
    employees = [{
        'id':           emp.employee_id or '',
        'pk':           emp.pk,
        'name':         emp.name,
        'dept':         emp.department or '',
        'role':         emp.designation or '',
        'mainLocation': emp.location or '',
        'site':         emp.site or '',
        'baseSalary':   float(emp.base_salary) if emp.base_salary else 0,
        'salaryType':   getattr(emp, 'salary_type', 'base_salary') or 'base_salary',
    } for emp in qs]
    return JsonResponse({'success': True, 'employees': employees})


@mobile_hr_required
@require_http_methods(['GET'])
def mobile_hr_attendance(request):
    """
    GET /api/mobile/hr/attendance/?employee_id=<pk>&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

    Returns attendance rows for the target employee across the requested
    window. Reuses:
      * ensure_sunday_holidays()  — same Sunday backfill the Suite uses
      * display_status()          — same Sunday-display rule the Suite uses
      * AttendanceRecord queryset — same admin_id-scoped filter shape

    404 if the target employee belongs to another admin_id (tenant isolation).
    """
    hr_admin_id = _hr_effective_admin_id(request.employee)
    emp_pk = (request.GET.get('employee_id') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()

    if not emp_pk:
        return JsonResponse(
            {'success': False, 'error': 'employee_id is required.'},
            status=400,
        )

    try:
        target = Employee.objects.get(pk=emp_pk, admin_id=hr_admin_id)
    except (Employee.DoesNotExist, ValueError, TypeError):
        # Never leak "wrong tenant" vs "doesn't exist" — both return 404.
        return JsonResponse(
            {'success': False, 'error': 'Employee not found.'},
            status=404,
        )

    # Sunday backfill scoped to this target so the response matches the
    # Suite web view for the same window.
    if date_from:
        backfill_to = date_to
        if not backfill_to:
            try:
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                next_month = df.replace(day=28) + timedelta(days=4)
                backfill_to = (
                    next_month.replace(day=1) - timedelta(days=1)
                ).isoformat()
            except ValueError:
                backfill_to = ''
        if backfill_to:
            ensure_sunday_holidays(
                hr_admin_id, date_from, backfill_to, employees=[target],
            )

    qs = AttendanceRecord.objects.filter(
        admin_id=hr_admin_id, employee=target,
    ).select_related('employee')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    qs = qs.order_by('-date')

    records = [{
        'empId':       r.employee.employee_id or '',
        'empPk':       r.employee.pk,
        'empName':     r.employee.name,
        'date':        r.date.isoformat(),
        'status':      display_status(r),
        'source':      r.source,
        'site':        getattr(r, 'site', '') or '',
        'workingSite': getattr(r, 'working_site', '') or '',
    } for r in qs]

    return JsonResponse({'success': True, 'records': records})


@mobile_hr_required
@require_http_methods(['GET'])
def mobile_hr_salary(request):
    """
    GET /api/mobile/hr/salary/?employee_id=<pk>

    Current 26→25 cycle salary summary for the target employee. Reuses
    the same helper mobile_salary uses (_compute_attendance_breakdown),
    so no salary calculation is duplicated.

    404 if the target employee belongs to another admin_id (tenant isolation).
    """
    hr_admin_id = _hr_effective_admin_id(request.employee)
    emp_pk = (request.GET.get('employee_id') or '').strip()

    if not emp_pk:
        return JsonResponse(
            {'success': False, 'error': 'employee_id is required.'},
            status=400,
        )

    try:
        target = Employee.objects.get(pk=emp_pk, admin_id=hr_admin_id)
    except (Employee.DoesNotExist, ValueError, TypeError):
        return JsonResponse(
            {'success': False, 'error': 'Employee not found.'},
            status=404,
        )

    today = date.today()

    # Cycle window — identical rule to mobile_salary.
    if today.day >= 26:
        cycle_start = today.replace(day=26)
        if today.month == 12:
            cycle_end = date(today.year + 1, 1, 25)
        else:
            cycle_end = date(today.year, today.month + 1, 25)
    else:
        if today.month == 1:
            cycle_start = date(today.year - 1, 12, 26)
        else:
            cycle_start = date(today.year, today.month - 1, 26)
        cycle_end = today.replace(day=25)

    sal = SalaryUpdate.objects.filter(
        employee=target,
        month__year=cycle_end.year,
        month__month=cycle_end.month,
    ).first()

    att_qs = AttendanceRecord.objects.filter(
        employee=target,
        date__gte=cycle_start,
        date__lte=cycle_end,
    )
    present_days = att_qs.filter(status='present').count()
    absent_days = att_qs.filter(status='absent').count()

    # Reuse the exact same helper mobile_salary uses.
    from employees.views import _compute_attendance_breakdown
    net_salary_amount, paid_days_dec = _compute_attendance_breakdown(
        target, cycle_end.replace(day=1), float(target.base_salary),
    )
    net_salary = str(round(net_salary_amount, 2))
    paid_days = float(paid_days_dec)
    basic_salary = str(target.base_salary)
    hra = '0.00'

    if sal:
        allowances = str(sal.extra_allowance + sal.ot_allowance + sal.food_allowance)
        deductions = str(sal.total_deduction)
    else:
        allowances = '0.00'
        deductions = '0.00'

    return JsonResponse({
        'success': True,
        'employee': {
            'pk': target.pk,
            'employee_id': target.employee_id or '',
            'name': target.name,
        },
        'salary': {
            'basic_salary': basic_salary,
            'hra':          hra,
            'allowances':   allowances,
            'deductions':   deductions,
            'net_salary':   net_salary,
            'paid_days':    paid_days,
            'present_days': present_days,
            'absent_days':  absent_days,
            'cycle_start':  str(cycle_start),
            'cycle_end':    str(cycle_end),
        },
    })


# ---------------------------------------------------------------------------
# SPIM Lite HR Income endpoints — read/write, HR-gated, tenant-scoped
# ---------------------------------------------------------------------------
#
# These endpoints wrap the existing Suite Income module:
#   * validation      → income.forms.IncomeForm   (single source of truth)
#   * serialization   → income.views._income_to_dict
#   * queryset shape  → Income.objects.filter(admin_id=…)
#   * location auto-register → income.views._ensure_location_site
#
# Nothing new is duplicated. Income has no employee FK (schema decision —
# search happens on the free-text fields title / source / description /
# payment_by; searching by Employee ID or Name is not supported).
#
# Every mutating endpoint sets Income.user to the Employee's creator
# Django User (Employee.created_by). This mirrors the fallback that
# api.views.mobile_attendance already uses to resolve admin_id for
# mobile-originated writes, so HR-created rows land in the same tenant
# bucket the Suite admin sees.
# ---------------------------------------------------------------------------


def _hr_creator_user(emp):
    """
    Resolve the Django User to stamp on rows created by an HR mobile
    call. Uses Employee.created_by, which is how the Suite already
    ties Employee rows to a tenant. Returns None if unresolvable;
    callers must 500 in that case rather than write a bad FK.
    """
    creator = getattr(emp, 'created_by', None)
    return creator if creator is not None else None


def _hr_income_payload_dict(income):
    """
    Thin wrapper over income.views._income_to_dict so the mobile
    response uses the exact same serializer as the Suite web AJAX
    endpoint. Deferred import avoids pulling income into api's
    module-load path.
    """
    from income.views import _income_to_dict
    return _income_to_dict(income)


@mobile_hr_required
@require_http_methods(['GET'])
def mobile_hr_income_categories(request):
    """
    GET /api/mobile/hr/income/categories/

    Reused IncomeCategory queryset — scoped to the tenant via the
    category creator's admin_id, matching income.views.income_list.
    """
    from categories.models import IncomeCategory
    hr_admin_id = _hr_effective_admin_id(request.employee)
    qs = IncomeCategory.objects.filter(
        created_by__admin_id=hr_admin_id,
    ).order_by('name')
    categories = [{
        'id':   c.id,
        'name': c.name,
    } for c in qs]
    return JsonResponse({'success': True, 'categories': categories})


@csrf_exempt
@mobile_hr_required
@require_http_methods(['GET', 'POST'])
def mobile_hr_income_list(request):
    """
    GET  /api/mobile/hr/income/       — list (with filters)
    POST /api/mobile/hr/income/       — create

    List filters (all optional, mirror income.views.income_list):
      * search       — matches title / source / description / payment_by
      * category     — IncomeCategory pk
      * date_from    — YYYY-MM-DD
      * date_to      — YYYY-MM-DD

    Sort order: same as Income.Meta.ordering (-date, -created_at) —
    "latest first" out of the box; no client-side sort needed.

    Search notes: Income is NOT linked to an Employee row (no FK). The
    Suite's income_list already searches title / source / description;
    payment_by is added here so free-text party names (which HR often
    treats as the "person") are matched too. Employee ID / Employee Name
    lookup is not possible against this schema.

    Response:
      { success: True, incomes: [ _income_to_dict(row), … ] }
    """
    from income.models import Income
    from income.forms import IncomeForm
    from income.views import _ensure_location_site
    from django.db.models import Q

    hr_admin_id = _hr_effective_admin_id(request.employee)

    if request.method == 'GET':
        qs = Income.objects.filter(admin_id=hr_admin_id).select_related('category', 'user')

        search    = (request.GET.get('search')    or '').strip()
        category  = (request.GET.get('category')  or '').strip()
        date_from = (request.GET.get('date_from') or '').strip()
        date_to   = (request.GET.get('date_to')   or '').strip()

        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(source__icontains=search)
                | Q(description__icontains=search)
                | Q(payment_by__icontains=search)
            )
        if category:
            try:
                qs = qs.filter(category_id=int(category))
            except (ValueError, TypeError):
                pass
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)

        # Income.Meta.ordering already sorts -date, -created_at.
        incomes = [_hr_income_payload_dict(i) for i in qs]
        return JsonResponse({'success': True, 'incomes': incomes})

    # POST — create. Reuses IncomeForm verbatim.
    creator = _hr_creator_user(request.employee)
    if creator is None:
        return JsonResponse({
            'success': False,
            'error': 'HR account is missing a tenant creator. Please contact your admin.',
        }, status=500)

    data = _json_body(request) or {}
    form = IncomeForm(creator, data)
    if not form.is_valid():
        errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
        first = next(iter(errors.values()), ['Invalid data.'])[0]
        return JsonResponse(
            {'success': False, 'errors': errors, 'message': first},
            status=400,
        )

    income = form.save(commit=False)
    income.user     = creator
    income.admin_id = hr_admin_id
    income.save()
    _ensure_location_site(hr_admin_id, income.location_site, creator)

    return JsonResponse({
        'success': True,
        'income':  _hr_income_payload_dict(income),
    }, status=201)


@csrf_exempt
@mobile_hr_required
@require_http_methods(['GET', 'PUT', 'DELETE'])
def mobile_hr_income_detail(request, pk):
    """
    GET    /api/mobile/hr/income/<pk>/  — retrieve
    PUT    /api/mobile/hr/income/<pk>/  — update
    DELETE /api/mobile/hr/income/<pk>/  — delete (mirrors the Suite web
                                          admin behavior; Suite already
                                          supports Income deletion).

    Cross-tenant lookups return 404 to avoid leaking existence.
    """
    from income.models import Income
    from income.forms import IncomeForm
    from income.views import _ensure_location_site

    hr_admin_id = _hr_effective_admin_id(request.employee)

    try:
        income = Income.objects.get(pk=pk, admin_id=hr_admin_id)
    except (Income.DoesNotExist, ValueError, TypeError):
        return JsonResponse(
            {'success': False, 'error': 'Income not found.'},
            status=404,
        )

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'income':  _hr_income_payload_dict(income),
        })

    if request.method == 'DELETE':
        income.delete()
        return JsonResponse({'success': True})

    # PUT — update via the same form the Suite uses.
    creator = _hr_creator_user(request.employee)
    if creator is None:
        return JsonResponse({
            'success': False,
            'error': 'HR account is missing a tenant creator. Please contact your admin.',
        }, status=500)

    data = _json_body(request) or {}
    form = IncomeForm(creator, data, instance=income)
    if not form.is_valid():
        errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
        first = next(iter(errors.values()), ['Invalid data.'])[0]
        return JsonResponse(
            {'success': False, 'errors': errors, 'message': first},
            status=400,
        )

    income = form.save(commit=False)
    income.admin_id = hr_admin_id  # never let the payload widen scope
    income.save()
    _ensure_location_site(hr_admin_id, income.location_site, creator)

    return JsonResponse({
        'success': True,
        'income':  _hr_income_payload_dict(income),
    })
