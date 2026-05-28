"""
employees/signals.py

Django signals that keep Supabase Auth in sync whenever an employee's
mobile credentials change in SPIM Suite.

WHAT IS SYNCED
--------------
Supabase auth user is created/updated automatically when:
  • A new employee is saved with a mobile_app_password
  • An existing employee's mobile_app_password changes
  • An existing employee's employee_login_id changes (auth email must update)
  • An existing employee's admin_id changes (rare — auth email must update)

WHAT IS NOT SYNCED
------------------
  • Employee-initiated password resets via the mobile app (mobile_app_password
    is cleared in that case; the existing Supabase password continues to work
    until admin sets a new one from SPIM Suite).

HOW IT WORKS
------------
pre_save:  capture old field values BEFORE the write
post_save: compare old vs new; if relevant fields changed, fire background
           thread via sync_employee_credentials_async(emp.pk)
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender='employees.Employee')
def _capture_employee_snapshot(sender, instance, **kwargs):
    """
    Before saving, record the current DB values of the fields that control
    Supabase sync.  Stored as a private attribute so post_save can compare.
    """
    if instance.pk:
        # Existing row — fetch only the three fields we care about.
        try:
            old = sender.objects.values(
                'mobile_app_password',
                'employee_login_id',
                'admin_id',
                'auth_user_id',
            ).get(pk=instance.pk)
        except sender.DoesNotExist:
            old = None
    else:
        old = None

    instance._pre_save_snapshot = old   # None means this is a new record


@receiver(post_save, sender='employees.Employee')
def _sync_supabase_on_credential_change(sender, instance, created, **kwargs):
    """
    After saving, determine whether the Supabase auth user needs to be
    created or updated, then fire the sync asynchronously.
    """
    from employees.supabase_auth_sync import sync_employee_credentials_async  # noqa: PLC0415

    old = getattr(instance, '_pre_save_snapshot', None)

    if old is None:
        # Brand-new employee
        needs_sync = bool(instance.mobile_app_password and instance.employee_login_id)
    else:
        # Existing employee — sync if any of the auth-relevant fields changed
        needs_sync = (
            instance.mobile_app_password != old['mobile_app_password']
            or instance.employee_login_id != old['employee_login_id']
            or instance.admin_id         != old['admin_id']
        )

    if needs_sync:
        sync_employee_credentials_async(instance.pk)
