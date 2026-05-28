"""
employees/supabase_auth_sync.py

Internal Supabase Auth synchronisation utilities for the employees app.

ARCHITECTURE NOTE
-----------------
Supabase Auth requires an email-shaped string for its internal transport layer.
We generate a deterministic "auth identifier" at the auth boundary only:

    build_auth_email(login_id, admin_id)
      → "<lower(login_id)>.<lower(admin_id)>@spim.local"

This identifier:
  • exists ONLY in auth.users (Supabase's internal table — never in ERP tables)
  • is NEVER shown to employees or admins
  • is NEVER used as an employee identity — org_code + employee_login_id remain
    the sole ERP identity keys
  • is matched by SPIM Lite's loginIdToEmail() — any change here MUST be
    reflected there too

The formula is deterministic, so we can always reconstruct it from the
employee row and never need to store it.

This module is the ONLY place in the codebase that should call Supabase's
Admin API.  All other code (signals, seed command) imports from here.
"""

import json
import logging
import threading
import urllib.error
import urllib.request

from decouple import config

logger = logging.getLogger(__name__)

SUPABASE_URL         = config('SUPABASE_URL',         default='').rstrip('/')
SUPABASE_SERVICE_KEY = config('SUPABASE_SERVICE_KEY', default='')

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_auth_email(employee_login_id: str, admin_id: str) -> str:
    """
    Construct the internal auth identifier for a SPIM employee.

    Formula (must match SPIM Lite's loginIdToEmail):
        "<lower(login_id)>.<lower(admin_id)>@spim.local"

    Example:
        employee_login_id="SPIM001", admin_id="ADM26019A"
        → "spim001.adm26019a@spim.local"
    """
    return f"{employee_login_id.strip().lower()}.{admin_id.strip().lower()}@spim.local"


def is_configured() -> bool:
    """Return True when the Supabase Admin API credentials are available."""
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------------------------
# Supabase Admin API (stdlib-only, no supabase-py needed)
# ---------------------------------------------------------------------------

def _admin_request(method: str, path: str, payload: dict | None = None) -> dict:
    """
    Raw HTTP request to the Supabase Auth Admin API.
    Raises RuntimeError on HTTP 4xx/5xx with the response body included.
    """
    url  = f"{SUPABASE_URL}/auth/v1/admin{path}"
    data = json.dumps(payload or {}).encode('utf-8')
    req  = urllib.request.Request(
        url,
        data=data if method != 'GET' else None,
        headers={
            'Content-Type':  'application/json',
            'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
            'apikey':        SUPABASE_SERVICE_KEY,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f"Supabase Admin API {method} {path} → {exc.code}: {body}") from exc


def create_auth_user(email: str, password: str) -> str:
    """
    Create a Supabase Auth user.  Returns the new auth UUID.
    Raises RuntimeError if the email is already registered.
    """
    result = _admin_request('POST', '/users', {
        'email':         email,
        'password':      password,
        'email_confirm': True,          # skip email verification
    })
    uid = result.get('id') or (result.get('user') or {}).get('id')
    if not uid:
        raise RuntimeError(f"Unexpected response shape: {result}")
    return str(uid)


def update_auth_user(auth_uid: str, *, email: str | None = None, password: str | None = None) -> None:
    """
    Update an existing Supabase Auth user's email and/or password by UUID.
    Silently skips if both email and password are None.
    """
    payload: dict = {}
    if email    is not None: payload['email']    = email
    if password is not None: payload['password'] = password
    if not payload:
        return
    _admin_request('PUT', f'/users/{auth_uid}', payload)


# ---------------------------------------------------------------------------
# High-level sync
# ---------------------------------------------------------------------------

def sync_employee_credentials(emp_pk: int) -> None:
    """
    Create or update the Supabase Auth user for the employee identified by
    `emp_pk`.  Safe to call multiple times — idempotent.

    Called from the post_save signal (background thread) and from the
    seed_supabase_auth management command.

    Does nothing (but logs a warning) when Supabase credentials are absent
    from .env so that local-only development still works.
    """
    if not is_configured():
        logger.debug(
            'employees.supabase_auth_sync: SUPABASE_URL / SUPABASE_SERVICE_KEY '
            'not set — skipping Supabase auth sync for employee pk=%s', emp_pk,
        )
        return

    # Late import to avoid circular-import at module load (models → signals →
    # this module → models would be circular if we imported at the top).
    from employees.models import Employee  # noqa: PLC0415

    try:
        emp = Employee.objects.get(pk=emp_pk)
    except Employee.DoesNotExist:
        logger.warning('sync_employee_credentials: employee pk=%s not found', emp_pk)
        return

    if not emp.mobile_account_active:
        logger.debug('Skipping inactive employee pk=%s', emp_pk)
        return

    if not emp.employee_login_id:
        logger.debug('Skipping employee pk=%s — no employee_login_id set', emp_pk)
        return

    if not emp.mobile_app_password:
        # Password not yet stored in plain text (may have been cleared after
        # an employee-initiated reset). Cannot sync without the plain-text
        # password. Skip — existing Supabase user (if any) remains valid.
        logger.debug('Skipping employee pk=%s — mobile_app_password is empty', emp_pk)
        return

    email    = build_auth_email(emp.employee_login_id, emp.admin_id)
    password = emp.mobile_app_password

    if emp.auth_user_id:
        # Auth user already exists — update email (login_id may have changed)
        # and password.
        try:
            update_auth_user(str(emp.auth_user_id), email=email, password=password)
            logger.info(
                'Updated Supabase auth user %s for employee pk=%s (%s)',
                emp.auth_user_id, emp_pk, email,
            )
        except RuntimeError as exc:
            logger.error('Failed to update Supabase auth user for employee pk=%s: %s', emp_pk, exc)
    else:
        # No auth user yet — create one and write back the UUID.
        try:
            uid = create_auth_user(email, password)
            Employee.objects.filter(pk=emp_pk).update(auth_user_id=uid)
            logger.info(
                'Created Supabase auth user %s for employee pk=%s (%s)',
                uid, emp_pk, email,
            )
        except RuntimeError as exc:
            if 'already been registered' in str(exc) or 'already exists' in str(exc).lower():
                logger.warning(
                    'Supabase auth user for %s already exists but auth_user_id is '
                    'not set on employee pk=%s — run seed_supabase_auth to reconcile.',
                    email, emp_pk,
                )
            else:
                logger.error('Failed to create Supabase auth user for employee pk=%s: %s', emp_pk, exc)


def sync_employee_credentials_async(emp_pk: int) -> None:
    """
    Fire-and-forget wrapper: runs sync_employee_credentials in a daemon
    thread so the Django request/save cycle is never blocked by a Supabase
    HTTP call (which can take 100-500 ms).
    """
    t = threading.Thread(
        target=sync_employee_credentials,
        args=(emp_pk,),
        daemon=True,
        name=f'supabase-sync-emp-{emp_pk}',
    )
    t.start()
